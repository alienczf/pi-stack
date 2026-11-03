import { createHash } from "node:crypto";
import { AutomaticAdmissionRejected } from "./automaticAdmissionStore.js";
import { persistedFailureBranch } from "./sessionFailureBoundary.js";
import { unresolvedEffects } from "./streamTransientRetry.js";
const CUSTOM_TYPE = "pi-web.failure-recovery";
function object(value) { return typeof value === "object" && value !== null && !Array.isArray(value); }
function canonical(value) {
    if (Array.isArray(value))
        return value.map(canonical);
    if (object(value))
        return Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])]));
    return value;
}
function hash(value) { return createHash("sha256").update(JSON.stringify(canonical(value))).digest("hex"); }
function evidence(value) { return object(value) && typeof value["entryId"] === "string" && value["entryId"] !== "" && typeof value["sha256"] === "string" && /^[a-f0-9]{64}$/.test(value["sha256"]); }
function validMaintenance(value) {
    if (value === undefined)
        return true;
    if (!object(value) || typeof value["id"] !== "string" || typeof value["expectedGeneration"] !== "string" || !["preparing", "ready", "uncertain"].includes(String(value["phase"])) || value["generation"] !== undefined && typeof value["generation"] !== "string" || value["phase"] === "ready" && (typeof value["generation"] !== "string" || value["generation"] === ""))
        return false;
    const sync = value["sync"];
    return sync === undefined || object(sync) && typeof sync["text"] === "string" && typeof sync["deliveryId"] === "string" && ["sending", "ended", "uncertain"].includes(String(sync["state"]));
}
function validOperation(value, session) {
    return object(value) && value["version"] === 1 && value["originalSessionId"] === session.sessionId && value["cwd"] === session.sessionManager.getCwd()
        && ["id", "episode", "root", "stream", "intentSha256", "generation"].every(key => typeof value[key] === "string")
        && value["authority"]?.kind === "engine-policy" && value["authority"].policyId === "enrolled-prefix-v1" && typeof value["authority"].enrollmentId === "string"
        && evidence(value["checkpoint"]) && evidence(value["failure"]) && validMaintenance(value["maintenance"])
        && ["fork-sending", "forked", "cancelled", "uncertain"].includes(String(value["state"]))
        && (value["forkSessionId"] === undefined || typeof value["forkSessionId"] === "string")
        && (value["forkFile"] === undefined || typeof value["forkFile"] === "string")
        && (value["forkGeneration"] === undefined || typeof value["forkGeneration"] === "string" && value["forkGeneration"] !== "");
}
export class SessionFailureRecoveries {
    constructor(control, hooks) {
        this.control = control;
        this.hooks = hooks;
        this.running = new Map();
        this.syncing = new Set();
    }
    policyConfigured() { return this.hooks.policy === "enrolled-prefix-v1"; }
    authorized(operation) {
        return operation?.authority?.kind === "engine-policy" && this.policyConfigured() && operation.authority.policyId === this.hooks.policy && typeof operation.authority.enrollmentId === "string";
    }
    operation(session, id) {
        const operation = this.operations(session).get(id);
        return operation === undefined ? undefined : structuredClone(operation);
    }
    save(session, operation) {
        if (session.sessionManager.appendCustomEntry === undefined)
            throw new AutomaticAdmissionRejected("Durable native recovery metadata is unavailable");
        session.sessionManager.appendCustomEntry(CUSTOM_TYPE, structuredClone(operation));
        persistedFailureBranch(session);
    }
    operations(session) {
        const records = new Map();
        for (const { value } of persistedFailureBranch(session)) {
            if (value["customType"] !== CUSTOM_TYPE)
                continue;
            const data = value["data"];
            if (!object(data) || data["originalSessionId"] !== session.sessionId)
                continue;
            if (!validOperation(data, session))
                throw new AutomaticAdmissionRejected("Native failure recovery metadata is invalid");
            records.set(data.id, structuredClone(data));
        }
        return records;
    }
    update(session, id, change) {
        const operation = this.operations(session).get(id);
        if (operation === undefined)
            throw new AutomaticAdmissionRejected("Recovery operation is unavailable");
        change(operation);
        this.save(session, operation);
        return operation;
    }
    async maintenance(original, request) {
        if (!object(request) || typeof request["id"] !== "string" || typeof request["action"] !== "string" || this.control === undefined)
            throw new AutomaticAdmissionRejected("Verified exact recovery maintenance is unavailable");
        const id = request["id"];
        let operation = this.operations(original).get(id);
        if (operation?.state !== "forked" || operation.forkSessionId === undefined || !this.authorized(operation))
            throw new AutomaticAdmissionRejected("Exact authorized forked recovery operation is required");
        const originalControl = this.control.snapshot({ id: operation.originalSessionId, cwd: operation.cwd });
        if (!originalControl.durable || originalControl.allowed || originalControl.generation !== operation.generation)
            throw new AutomaticAdmissionRejected("A newer original stop/input superseded recovery maintenance");
        const fork = await this.hooks.resolveFork(operation);
        const held = this.hooks.boundary(fork);
        if (fork.sessionId !== operation.forkSessionId || fork.sessionManager.getCwd() !== operation.cwd || held?.state !== "recovering" || held.recovery?.id !== id || held.recovery.originalSessionId !== operation.originalSessionId)
            throw new AutomaticAdmissionRejected("Returned fork is not held by this exact recovery owner");
        const ref = { id: fork.sessionId, cwd: operation.cwd };
        let automaticAdmission = this.control.snapshot(ref);
        if (request["action"] === "prepare") {
            if (typeof operation.forkGeneration !== "string" || request["expectedForkGeneration"] !== operation.forkGeneration)
                throw new AutomaticAdmissionRejected("Exact receiving-owned held-fork generation is required; a newer stop cannot authorize preparation");
            if (operation.maintenance !== undefined) {
                if (operation.maintenance.expectedGeneration !== request["expectedForkGeneration"] || operation.maintenance.phase !== "ready" || operation.maintenance.generation !== automaticAdmission.generation || !automaticAdmission.allowed || !automaticAdmission.durable)
                    throw new AutomaticAdmissionRejected("Prior maintenance preparation is uncertain or superseded; do not rearm");
                return { operation, automaticAdmission };
            }
            if (!automaticAdmission.durable || automaticAdmission.allowed || automaticAdmission.generation !== request["expectedForkGeneration"])
                throw new AutomaticAdmissionRejected("Held-fork generation changed before preparation");
            operation = this.update(original, id, current => { current.maintenance = { id, expectedGeneration: String(request["expectedForkGeneration"]), phase: "preparing" }; });
            try {
                automaticAdmission = await this.control.setAllowedAtGeneration(ref, true, automaticAdmission.generation);
                const after = this.control.snapshot({ id: operation.originalSessionId, cwd: operation.cwd });
                if (!after.durable || after.generation !== operation.generation)
                    throw new AutomaticAdmissionRejected("Original stop superseded preparation");
                operation = this.update(original, id, current => { if (current.maintenance !== undefined) {
                    current.maintenance.phase = "ready";
                    current.maintenance.generation = automaticAdmission.generation;
                } });
            }
            catch (error) {
                this.update(original, id, current => { if (current.maintenance !== undefined)
                    current.maintenance.phase = "uncertain"; current.detail = "Held-fork maintenance preparation is unconfirmed"; });
                throw error;
            }
            return { operation, automaticAdmission };
        }
        const maintenance = operation.maintenance;
        if (maintenance?.phase !== "ready" || maintenance.generation !== automaticAdmission.generation || !automaticAdmission.durable || !automaticAdmission.allowed)
            throw new AutomaticAdmissionRejected("Recovery maintenance generation is unprepared, stopped or uncertain");
        const key = JSON.stringify([operation.originalSessionId, operation.cwd, id]);
        if (request["action"] === "status") {
            if (maintenance.sync?.state === "sending" && !this.syncing.has(key))
                operation = this.update(original, id, current => { if (current.maintenance?.sync !== undefined)
                    current.maintenance.sync.state = "uncertain"; });
            return { operation, automaticAdmission };
        }
        if (request["action"] === "sync") {
            if (typeof request["text"] !== "string" || request["text"] === "" || request["deliveryId"] !== id + ":sync")
                throw new AutomaticAdmissionRejected("Exact correlated recovery SYNC is required");
            if (maintenance.sync !== undefined) {
                if (maintenance.sync.text !== request["text"] || maintenance.sync.deliveryId !== request["deliveryId"])
                    throw new AutomaticAdmissionRejected("Recovery SYNC changed immutable intent");
                if (maintenance.sync.state === "sending" && !this.syncing.has(key))
                    operation = this.update(original, id, current => { if (current.maintenance?.sync !== undefined)
                        current.maintenance.sync.state = "uncertain"; });
                return { operation, automaticAdmission };
            }
            operation = this.update(original, id, current => { if (current.maintenance !== undefined)
                current.maintenance.sync = { text: String(request["text"]), deliveryId: String(request["deliveryId"]), state: "sending" }; });
            this.syncing.add(key);
            void this.hooks.maintenance(fork, operation, request).then(() => {
                this.update(original, id, current => { if (current.maintenance?.sync !== undefined)
                    current.maintenance.sync.state = "ended"; });
            }, (error) => {
                this.update(original, id, current => { if (current.maintenance?.sync !== undefined)
                    current.maintenance.sync.state = "uncertain"; current.detail = error instanceof Error ? error.message : "Recovery SYNC admission is uncertain"; });
            }).catch(() => undefined).finally(() => { this.syncing.delete(key); });
            return { operation, automaticAdmission };
        }
        const metadataOnly = request["action"] === "watch" || request["action"] === "close";
        const liveSync = maintenance.sync?.state === "sending" && this.syncing.has(key);
        if (maintenance.sync?.state !== "ended" && !(metadataOnly && liveSync))
            throw new AutomaticAdmissionRejected("A completed owned recovery SYNC is required before maintenance effects");
        const result = await this.hooks.maintenance(fork, operation, request);
        return { operation: this.operations(original).get(id) ?? operation, automaticAdmission: this.control.snapshot(ref), ...result };
    }
    async fork(session, request) {
        if (!object(request) || typeof request["id"] !== "string" || !/^[A-Za-z0-9_.-]+$/.test(request["id"]) || typeof request["episode"] !== "string" || request["episode"] === "" || !object(request["expected"]))
            throw new AutomaticAdmissionRejected("Exact recovery operation, episode and expected checkpoint are required");
        const id = request["id"];
        const intent = hash(request);
        const key = JSON.stringify([session.sessionManager.getCwd(), session.sessionId, id]);
        const running = this.running.get(key);
        if (running !== undefined) {
            if (running.intent !== intent)
                throw new AutomaticAdmissionRejected("Recovery identity changed intent");
            return running.result;
        }
        const result = this.execute(session, id, request["episode"], request, intent);
        this.running.set(key, { intent, result });
        try {
            return await result;
        }
        finally {
            if (this.running.get(key)?.result === result)
                this.running.delete(key);
        }
    }
    async execute(session, id, episode, request, intent) {
        const records = this.operations(session);
        const previous = records.get(id);
        if (previous !== undefined) {
            if (previous.intentSha256 !== intent)
                throw new AutomaticAdmissionRejected("Recovery identity changed its exact request");
            if (previous.state === "fork-sending") {
                previous.state = "uncertain";
                previous.detail = "Prior fork owner is unavailable; no second fork is created";
                this.save(session, previous);
            }
            return previous;
        }
        if ([...records.values()].some(record => record.state !== "cancelled"))
            throw new AutomaticAdmissionRejected("An existing recovery owns this exact original; no second fork is created");
        if (!this.policyConfigured() || request["authority"]?.kind !== "engine-policy")
            throw new AutomaticAdmissionRejected("Configured recovery authority is unavailable; original remains parked");
        const boundary = this.hooks.boundary(session);
        const expected = request["expected"];
        if (boundary?.state !== "parked" || boundary.checkpoint === undefined || boundary.failure === undefined || !object(expected) || hash({ ...boundary, generation: expected["generation"] }) !== hash(expected))
            throw new AutomaticAdmissionRejected("Recovery checkpoint, branch or native failure identity changed");
        if (this.control === undefined)
            throw new AutomaticAdmissionRejected("Receiving generation control is unavailable");
        const ref = { id: session.sessionId, cwd: session.sessionManager.getCwd() };
        const control = this.control.snapshot(ref);
        if (!control.durable || control.allowed || expected["generation"] !== control.generation)
            throw new AutomaticAdmissionRejected("Saved parked generation is stale or unconfirmed");
        this.hooks.quiescent(session);
        const original = persistedFailureBranch(session);
        const at = original.findIndex(({ value }) => value["id"] === boundary.checkpoint?.entryId);
        const failed = original.findIndex(({ value }) => value["id"] === boundary.failure?.entryId);
        if (at < 0 || failed <= at || createHash("sha256").update(original[at]?.raw ?? "").digest("hex") !== boundary.checkpoint.sha256 || createHash("sha256").update(original[failed]?.raw ?? "").digest("hex") !== boundary.failure.sha256)
            throw new AutomaticAdmissionRejected("Saved recovery evidence hash/branch is unavailable");
        if (original.slice(failed + 1).some(({ value }) => object(value["message"]) && value["message"]["role"] === "user"))
            throw new AutomaticAdmissionRejected("Later accepted human input needs explicit ordered reconciliation before forking");
        const authority = request["authority"];
        const enrollment = boundary.enrollment;
        const continuation = request["continuation"];
        const assignment = enrollment ?? continuation;
        const binding = enrollment?.id ?? session.sessionId;
        if (authority.policyId !== this.hooks.policy || authority.enrollmentId !== binding || !object(assignment) || typeof assignment.role !== "string" || !/^[a-z][a-z0-9_-]*$/.test(assignment.role) || typeof assignment.assignment !== "string" || !assignment.assignment || createHash("sha256").update(assignment.assignment).digest("hex") !== assignment.assignmentSha256 || boundary.parking?.owned !== true || boundary.parking.generation !== control.generation || unresolvedEffects(original))
            throw new AutomaticAdmissionRejected("Engine policy lacks exact lane assignment, failure-owned parking or resolved effects");
        const authorization = { authority: { kind: "engine-policy", policyId: authority.policyId, enrollmentId: binding }, continuation: structuredClone(assignment) };
        this.hooks.quiescent(session);
        const frozen = await this.control.pauseAtGeneration(ref, control.generation);
        const operation = { version: 1, id, episode, originalSessionId: session.sessionId, cwd: ref.cwd, root: boundary.root, stream: boundary.stream, checkpoint: boundary.checkpoint, failure: boundary.failure, intentSha256: intent, ...authorization, generation: frozen.generation, state: "fork-sending" };
        this.save(session, operation);
        const model = session.model;
        const thinking = session.thinkingLevel;
        try {
            if (this.control.snapshot(ref).generation !== operation.generation)
                throw new AutomaticAdmissionRejected("Recovery was superseded by newer stop/input before forking");
            const result = await this.hooks.fork(session, operation);
            if (result.cancelled)
                operation.state = "cancelled";
            else {
                const fork = result.session;
                operation.forkSessionId = fork.sessionId;
                const file = fork.sessionManager.getSessionFile();
                if (file !== undefined)
                    operation.forkFile = file;
                if (fork.sessionId === session.sessionId || file === undefined || fork.sessionManager.getHeader?.()?.parentSession !== session.sessionManager.getSessionFile() || fork.model?.provider !== model?.provider || fork.model?.id !== model?.id || fork.thinkingLevel !== thinking)
                    throw new AutomaticAdmissionRejected("Fork identity, parent, model or thinking changed");
                const actual = persistedFailureBranch(fork).filter(({ value }) => value["type"] !== "label");
                const prefix = original.slice(0, at + 1).filter(({ value }) => value["type"] !== "label");
                let parent = null;
                for (let index = 0; index < prefix.length; index++) {
                    const entry = prefix[index]?.value;
                    if (entry === undefined || hash({ ...entry, parentId: parent }) !== hash(actual[index]?.value))
                        throw new AutomaticAdmissionRejected("Native fork did not preserve the exact inclusive logical prefix");
                    parent = String(entry["id"]);
                }
                if (actual.slice(prefix.length).some(({ value }) => value["type"] === "message") || this.hooks.boundary(fork)?.recovery?.id !== operation.id)
                    throw new AutomaticAdmissionRejected("Fork has unowned later task entries or no receiving recovery hold");
                const heldControl = this.control.snapshot({ id: fork.sessionId, cwd: operation.cwd });
                if (operation.forkGeneration === undefined || !heldControl.durable || heldControl.allowed || heldControl.generation !== operation.forkGeneration)
                    throw new AutomaticAdmissionRejected("A newer fork stop/input superseded its initial receiving hold; preserve both sessions");
                if (this.control.snapshot(ref).generation !== operation.generation)
                    throw new AutomaticAdmissionRejected("A newer stop/input superseded fork completion; preserve both sessions");
                operation.state = "forked";
            }
        }
        catch (error) {
            operation.state = "uncertain";
            operation.detail = error instanceof Error ? error.message : "Native fork outcome is uncertain";
        }
        this.save(session, operation);
        return structuredClone(operation);
    }
}
//# sourceMappingURL=sessionFailureRecovery.js.map