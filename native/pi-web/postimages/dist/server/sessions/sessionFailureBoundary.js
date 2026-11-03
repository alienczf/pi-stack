import { createHash, randomUUID } from "node:crypto";
import { isRetryableAssistantError } from "@earendil-works/pi-ai/compat";
import { closeSync, constants, fstatSync, fsyncSync, lstatSync, openSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, isAbsolute, resolve } from "node:path";
import { cwdPathsEqual } from "../workingDirectory.js";
import { AutomaticAdmissionRejected } from "./automaticAdmissionStore.js";
import { StreamTransientRetry, retryDispositions } from "./streamTransientRetry.js";
const CUSTOM_TYPE = "pi-web.stream-failure";
function object(value) { return typeof value === "object" && value !== null && !Array.isArray(value); }
function evidence(value) { return object(value) && typeof value["entryId"] === "string" && value["entryId"] !== "" && typeof value["sha256"] === "string" && /^[a-f0-9]{64}$/.test(value["sha256"]); }
function failureEvidence(value) {
    return object(value) && ["resource", "tool-login", "codex-login", "model-error", "transient"].includes(String(value["kind"])) && evidence(value);
}
function boundary(value, session) {
    return object(value)
        && value["version"] === 1 && value["sessionId"] === session.sessionId && value["cwd"] === session.sessionManager.getCwd()
        && typeof value["root"] === "string" && isAbsolute(value["root"])
        && typeof value["stream"] === "string" && /^[A-Za-z0-9_.-]+$/.test(value["stream"])
        && ["watching", "parked", "uncertain", "recovering"].includes(String(value["state"]))
        && (value["checkpoint"] === undefined || evidence(value["checkpoint"]))
        && (value["failure"] === undefined || failureEvidence(value["failure"]))
        && (value["state"] !== "parked" || value["failure"] !== undefined)
        && (value["state"] !== "recovering" || object(value["recovery"]) && typeof value["recovery"]["id"] === "string" && typeof value["recovery"]["originalSessionId"] === "string")
        && (value["detail"] === undefined || typeof value["detail"] === "string")
        && (value["enrollment"] === undefined || object(value["enrollment"]) && value["enrollment"].policyId === "enrolled-prefix-v1" && ["id", "role", "assignment", "assignmentSha256", "generation"].every(key => typeof value["enrollment"][key] === "string" && value["enrollment"][key] !== "") && createHash("sha256").update(value["enrollment"].assignment).digest("hex") === value["enrollment"].assignmentSha256)
        && (value["parking"] === undefined || object(value["parking"]) && typeof value["parking"].generation === "string" && typeof value["parking"].owned === "boolean");
}
function failure(message) {
    const text = typeof message["errorMessage"] === "string" ? message["errorMessage"] : JSON.stringify(message["content"] ?? []);
    const tool = message["role"] === "toolResult" && message["isError"] === true;
    if (!tool && !(message["role"] === "assistant" && message["stopReason"] === "error"))
        return undefined;
    if (!tool && (/insufficient_quota|quota exceeded|usage.?limit/i.test(text) || message["provider"] === "openai-codex" && /usage_not_included|rate_limit_exceeded/i.test(text)))
        return undefined;
    if (/ENOSPC|no space left|resource exhausted|out of memory/i.test(text))
        return "resource";
    if (/login expired|session expired|unauthorized|token expired|authentication expired/i.test(text))
        return tool ? "tool-login" : "codex-login";
    return tool ? undefined : !/usage.?limit/i.test(text) && isRetryableAssistantError(message) ? "transient" : "model-error";
}
function persistInitialRegistration(session) {
    const manager = session.sessionManager;
    const file = manager.getSessionFile();
    if (file === undefined)
        throw new Error("Registration requires its exact native file path");
    try {
        lstatSync(file);
        return;
    }
    catch (error) {
        if (!(error instanceof Error) || !("code" in error) || error.code !== "ENOENT")
            throw error;
    }
    if (session.messages.length !== 0 || session.isStreaming || session.isCompacting || session.isBashRunning || manager.getHeader === undefined || manager.getEntries === undefined || manager.setSessionFile === undefined)
        throw new Error("A busy or nonempty unpersisted runtime cannot confirm failure registration");
    const header = manager.getHeader();
    const entries = manager.getEntries();
    if (!object(header) || header["type"] !== "session" || header["id"] !== session.sessionId || header["cwd"] !== manager.getCwd() || entries.some(entry => object(entry) && entry["type"] === "message"))
        throw new Error("Initial registration cannot reconstruct missing native messages");
    const descriptor = openSync(file, constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW, 0o600);
    try {
        writeFileSync(descriptor, [header, ...entries].map(entry => JSON.stringify(entry) + "\n").join(""));
        fsyncSync(descriptor);
    }
    finally {
        closeSync(descriptor);
    }
    const directory = openSync(dirname(file), constants.O_RDONLY | constants.O_DIRECTORY | constants.O_NOFOLLOW);
    try {
        fsyncSync(directory);
    }
    finally {
        closeSync(directory);
    }
    manager.setSessionFile(file);
}
function persistedBranch(session) {
    const file = session.sessionManager.getSessionFile();
    if (file === undefined)
        throw new Error("A persisted native file is required for failure checkpoint evidence");
    const fd = openSync(file, constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK);
    try {
        const before = fstatSync(fd);
        if (!before.isFile())
            throw new Error("Failure checkpoint evidence must be regular");
        const lines = new TextDecoder("utf-8", { fatal: true }).decode(readFileSync(fd)).match(/[^\n]*\n|[^\n]+$/g) ?? [];
        const header = JSON.parse(lines[0] ?? "null");
        if (!object(header) || header["type"] !== "session" || header["id"] !== session.sessionId || typeof header["cwd"] !== "string" || !cwdPathsEqual(header["cwd"], session.sessionManager.getCwd()))
            throw new Error("Failure checkpoint native identity changed");
        const entries = new Map();
        for (const raw of lines.slice(1)) {
            if (raw.trim() === "")
                continue;
            const value = JSON.parse(raw);
            if (!object(value) || typeof value["id"] !== "string" || entries.has(value["id"]))
                throw new Error("Malformed or ambiguous persisted checkpoint entries");
            entries.set(value["id"], { value, raw });
        }
        for (const entry of session.sessionManager.getBranch()) {
            if (!object(entry) || typeof entry["id"] !== "string" || JSON.stringify(entries.get(entry["id"])?.value) !== JSON.stringify(entry))
                throw new Error("Native memory and synchronized branch disagree");
        }
        const branch = [];
        const seen = new Set();
        let id = session.sessionManager.getLeafId();
        while (id !== null) {
            const item = entries.get(id);
            if (seen.has(id) || item === undefined)
                throw new Error("Current branch is not completely persisted");
            seen.add(id);
            branch.push(item);
            const parent = item.value["parentId"];
            if (parent !== null && typeof parent !== "string")
                throw new Error("Incomplete checkpoint ancestry");
            id = parent;
        }
        const after = fstatSync(fd);
        const path = lstatSync(file);
        if (before.dev !== path.dev || before.ino !== path.ino || !path.isFile() || before.size !== after.size || before.mtimeMs !== after.mtimeMs || before.ctimeMs !== after.ctimeMs || after.size !== path.size || after.mtimeMs !== path.mtimeMs || after.ctimeMs !== path.ctimeMs)
            throw new Error("Failure checkpoint file changed during synchronization");
        fsyncSync(fd);
        const directory = openSync(dirname(file), constants.O_RDONLY | constants.O_DIRECTORY);
        try {
            fsyncSync(directory);
        }
        finally {
            closeSync(directory);
        }
        return branch.reverse();
    }
    finally {
        closeSync(fd);
    }
}
export function assertFailureLifecycleFile(file, sessionId, cwd) {
    if (file === undefined)
        return;
    let descriptor;
    try {
        descriptor = openSync(file, constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK);
    }
    catch (error) {
        if (error instanceof Error && "code" in error && error.code === "ENOENT")
            return;
        throw error;
    }
    try {
        const before = fstatSync(descriptor);
        if (!before.isFile())
            throw new AutomaticAdmissionRejected("Failure lifecycle evidence is not a regular file");
        const lines = new TextDecoder("utf-8", { fatal: true }).decode(readFileSync(descriptor)).match(/[^\n]*\n|[^\n]+$/g)?.filter(line => line.trim() !== "") ?? [];
        const values = [];
        const rawById = new Map();
        let malformed = false;
        for (const line of lines) {
            try {
                const value = JSON.parse(line);
                if (object(value)) {
                    values.push(value);
                    rawById.set(value["id"], line);
                }
                else
                    malformed = true;
            }
            catch {
                malformed = true;
            }
        }
        const stable = () => {
            const after = fstatSync(descriptor);
            const path = lstatSync(file);
            if (before.dev !== path.dev || before.ino !== path.ino || !path.isFile() || before.size !== after.size || before.mtimeMs !== after.mtimeMs || before.ctimeMs !== after.ctimeMs || after.size !== path.size || after.mtimeMs !== path.mtimeMs || after.ctimeMs !== path.ctimeMs)
                throw new AutomaticAdmissionRejected("Failure lifecycle file changed during observation");
        };
        const registered = values.some(value => value["type"] === "custom" && value["customType"] === CUSTOM_TYPE);
        if (!registered) {
            stable();
            return;
        }
        const header = values[0];
        if (malformed || header?.["type"] !== "session" || header["id"] !== sessionId || typeof header["cwd"] !== "string" || !cwdPathsEqual(header["cwd"], cwd))
            throw new AutomaticAdmissionRejected("Registered failure lifecycle identity is unconfirmed");
        const entries = new Map();
        for (const value of values.slice(1)) {
            if (typeof value["id"] !== "string" || entries.has(value["id"]))
                throw new AutomaticAdmissionRejected("Failure lifecycle entries are ambiguous");
            entries.set(value["id"], value);
        }
        const branch = [];
        const seen = new Set();
        let leaf = values.at(-1)?.["id"];
        while (leaf !== null) {
            if (typeof leaf !== "string" || seen.has(leaf))
                throw new AutomaticAdmissionRejected("Failure lifecycle branch is unconfirmed");
            const entry = entries.get(leaf);
            if (entry === undefined)
                throw new AutomaticAdmissionRejected("Failure lifecycle ancestry is incomplete");
            seen.add(leaf);
            branch.push(entry);
            leaf = entry["parentId"];
        }
        branch.reverse();
        const retries = retryDispositions(branch.map(value => ({ value, raw: rawById.get(value["id"]) })), sessionId, cwd);
        let watching = false;
        for (const entry of branch) {
            if (entry["type"] === "custom" && entry["customType"] === CUSTOM_TYPE && object(entry["data"]) && entry["data"]["sessionId"] === sessionId) {
                if (entry["data"]["version"] !== 1 || entry["data"]["cwd"] !== cwd || typeof entry["data"]["root"] !== "string" || !isAbsolute(entry["data"]["root"]) || typeof entry["data"]["stream"] !== "string" || entry["data"]["state"] !== "watching")
                    throw new AutomaticAdmissionRejected("Parked/recovering or unconfirmed stream failure requires its scoped verified retirement operation");
                watching = true;
            }
            if (watching && retries.has(entry["id"]) && !["resolved", "superseded"].includes(retries.get(entry["id"]).state))
                throw new AutomaticAdmissionRejected("Persisted retry has no completed native settlement");
            if (watching && object(entry["message"]) && failure(entry["message"]) !== undefined && !["resolved", "superseded"].includes(retries.get(entry["id"])?.state))
                throw new AutomaticAdmissionRejected("Persisted stream failure remains parked before lifecycle retirement");
        }
        if (!watching)
            throw new AutomaticAdmissionRejected("Inherited stream failure metadata has unknown fork ownership; preserve this session");
        stable();
    }
    finally {
        closeSync(descriptor);
    }
}
export { persistedBranch as persistedFailureBranch };
export class SessionFailureBoundaries {
    constructor(control, permitsRelease, enginePolicy) {
        this.control = control;
        this.enginePolicy = enginePolicy;
        this.permitsRelease = permitsRelease;
        this.records = new WeakMap();
        this.installed = new WeakSet();
        this.pending = new WeakSet();
        this.recoveryScopes = new WeakMap();
        this.retries = new WeakMap();
    }
    supported(session) {
        return this.control !== undefined && session.setRuntimeRetryPolicy !== undefined && session.agent.subscribe !== undefined && session.abortRetry !== undefined && session.sessionManager.appendCustomEntry !== undefined && session.sessionManager.getHeader !== undefined && session.sessionManager.getEntries !== undefined && session.sessionManager.setSessionFile !== undefined && session.sessionManager.getSessionFile() !== undefined;
    }
    snapshot(session) {
        const record = this.records.get(session);
        return record === undefined ? undefined : this.pending.has(session) ? { ...structuredClone(record), state: "uncertain", detail: "Native failure checkpoint publication is pending" } : structuredClone(record);
    }
    retrySnapshot(session) {
        return structuredClone(this.retries.get(session)?.active);
    }
    assertAdmission(session) {
        const record = this.records.get(session);
        if (record !== undefined && (record.state !== "watching" || record.recovery !== undefined && this.permitsRelease?.(session, record.recovery.id, record.recovery.originalSessionId) !== true))
            throw new AutomaticAdmissionRejected("Stream failure is parked; only its engine-owned good-prefix recovery may replace the original");
    }
    assertInternalAdmission(session) {
        const record = this.records.get(session);
        const scope = this.recoveryScopes.get(session);
        if (record?.state === "recovering" && scope !== undefined && record.recovery?.id === scope.id && scope.count > 0) {
            const fork = this.control?.snapshot({ id: session.sessionId, cwd: session.sessionManager.getCwd() });
            const original = this.control?.snapshot({ id: scope.originalSessionId, cwd: session.sessionManager.getCwd() });
            if (fork?.durable === true && fork.allowed && fork.generation === scope.generation && original?.durable === true && !original.allowed && original.generation === scope.originalGeneration)
                return;
            throw new AutomaticAdmissionRejected("Recovery inference was superseded by newer stop/input or unconfirmed control");
        }
        this.assertAdmission(session);
    }
    retainRecovery(session) {
        const scope = this.recoveryScopes.get(session);
        if (scope === undefined)
            return () => undefined;
        scope.count++;
        return () => { scope.count--; if (scope.count === 0)
            this.recoveryScopes.delete(session); };
    }
    async runRecovery(session, operation, action) {
        const id = operation.id;
        const record = this.records.get(session);
        if (record?.state !== "recovering" || record.recovery?.id !== id)
            throw new AutomaticAdmissionRejected("This exact operation does not own the held fork");
        const prior = this.recoveryScopes.get(session);
        if (prior !== undefined && prior.id !== id)
            throw new AutomaticAdmissionRejected("Another recovery owns runtime admission");
        if (operation.maintenance?.generation === undefined)
            throw new AutomaticAdmissionRejected("Recovery maintenance generation is unavailable");
        const scope = prior ?? { id, count: 0, generation: operation.maintenance.generation, originalSessionId: operation.originalSessionId, originalGeneration: operation.generation };
        scope.count++;
        this.recoveryScopes.set(session, scope);
        try {
            this.assertInternalAdmission(session);
            return await action();
        }
        finally {
            scope.count--;
            if (scope.count === 0)
                this.recoveryScopes.delete(session);
        }
    }
    attach(session) {
        if (!this.supported(session) || this.installed.has(session))
            return;
        this.installed.add(session);
        const entries = session.sessionManager.getBranch();
        for (const entry of entries) {
            if (!object(entry) || entry["type"] !== "custom" || entry["customType"] !== CUSTOM_TYPE || !object(entry["data"]) || entry["data"]["sessionId"] !== session.sessionId)
                continue;
            const data = entry["data"];
            if (!boundary(data, session))
                throw new AutomaticAdmissionRejected("Invalid persisted stream failure boundary");
            this.records.set(session, structuredClone(data));
        }
        const retry = new StreamTransientRetry(session, this.control, persistedBranch, () => this.records.has(session), () => this.observe(session));
        this.retries.set(session, retry);
        session.setRuntimeRetryPolicy(retry);
        if (this.records.has(session)) {
            retry.reconcile();
            void this.observe(session);
        }
        const stream = session.agent.streamFunction;
        session.agent.streamFunction = (...args) => { retry.assertInference(); this.assertInternalAdmission(session); return stream(...args); };
        const prepare = session.agent.prepareNextTurnWithContext;
        session.agent.prepareNextTurnWithContext = (context, signal) => { retry.assertInference(); this.assertInternalAdmission(session); return prepare?.(context, signal); };
        session.agent.subscribe?.(async (event) => {
            if (event.type === "turn_end" && this.records.has(session))
                await this.observe(session);
        });
    }
    async watch(session, request) {
        if (!this.supported(session) || !object(request) || typeof request["stream"] !== "string" || !/^[A-Za-z0-9_.-]+$/.test(request["stream"]) || typeof request["root"] !== "string" || !isAbsolute(request["root"]))
            throw new AutomaticAdmissionRejected("Exact stream registration and awaited native checkpoint capability are required");
        this.attach(session);
        const previous = this.records.get(session);
        const root = resolve(request["root"]);
        if (previous !== undefined) {
            if (previous.stream !== request["stream"] || previous.root !== root)
                throw new AutomaticAdmissionRejected("Failure boundary registration identity cannot change");
            if (request["enroll"] !== undefined) {
                if (previous.enrollment === undefined) {
                    const enrollment = this.assignment(session, request["enroll"], previous);
                    previous.enrollment = enrollment;
                    session.sessionManager.appendCustomEntry(CUSTOM_TYPE, structuredClone(previous));
                    persistedBranch(session);
                } else if (previous.enrollment.policyId !== request["enroll"]?.policyId || previous.enrollment.role !== request["enroll"]?.role || previous.enrollment.assignment !== request["enroll"]?.assignment)
                    throw new AutomaticAdmissionRejected("Saved lane assignment cannot be rebound");
            }
            if (previous.state === "uncertain")
                throw new AutomaticAdmissionRejected("Failure registration durability is uncertain; readiness cannot confirm it");
            try {
                persistedBranch(session);
            }
            catch (error) {
                this.records.set(session, { ...previous, state: "uncertain", detail: error instanceof Error ? error.message : "Registration durability is unconfirmed" });
                try {
                    await this.control?.setAllowed({ id: session.sessionId, cwd: session.sessionManager.getCwd() }, false);
                }
                catch { /* The runtime guard remains denied. */ }
                throw new AutomaticAdmissionRejected("Failure registration durability is uncertain; no task is admitted");
            }
            return structuredClone(previous);
        }
        const state = { version: 1, sessionId: session.sessionId, cwd: session.sessionManager.getCwd(), root, stream: request["stream"], state: "watching" };
        if (request["enroll"] !== undefined) {
            state.enrollment = this.assignment(session, request["enroll"], state);
        }
        this.records.set(session, { ...state, state: "uncertain", detail: "Failure registration publication is unconfirmed" });
        try {
            session.sessionManager.appendCustomEntry?.(CUSTOM_TYPE, structuredClone(state));
            persistInitialRegistration(session);
            persistedBranch(session);
            this.records.set(session, state);
            if (session.messages.length > 0)
                await this.observe(session);
            return structuredClone(this.snapshot(session) ?? state);
        }
        catch (error) {
            const failed = { ...state, state: "uncertain", detail: error instanceof Error ? error.message : "Failure registration publication failed" };
            this.records.set(session, failed);
            try {
                session.sessionManager.appendCustomEntry?.(CUSTOM_TYPE, structuredClone(failed));
                persistInitialRegistration(session);
                persistedBranch(session);
            }
            catch { /* Failed durability is retained, never converted into confirmed registration. */ }
            try {
                await this.control?.setAllowed({ id: session.sessionId, cwd: session.sessionManager.getCwd() }, false);
            }
            catch { /* Runtime admission remains fenced if stop publication also fails. */ }
            throw new AutomaticAdmissionRejected("Failure registration durability is uncertain; no first task is admitted");
        }
    }
    assignment(session, enroll, boundary) {
        const control = this.control.snapshot({ id: session.sessionId, cwd: session.sessionManager.getCwd() });
        if (this.enginePolicy !== "enrolled-prefix-v1" || !object(enroll) || enroll.policyId !== this.enginePolicy || typeof enroll.role !== "string" || !/^[a-z][a-z0-9_-]*$/.test(enroll.role) || typeof enroll.assignment !== "string" || !enroll.assignment.trim() || session.isStreaming || session.isCompacting || session.isBashRunning || !control.durable || !control.allowed && !(boundary.parking?.owned === true && boundary.parking.generation === control.generation))
            throw new AutomaticAdmissionRejected("Lane assignment requires configured policy and idle, unchanged receiving ownership");
        return { id: randomUUID(), policyId: this.enginePolicy, role: enroll.role, assignment: enroll.assignment, assignmentSha256: createHash("sha256").update(enroll.assignment).digest("hex"), generation: control.generation };
    }
    releaseRecovery(session, operation) {
        const previous = this.records.get(session);
        if (previous?.recovery?.id !== operation.id || previous.recovery.originalSessionId !== operation.originalSessionId || !["recovering", "watching"].includes(previous.state) || this.permitsRelease?.(session, operation.id, operation.originalSessionId) !== true)
            throw new AutomaticAdmissionRejected("No durable owned original deletion permits release");
        if (previous.state !== "watching") {
            const next = { ...previous, state: "watching" };
            try {
                session.sessionManager.appendCustomEntry?.(CUSTOM_TYPE, next);
                persistedBranch(session);
                this.records.set(session, next);
            }
            catch (error) {
                this.records.set(session, { ...previous, state: "uncertain", detail: "Recovery release durability is unconfirmed" });
                throw error;
            }
        }
        const saved = persistedBranch(session).filter(item => item.value["customType"] === CUSTOM_TYPE && object(item.value["data"]) && item.value["data"]["state"] === "watching" && object(item.value["data"]["recovery"]) && item.value["data"]["recovery"]["id"] === operation.id).at(-1);
        if (saved === undefined)
            throw new AutomaticAdmissionRejected("Recovery release has no exact native receipt");
        return { entryId: String(saved.value["id"]), sha256: createHash("sha256").update(saved.raw).digest("hex") };
    }
    async holdRecovery(session, operation) {
        if (!this.supported(session) || session.sessionId === operation.originalSessionId || !cwdPathsEqual(session.sessionManager.getCwd(), operation.cwd))
            throw new AutomaticAdmissionRejected("Recovery fork identity or receiving boundary is unavailable");
        this.attach(session);
        const held = { version: 1, sessionId: session.sessionId, cwd: session.sessionManager.getCwd(), root: operation.root, stream: operation.stream, state: "recovering", enrollment: { ...operation.continuation, id: session.sessionId, policyId: this.enginePolicy, generation: operation.generation }, recovery: { id: operation.id, originalSessionId: operation.originalSessionId } };
        this.records.set(session, held);
        try {
            session.sessionManager.appendCustomEntry?.(CUSTOM_TYPE, structuredClone(held));
            persistedBranch(session);
            const control = await this.control?.setAllowed({ id: session.sessionId, cwd: session.sessionManager.getCwd() }, false);
            if (control?.durable !== true || control.allowed)
                throw new AutomaticAdmissionRejected("Recovery hold generation is unconfirmed");
            operation.forkGeneration = control.generation;
        }
        catch (error) {
            this.records.set(session, { ...held, state: "uncertain", detail: "Recovery fork hold publication is unconfirmed" });
            throw error;
        }
    }
    async observe(session) {
        const previous = this.records.get(session);
        if (previous === undefined || previous.state !== "watching" && previous.state !== "recovering" || this.pending.has(session))
            return;
        this.pending.add(session);
        try {
            const branch = persistedBranch(session);
            const retries = retryDispositions(branch, session.sessionId, session.sessionManager.getCwd());
            const pending = new Set();
            let healthy = true;
            let checkpoint;
            let failed;
            for (const { value, raw } of branch) {
                const message = value["message"];
                if (!object(message))
                    continue;
                const disposition = retries.get(value["id"]);
                if (["resolved", "superseded"].includes(disposition?.state)) continue;
                if (disposition?.state === "pending" && this.retries.get(session)?.owns(disposition)) continue;
                if (disposition && ["pending", "cancelled", "uncertain"].includes(disposition.state))
                    throw new AutomaticAdmissionRejected("Retry ownership was cancelled or lost; no automatic replay");
                const kind = failure(message);
                if (kind !== undefined && failed === undefined)
                    failed = { entryId: String(value["id"]), sha256: createHash("sha256").update(raw).digest("hex"), kind };
                if (message["role"] === "assistant") {
                    healthy = pending.size === 0 && failed === undefined;
                    const content = message["content"];
                    if (Array.isArray(content))
                        for (const part of content)
                            if (object(part) && part["type"] === "toolCall" && typeof part["id"] === "string") {
                                if (pending.has(part["id"]))
                                    healthy = false;
                                pending.add(part["id"]);
                            }
                    if (message["stopReason"] === "error" || message["stopReason"] === "aborted" || message["stopReason"] === "length")
                        healthy = false;
                    else if (pending.size === 0 && healthy && failed === undefined && message["stopReason"] === "stop")
                        checkpoint = { entryId: String(value["id"]), sha256: createHash("sha256").update(raw).digest("hex") };
                }
                if (message["role"] === "toolResult") {
                    const call = message["toolCallId"];
                    if (typeof call !== "string" || !pending.delete(call) || message["isError"] === true)
                        healthy = false;
                    if (pending.size === 0 && healthy && failed === undefined)
                        checkpoint = { entryId: String(value["id"]), sha256: createHash("sha256").update(raw).digest("hex") };
                }
            }
            if (previous.state === "recovering" && failed === undefined)
                return;
            const next = { ...previous, ...(failed === undefined ? {} : { failure: failed, state: "parked" }) };
            delete next.checkpoint;
            if (checkpoint !== undefined)
                next.checkpoint = checkpoint;
            this.records.set(session, next);
            if (failed !== undefined) {
                const ref = { id: session.sessionId, cwd: session.sessionManager.getCwd() };
                const control = this.control.snapshot(ref);
                const parked = control.durable && control.allowed ? await this.control.setAllowedAtGeneration(ref, false, control.generation) : control;
                next.parking = { generation: parked.generation, owned: control.durable && control.allowed && parked.durable && !parked.allowed };
            }
            if (JSON.stringify(previous) !== JSON.stringify(next)) {
                session.sessionManager.appendCustomEntry?.(CUSTOM_TYPE, structuredClone(next));
                persistedBranch(session);
            }
        }
        catch (error) {
            this.records.set(session, { ...previous, state: "uncertain", detail: error instanceof Error ? error.message : "Failure checkpoint persistence is unconfirmed" });
            try {
                await this.control?.setAllowed({ id: session.sessionId, cwd: session.sessionManager.getCwd() }, false);
            }
            catch { /* In-memory boundary still refuses all new task admissions. */ }
        }
        finally {
            this.pending.delete(session);
        }
    }
}
//# sourceMappingURL=sessionFailureBoundary.js.map