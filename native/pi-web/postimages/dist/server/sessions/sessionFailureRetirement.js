import { createHash, randomUUID } from "node:crypto";
import { closeSync, constants, fstatSync, lstatSync, openSync, readFileSync } from "node:fs";
import { AutomaticAdmissionRejected } from "./automaticAdmissionStore.js";
import { persistedFailureBranch } from "./sessionFailureBoundary.js";
function object(value) { return typeof value === "object" && value !== null && !Array.isArray(value); }
function hash(raw) { return createHash("sha256").update(raw).digest("hex"); }
const STATES = new Set(["prepared", "archive-sending", "archived", "delete-sending", "deleted", "released", "uncertain"]);
export function validFailureRetirement(value, ref, id) {
    if (!object(value) || value["version"] !== 1 || value["id"] !== id || value["forkSessionId"] !== ref.id || value["cwd"] !== ref.cwd || !STATES.has(String(value["state"])) || !["originalSessionId", "originalFile", "cacheFile", "originalLeaf", "sourceSha256", "sourceBase64"].every(key => typeof value[key] === "string" && value[key] !== ""))
        return false;
    const operation = value["operation"];
    const model = value["model"];
    const observation = value["observation"];
    if (!object(operation) || operation["id"] !== id || operation["state"] !== "forked" || operation["originalSessionId"] !== value["originalSessionId"] || operation["forkSessionId"] !== ref.id || operation["cwd"] !== ref.cwd || typeof operation["generation"] !== "string" || !object(operation["maintenance"]) || typeof operation["maintenance"]["generation"] !== "string" || !object(model) || !["provider", "id", "thinking"].every(key => typeof model[key] === "string") || !object(observation) || observation["kind"] !== "assistant-stop" || !["entryId", "sha256", "deliveryId", "compactionEntryId", "userEntryId", "userSha256", "assistantEntryId", "assistantSha256"].every(key => typeof observation[key] === "string" && observation[key] !== ""))
        return false;
    const archive = value["archive"];
    const deleted = value["deleted"];
    const release = value["release"];
    if (archive !== undefined && (!object(archive) || archive["sessionId"] !== value["originalSessionId"] || archive["cwd"] !== ref.cwd || archive["originalPath"] !== value["originalFile"] || !["archivePath", "archivedAt"].every(key => typeof archive[key] === "string" && archive[key] !== "")))
        return false;
    if (["archived", "delete-sending", "deleted", "released"].includes(String(value["state"])) && archive === undefined)
        return false;
    if (deleted !== undefined && (!object(deleted) || deleted["sessionId"] !== value["originalSessionId"] || deleted["archivePath"] !== (object(archive) ? archive["archivePath"] : undefined) || deleted["sourceSha256"] !== value["sourceSha256"]))
        return false;
    if (["deleted", "released"].includes(String(value["state"])) && deleted === undefined)
        return false;
    if (release !== undefined && (!object(release) || typeof release["entryId"] !== "string" || typeof release["sha256"] !== "string"))
        return false;
    if (value["state"] === "released" && release === undefined)
        return false;
    return hash(Buffer.from(String(value["sourceBase64"]), "base64")) === value["sourceSha256"];
}
export function retirementSource(file, sid, cwd) {
    const descriptor = openSync(file, constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK);
    try {
        const before = fstatSync(descriptor);
        if (!before.isFile())
            throw new Error("Retirement evidence must be regular");
        const raw = readFileSync(descriptor);
        const header = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(raw).split("\n")[0] ?? "null");
        const after = fstatSync(descriptor);
        const path = lstatSync(file);
        if (!object(header) || header["type"] !== "session" || header["id"] !== sid || header["cwd"] !== cwd || [after, path].some(stat => stat.dev !== before.dev || stat.ino !== before.ino || stat.mode !== before.mode || stat.size !== before.size || stat.mtimeMs !== before.mtimeMs || stat.ctimeMs !== before.ctimeMs))
            throw new Error("Retirement evidence identity or stable source changed");
        return raw;
    }
    finally {
        closeSync(descriptor);
    }
}
function ownedResume(session, maintenance) {
    const observation = maintenance.resume?.observation;
    if (maintenance.state !== "resumed" || maintenance.inputSequence !== 0 || maintenance.resume?.state !== "admitted" || maintenance.resume.inputSequence !== 0 || observation === undefined || maintenance.compactionEntryId === undefined || maintenance.compactionSha256 === undefined || maintenance.resume.deliveryId !== maintenance.id + ":resume" || maintenance.resume.generation !== maintenance.generation)
        throw new AutomaticAdmissionRejected("Owned completed RESUME/compaction evidence is required before retirement");
    const branch = persistedFailureBranch(session);
    const position = (id) => branch.findIndex(item => item.value["id"] === id);
    const indices = [maintenance.compactionEntryId, observation.userEntryId, observation.assistantEntryId, observation.entryId].map(position);
    if (indices.some(index => index < 0) || !indices.every((index, at) => at === 0 || index > (indices[at - 1] ?? index)))
        throw new AutomaticAdmissionRejected("Owned RESUME evidence is not on the ordered current branch");
    const saved = branch[indices[3] ?? -1];
    const user = branch[indices[1] ?? -1];
    const assistant = branch[indices[2] ?? -1];
    const compaction = branch[indices[0] ?? -1];
    const expected = { kind: "assistant-stop", operationId: maintenance.id, sessionId: session.sessionId, cwd: maintenance.cwd, generation: maintenance.generation, deliveryId: maintenance.id + ":resume", compactionEntryId: maintenance.compactionEntryId, userEntryId: observation.userEntryId, userSha256: observation.userSha256, assistantEntryId: observation.assistantEntryId, assistantSha256: observation.assistantSha256 };
    if (saved === undefined || user === undefined || hash(user.raw) !== observation.userSha256 || assistant === undefined || compaction === undefined || hash(saved.raw) !== observation.sha256 || saved.value["customType"] !== "pi-web.resume-observed" || JSON.stringify(saved.value["data"]) !== JSON.stringify(expected) || hash(assistant.raw) !== observation.assistantSha256 || !object(assistant.value["message"]) || assistant.value["message"]["role"] !== "assistant" || assistant.value["message"]["stopReason"] !== "stop" || hash(compaction.raw) !== maintenance.compactionSha256 || compaction.value["type"] !== "compaction")
        throw new AutomaticAdmissionRejected("Owned RESUME completion/hash changed");
    const later = branch.slice((indices[0] ?? -1) + 1).map(item => item.value["message"]).filter(object);
    if (later.filter(message => message["role"] === "user").length !== 1 || later.some(message => message["stopReason"] === "error" || message["stopReason"] === "aborted"))
        throw new AutomaticAdmissionRejected("New input or failed RESUME superseded retirement");
    return observation;
}
export class SessionFailureRetirements {
    constructor(store, controls, hooks) {
        this.store = store;
        this.controls = controls;
        this.hooks = hooks;
        this.running = new Map();
    }
    permitsRelease(session, id, originalSessionId) {
        const retirement = this.store.get({ id: session.sessionId, cwd: session.sessionManager.getCwd() }, id)?.retirement;
        return retirement?.originalSessionId === originalSessionId && retirement.deleted?.sessionId === originalSessionId && (retirement.state === "deleted" || retirement.state === "released");
    }
    async retire(ref, request) {
        if (!this.hooks.configured() || !object(request) || typeof request["id"] !== "string" || typeof request["forkSessionId"] !== "string" || request["forkSessionId"] === ref.id)
            throw new AutomaticAdmissionRejected("Exact configured recovery retirement owner is required");
        const key = JSON.stringify([ref.cwd, ref.id, request["id"]]);
        const running = this.running.get(key);
        if (running !== undefined) {
            if (running.fork !== request["forkSessionId"])
                throw new AutomaticAdmissionRejected("Retirement identity changed fork");
            return running.promise;
        }
        const promise = this.execute(ref, request["id"], request["forkSessionId"]);
        this.running.set(key, { fork: request["forkSessionId"], promise });
        try {
            return await promise;
        }
        finally {
            if (this.running.get(key)?.promise === promise)
                this.running.delete(key);
        }
    }
    async execute(ref, id, forkSessionId) {
        const forkRef = { id: forkSessionId, cwd: ref.cwd };
        const fork = await this.hooks.resolve(forkRef);
        if (fork.sessionId !== forkSessionId || fork.sessionManager.getCwd() !== ref.cwd)
            throw new AutomaticAdmissionRejected("Retirement requires the full exact returned fork SID/cwd");
        const maintenance = this.store.get(forkRef, id);
        if (maintenance === undefined)
            throw new AutomaticAdmissionRejected("Completed native maintenance is unavailable");
        let retirement = maintenance.retirement;
        const save = () => { const next = retirement; if (next === undefined)
            throw new Error("Missing retirement intent"); this.store.update(forkRef, id, current => { current.retirement = structuredClone(next); }); };
        const response = () => { if (retirement === undefined)
            throw new Error("Missing retirement result"); const { sourceBase64, ...receipt } = retirement; if (hash(Buffer.from(sourceBase64, "base64")) !== receipt.sourceSha256)
            throw new Error("Retained source cache hash changed"); return receipt; };
        if (retirement !== undefined && (retirement.id !== id || retirement.originalSessionId !== ref.id || retirement.forkSessionId !== forkSessionId || retirement.cwd !== ref.cwd))
            throw new AutomaticAdmissionRejected("Persisted retirement identity changed");
        if (retirement?.state === "released")
            return response();
        if (retirement?.state === "delete-sending" || retirement?.state === "uncertain")
            throw new AutomaticAdmissionRejected("Prior deletion outcome is uncertain; never replay or infer success from absence");
        if (retirement === undefined) {
            const observation = ownedResume(fork, maintenance);
            const original = await this.hooks.resolve(ref);
            if (original.sessionId !== ref.id || original.sessionManager.getCwd() !== ref.cwd)
                throw new AutomaticAdmissionRejected("Retirement requires the full exact original SID/cwd");
            const operation = this.hooks.operation(original, id);
            if (operation?.state !== "forked" || !this.hooks.authorized(operation) || operation.forkSessionId !== forkSessionId || operation.cwd !== ref.cwd || operation.maintenance?.generation !== maintenance.generation)
                throw new AutomaticAdmissionRejected("Exact recorded recovery fork/epoch is required");
            this.hooks.quiescent(original);
            this.hooks.quiescent(fork, operation);
            const branch = persistedFailureBranch(original);
            const checkpoint = branch.findIndex(item => item.value["id"] === operation.checkpoint.entryId);
            const failed = branch.findIndex(item => item.value["id"] === operation.failure.entryId);
            if (checkpoint < 0 || failed <= checkpoint || hash(branch[checkpoint].raw) !== operation.checkpoint.sha256 || hash(branch[failed].raw) !== operation.failure.sha256)
                throw new AutomaticAdmissionRejected("Retirement changed its exact good-prefix/failure evidence");
            const jobs = new Set();
            for (const { value } of branch) {
                const message = value["message"];
                if (!object(message) || message["role"] !== "toolResult" || !object(message["details"]))
                    continue;
                const details = message["details"];
                const job = details["jobId"] ?? details["job_id"] ?? details["externalJobId"];
                if (typeof job !== "string" || job === "")
                    continue;
                const state = typeof details["status"] === "string" ? details["status"] : "unknown";
                if (["completed", "succeeded", "failed", "cancelled"].includes(state))
                    jobs.delete(job);
                else
                    jobs.add(job);
            }
            if (failed < 0 || jobs.size > 0 || branch.slice(failed + 1).some(item => object(item.value["message"]) && item.value["message"]["role"] === "user"))
                throw new AutomaticAdmissionRejected("Original input or uncertain external job still owns retirement");
            const file = original.sessionManager.getSessionFile();
            const leaf = original.sessionManager.getLeafId();
            if (file === undefined || leaf === null || original.model === undefined || fork.model?.provider !== original.model.provider || fork.model.id !== original.model.id || fork.thinkingLevel !== original.thinkingLevel || await this.hooks.archived(ref) !== undefined)
                throw new AutomaticAdmissionRejected("Exact original file/model/archive ownership is unconfirmed");
            const source = retirementSource(file, ref.id, ref.cwd);
            retirement = { version: 1, id, originalSessionId: ref.id, forkSessionId, cwd: ref.cwd, operation, observation, originalFile: file, cacheFile: this.store.location(forkRef), originalLeaf: leaf, model: { provider: original.model.provider, id: original.model.id, thinking: original.thinkingLevel }, sourceSha256: hash(source), sourceBase64: source.toString("base64"), state: "prepared" };
            this.guard(retirement, fork, maintenance);
            save();
        }
        let completionGuard;
        this.guard(retirement, fork, maintenance);
        if (retirement.state === "prepared") {
            const original = await this.hooks.resolve(ref);
            this.hooks.quiescent(original);
            if (original.sessionManager.getLeafId() !== retirement.originalLeaf || hash(retirementSource(retirement.originalFile, ref.id, ref.cwd)) !== retirement.sourceSha256)
                throw new AutomaticAdmissionRejected("Original evidence changed before archive");
            retirement.state = "archive-sending";
            save();
        }
        if (retirement.state === "archive-sending" || retirement.state === "archived" || retirement.state === "deleted" && retirement.deleted?.protocol === "intent-quarantine-v1") {
            const current = retirement;
            const guard = () => { this.guard(current, fork, this.store.get(forkRef, id) ?? maintenance); };
            const attemptId = randomUUID();
            const result = await this.hooks.complete(current, fork, guard, state => {
                guard();
                const prior = current.completionDispatch;
                const attempts = prior?.attempts ?? [];
                current.completionDispatch = { version: 1, kind: "artifact-completion", anyStoreDispatched: prior?.anyStoreDispatched === true || state === "store-dispatched", attempts: [...attempts.filter(attempt => attempt.id !== attemptId), { id: attemptId, state }] };
                save();
            });
            completionGuard = result.verify;
            completionGuard();
            const archived = result.archive, deleted = result.deleted;
            if (archived?.sessionId !== ref.id || archived.cwd !== ref.cwd || archived.originalPath !== current.originalFile || archived.recoveryOperationId !== id || deleted?.protocol !== "intent-quarantine-v1" || deleted.completionId !== archived.recoveryCompletionId || deleted.sessionId !== ref.id || deleted.archivePath !== archived.archivePath || deleted.sourceSha256 !== current.sourceSha256)
                throw new AutomaticAdmissionRejected("Positive same-intent archive and deletion receipts are required");
            retirement.archive = { sessionId: ref.id, cwd: ref.cwd, originalPath: current.originalFile, archivePath: archived.archivePath, archivedAt: archived.archivedAt };
            retirement.deleted = deleted;
            retirement.state = "deleted";
            save();
        }
        if (retirement.state === "deleted") {
            completionGuard?.();
            this.guard(retirement, fork, maintenance);
            retirement.release = this.hooks.release(fork, retirement.operation);
            retirement.state = "released";
            save();
        }
        return response();
    }
    guard(retirement, fork, maintenance) {
        if (retirement.cacheFile !== this.store.location({ id: retirement.forkSessionId, cwd: retirement.cwd }) || hash(Buffer.from(retirement.sourceBase64, "base64")) !== retirement.sourceSha256 || maintenance.retirement !== undefined && ["sourceBase64", "sourceSha256", "originalFile", "originalLeaf", "cacheFile"].some(key => maintenance.retirement[key] !== retirement[key]))
            throw new AutomaticAdmissionRejected("Protected retirement cache or original binding changed");
        if (!this.hooks.authorized(retirement.operation))
            throw new AutomaticAdmissionRejected("The saved recovery authority is unavailable");
        this.controls.assertSettled({ id: retirement.originalSessionId, cwd: retirement.cwd });
        this.controls.assertSettled({ id: retirement.forkSessionId, cwd: retirement.cwd });
        if (typeof this.controls.recoverySnapshot !== "function")
            throw new AutomaticAdmissionRejected("Fresh durable recovery epoch reads are unavailable");
        const original = this.controls.recoverySnapshot({ id: retirement.originalSessionId, cwd: retirement.cwd });
        const current = this.controls.recoverySnapshot({ id: retirement.forkSessionId, cwd: retirement.cwd });
        if (!original.durable || original.allowed || original.generation !== retirement.operation.generation || !current.durable || !current.allowed || current.generation !== retirement.operation.maintenance?.generation)
            throw new AutomaticAdmissionRejected("Newer original/fork stop, input or unconfirmed epoch superseded retirement");
        this.hooks.quiescent(fork, retirement.operation);
        const boundary = this.hooks.boundary(fork);
        if (boundary?.recovery?.id !== retirement.id || boundary.recovery.originalSessionId !== retirement.originalSessionId || boundary.state !== "recovering" && !(boundary.state === "watching" && retirement.deleted !== undefined))
            throw new AutomaticAdmissionRejected("Exact fork recovery hold is unknown or failed");
        if (fork.model?.provider !== retirement.model.provider || fork.model.id !== retirement.model.id || fork.thinkingLevel !== retirement.model.thinking || JSON.stringify(ownedResume(fork, maintenance)) !== JSON.stringify(retirement.observation))
            throw new AutomaticAdmissionRejected("Fork model or completed RESUME proof changed");
    }
}
//# sourceMappingURL=sessionFailureRetirement.js.map