import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { estimateTokens } from "@earendil-works/pi-coding-agent";
import { AutomaticAdmissionRejected, parseAutomaticAdmission } from "./automaticAdmissionStore.js";
import { maintenanceEvidence } from "./sessionMaintenanceEvidence.js";
import { canonicalizeStoredCwd } from "../workingDirectory.js";
import { completedResumeEvidence } from "./sessionResumeEvidence.js";
import { persistedFailureBranch } from "./sessionFailureBoundary.js";
function record(value) {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}
function key(ref, id) { return JSON.stringify([ref.cwd, ref.id, id]); }
function identity(session) { return { id: session.sessionId, cwd: canonicalizeStoredCwd(session.sessionManager.getCwd()) }; }
function operationId(value) {
    if (typeof value !== "string" || value.trim() !== value || value === "" || /[\r\n\0]/.test(value))
        throw new AutomaticAdmissionRejected("Maintenance requires a stable operation id");
    return value;
}
const contextTokens = session => session.messages.reduce((sum, message) => sum + estimateTokens(message), 0);
const liveOwners = new Set();
function processStart(pid) {
    if (!Number.isSafeInteger(pid) || pid <= 0) return "unknown";
    try { return readFileSync(`/proc/${pid}/stat`, "utf8").split(") ").at(-1).split(" ")[19]; }
    catch (error) { return error.code === "ENOENT" ? undefined : "unknown"; }
}
function contextBudget(session) {
    const model = session.model;
    if (!Number.isSafeInteger(model?.contextWindow) || model.contextWindow <= 0)
        throw new AutomaticAdmissionRejected("Same-model safe context capacity is unknown");
    return { provider: model.provider, model: model.id, contextWindow: model.contextWindow, targetTokens: Math.floor(model.contextWindow * 0.8) };
}
function budgetMatches(session, operation) {
    return JSON.stringify(operation.contextBudget) === JSON.stringify(contextBudget(session)) && operation.targetTokens === operation.contextBudget.targetTokens;
}
function transparentSuffix(session, operation, branch = persistedFailureBranch(session)) {
    const at = branch.findIndex(item => item.value.id === operation.compactionEntryId);
    if (at < 0) return false;
    const prior = branch.slice(0, at).filter(item => item.value.customType === "pi-web.stream-failure" && item.value.data?.sessionId === session.sessionId).at(-1)?.value.data;
    return branch.slice(at + 1).every(({ value }) => value.type === "custom" && (
        value.customType === "pi-web.stream-failure" && ["watching", "recovering"].includes(value.data?.state) && !value.data.failure && JSON.stringify(value.data) === JSON.stringify(prior)
        || value.customType === "pi-web.streams-dcr" && value.data?.version === undefined && value.data?.sessionId === session.sessionId && value.data?.cwd === operation.cwd && value.data?.id === operation.id && value.data?.generation === operation.generation && value.data?.state === "active"
    ));
}
export class SessionMaintenanceController {
    constructor(store, controls, host) {
        this.store = store;
        this.controls = controls;
        this.host = host;
        this.compacting = new Map();
        this.draining = new Set();
        this.resuming = new Set();
    }
    start(session, request, expected) {
        if (!record(request) || typeof request["instructions"] !== "string")
            throw new AutomaticAdmissionRejected("Maintenance requires exact compaction instructions");
        const id = operationId(request["id"]);
        const ref = identity(session);
        if (ref.id !== expected.sessionId || ref.cwd !== expected.cwd)
            throw new AutomaticAdmissionRejected("Maintenance checkpoint destination changed");
        const previous = this.store.get(ref, id);
        if (previous !== undefined) {
            if (previous.entryId !== expected.entryId || previous.generation !== expected.generation || previous.instructions !== request["instructions"])
                throw new AutomaticAdmissionRejected("Maintenance operation changed intent");
            return this.status(session, id);
        }
        const current = this.store.current(ref);
        if (current !== undefined) this.status(session, current.id);
        this.controls.assertCurrent(ref, { ...expected, kind: "wake" });
        if (!this.host.current(session) || this.host.busy(session) || this.host.humanInputPending(session))
            throw new AutomaticAdmissionRejected("Maintenance requires the expected idle checkpoint without pending human input");
        if (session.sessionManager.getLeafId() !== expected.entryId || session.sessionManager.appendCustomEntry === undefined)
            throw new AutomaticAdmissionRejected("Maintenance checkpoint is stale or native marker capability is unavailable");
        const operation = this.store.create(ref, { version: 1, id, sessionId: ref.id, cwd: ref.cwd, entryId: expected.entryId, generation: expected.generation, instructions: request["instructions"], targetTokens: contextBudget(session).targetTokens, contextBudget: contextBudget(session), ownerProcess: { pid: process.pid, start: processStart(process.pid) }, tokensBefore: contextTokens(session), state: "prepared", inputSequence: 0, lastInputGeneration: expected.generation, inputs: [] });
        const opKey = key(ref, id);
        this.compacting.set(opKey, session);
        liveOwners.add(opKey);
        try {
            this.host.begin(session);
            const markerEntryId = session.sessionManager.appendCustomEntry("pi-web.maintenance", { id, sessionId: ref.id, cwd: ref.cwd, entryId: expected.entryId, generation: expected.generation });
            maintenanceEvidence(session.sessionFile, operation);
            this.store.update(ref, id, (current) => { current.markerEntryId = markerEntryId; current.state = "compacting"; });
            this.controls.assertCurrent(ref, { ...expected, kind: "wake" });
            this.background(session, this.compact(session, id));
            return this.required(ref, id);
        }
        catch (error) {
            this.compacting.delete(opKey);
            liveOwners.delete(opKey);
            this.host.end(session);
            this.store.update(ref, id, (current) => { current.state = "uncertain"; current.detail = error instanceof Error ? error.message : String(error); });
            throw error;
        }
    }
    status(session, id) {
        const ref = identity(session);
        let operation = this.required(ref, id);
        const opKey = key(ref, id);
        const owner = operation.ownerProcess;
        const start = owner === undefined ? undefined : processStart(owner.pid);
        const processAlive = owner !== undefined && owner.pid !== process.pid && start !== undefined && (start === "unknown" || start === owner.start);
        const live = liveOwners.has(opKey) || processAlive || this.compacting.has(opKey) || this.draining.has(opKey) || this.resuming.has(opKey) || !this.host.current(session) || this.host.busy(session) || session.isStreaming || session.isCompacting || session.isBashRunning;
        const legacyGate = operation.targetTokens === 150000 && /^Native compaction did not reduce rebuilt context below 150000 tokens$/.test(operation.detail ?? "");
        if (!live && (operation.state === "prepared" || operation.state === "compacting" || operation.state === "uncertain" && operation.compactionEntryId === undefined && operation.resume === undefined && operation.inputs.every((input) => input.state === "queued") || (operation.state === "failed" && legacyGate || operation.state === "complete" && operation.targetTokens === 150000 && operation.contextBudget === undefined) && operation.resume === undefined && operation.inputs.length === 0)) {
            try {
                const evidence = maintenanceEvidence(session.sessionFile, operation);
                const branch = persistedFailureBranch(session);
                const at = branch.findIndex(item => item.value.id === operation.entryId);
                if (at < 0 || branch.slice(at + 1).some(item => ["model_change", "thinking_level_change"].includes(item.value.type)))
                    throw new AutomaticAdmissionRejected("Maintenance same-model checkpoint changed before reconciliation");
                operation = this.store.update(ref, id, (current) => {
                    Object.assign(current, evidence);
                    current.tokensAfter = contextTokens(session);
                    current.contextBudget = contextBudget(session);
                    current.targetTokens = current.contextBudget.targetTokens;
                    current.state = evidence.compactionEntryId === undefined ? "uncertain" : Number.isSafeInteger(current.tokensAfter) && current.tokensAfter >= 0 && current.tokensAfter < current.targetTokens ? "complete" : "failed";
                    if (legacyGate && current.state === "complete") current.detail = "Reconciled completed native compaction against the same-model safe capacity; admission remains unchanged";
                    if (evidence.compactionEntryId === undefined)
                        current.detail = "Interrupted maintenance has no proven completed native compaction; do not replay";
                });
            }
            catch (error) {
                operation = this.store.update(ref, id, (current) => { current.state = "uncertain"; current.detail = error instanceof Error ? error.message : String(error); });
            }
        }
        if (!live && !this.draining.has(opKey) && operation.inputs.some((input) => input.state === "sending"))
            operation = this.store.update(ref, id, (current) => { current.state = "uncertain"; for (const input of current.inputs)
                if (input.state === "sending")
                    input.state = "uncertain"; current.detail = "Interrupted input admission is uncertain; preserve its ordered prefix without replay"; });
        if (operation.state === "resuming" && !live && !this.resuming.has(opKey))
            operation = this.store.update(ref, id, (current) => { current.state = "uncertain"; if (current.resume !== undefined)
                current.resume.state = "uncertain"; current.detail = "Interrupted RESUME admission must be reconciled, never replayed"; });
        if (!live && ["failed", "uncertain"].includes(operation.state) && operation.resume === undefined && operation.inputs.length === 0 && operation.inputSequence === 0) {
            operation = this.store.update(ref, id, current => { const prior = current.state; current.state = "superseded"; current.detail = `Dead empty maintenance ownership released without replay. Prior ${prior}: ${current.detail ?? "unconfirmed"}`; });
        }
        if (operation.state === "complete" && operation.resume === undefined && operation.inputs.length === 0 && !live) {
            const control = this.controls.snapshot(ref);
            const evidence = maintenanceEvidence(session.sessionFile, operation);
            const branch = persistedFailureBranch(session);
            const at = branch.findIndex(item => item.value.id === operation.compactionEntryId);
            if (evidence.compactionSha256 !== operation.compactionSha256 || at < 0)
                throw new AutomaticAdmissionRejected("Completed maintenance compaction proof changed; preserve ownership");
            const newerInput = branch.slice(at + 1).some(item => item.value.message?.role === "user");
            const checkpointChanged = session.sessionManager.getLeafId() !== operation.compactionEntryId && !transparentSuffix(session, operation, branch);
            if (control.durable && (control.generation !== operation.generation || newerInput || checkpointChanged))
                operation = this.store.update(ref, id, current => { current.state = "superseded"; current.detail = "Verified completed compaction was superseded by newer receiving input or stop; no RESUME is replayed"; });
        }
        return operation;
    }
    hasInput(session, text, kind, images, attachments, deliveryId, potetoGoal) {
        const operation = this.store.current(identity(session));
        const input = operation?.inputs.find((candidate) => candidate.id === deliveryId);
        if (input === undefined)
            return false;
        if (JSON.stringify([input.text, input.kind, input.images, input.attachments, input.potetoGoal]) !== JSON.stringify([text, kind, images, attachments, potetoGoal]))
            throw new AutomaticAdmissionRejected("Accepted maintenance input id changed intent");
        return true;
    }
    activateQueued(session) {
        const operation = this.store.current(identity(session));
        if (operation !== undefined && operation.cancelledByStop !== true && (operation.state === "complete" || operation.state === "superseded") && operation.inputs.some(input => input.state === "queued") && !operation.inputs.some(input => input.state === "sending" || input.state === "uncertain"))
            this.background(session, this.drain(session, operation.id));
    }
    queue(session, text, kind, images, attachments, echo, deliveryId, potetoGoal) {
        const ref = identity(session);
        let operation = this.store.current(ref);
        if (operation === undefined)
            return false;
        const opKey = key(ref, operation.id);
        const owner = this.compacting.get(opKey);
        if (operation.cancelledByStop === true)
            return false;
        if (owner !== undefined && owner !== session) {
            operation = this.store.update(ref, operation.id, (current) => { current.state = "uncertain"; current.detail = "Maintenance runtime changed; preserve prior accepted input"; });
        }
        if ((operation.state === "prepared" || operation.state === "compacting") && owner === undefined && !session.isCompacting)
            operation = this.status(session, operation.id);
        const unresolved = operation.inputs.some((input) => input.state === "queued" || input.state === "sending" || input.state === "uncertain");
        if (unresolved && !this.draining.has(opKey) && (operation.state === "uncertain" || operation.state === "failed" || operation.state === "superseded"))
            throw new AutomaticAdmissionRejected("Earlier maintenance input has an unresolved ordered prefix; retain new input pending reconciliation or an explicit stop/cancel");
        const control = this.controls.snapshot(ref);
        if (!control.allowed) {
            if (!unresolved && operation.state === "complete" && owner === undefined && !session.isCompacting) {
                this.store.update(ref, operation.id, (current) => { current.state = "superseded"; current.detail = "Fresh explicit input superseded the empty completed maintenance while automatic admission remained off"; });
                return false;
            }
            if (unresolved || owner !== undefined || session.isCompacting)
                throw new AutomaticAdmissionRejected("Automatic maintenance admission is disabled; input has not been accepted and must be retained pending reconciliation");
        }
        if (!(["prepared", "compacting", "complete"].includes(operation.state) || this.draining.has(opKey)))
            return false;
        const id = deliveryId ?? randomUUID();
        const previous = operation.inputs.find((input) => input.id === id);
        if (previous !== undefined) {
            if (JSON.stringify([previous.text, previous.kind, previous.images, previous.attachments, previous.potetoGoal]) !== JSON.stringify([text, kind, images, attachments, potetoGoal]))
                throw new AutomaticAdmissionRejected("Accepted maintenance input id changed intent");
            if (previous.state === "queued" && control.durable)
                this.store.update(ref, operation.id, (current) => { current.lastInputGeneration = control.generation; });
            return true;
        }
        if (!control.durable)
            throw new AutomaticAdmissionRejected("Maintenance input cannot be accepted without durable generation state");
        this.store.update(ref, operation.id, (current) => {
            current.inputSequence++;
            current.lastInputGeneration = control.generation;
            current.inputs.push({ id, sequence: current.inputSequence, text, kind, images, attachments, echoUserMessage: echo, generation: control.generation, ...(potetoGoal === undefined ? {} : { potetoGoal }), state: "queued" });
            if (current.state === "complete")
                current.state = "superseded";
        });
        this.host.publish(session);
        return true;
    }
    reconcile(session, id) {
        const operation = this.status(session, id);
        if (operation.inputs.some((input) => input.state === "queued") && !this.controls.snapshot(identity(session)).allowed)
            throw new AutomaticAdmissionRejected("Automatic maintenance admission is disabled; accepted input is retained pending explicit reconciliation or stop/cancel");
        if ((operation.state === "complete" || operation.state === "superseded") && operation.inputs.some((input) => input.state === "queued"))
            this.background(session, this.drain(session, id));
        return this.required(identity(session), id);
    }
    resume(session, request) {
        if (!record(request) || typeof request["text"] !== "string" || request["text"].trim() === "" || typeof request["deliveryId"] !== "string")
            throw new AutomaticAdmissionRejected("RESUME requires exact text and delivery identity");
        const id = operationId(request["id"]);
        const potetoGoal = request["potetoGoal"];
        if (potetoGoal !== undefined && typeof potetoGoal !== "string")
            throw new AutomaticAdmissionRejected("RESUME poteto invocation requires its exact goal string");
        const ref = identity(session);
        const operation = this.status(session, id);
        const automatic = parseAutomaticAdmission(request["automaticAdmission"]);
        if (automatic?.kind !== "resume")
            throw new AutomaticAdmissionRejected("RESUME requires its saved automatic generation");
        if (operation.resume !== undefined) {
            if (operation.resume.deliveryId !== request["deliveryId"] || operation.resume.text !== request["text"] || operation.resume.generation !== automatic.generation || operation.resume.inputSequence !== request["inputSequence"] || operation.compactionEntryId !== request["compactionEntryId"] || operation.resume.potetoGoal !== potetoGoal)
                throw new AutomaticAdmissionRejected("RESUME identity changed intent");
            return operation;
        }
        this.controls.assertCurrent(ref, automatic);
        if (!this.host.current(session) || this.host.busy(session) || this.host.humanInputPending(session) || operation.state !== "complete" || operation.compactionEntryId === undefined || operation.compactionEntryId !== request["compactionEntryId"] || request["inputSequence"] !== operation.inputSequence || operation.inputSequence !== 0 || automatic.generation !== operation.generation || !transparentSuffix(session, operation) || !budgetMatches(session, operation) || !Number.isSafeInteger(operation.tokensAfter) || operation.tokensAfter >= operation.targetTokens || contextTokens(session) >= operation.targetTokens)
            throw new AutomaticAdmissionRejected("Maintenance RESUME checkpoint, generation, context target or newer input was superseded");
        const evidence = maintenanceEvidence(session.sessionFile, operation);
        if (evidence.compactionSha256 !== operation.compactionSha256)
            throw new AutomaticAdmissionRejected("Persisted compaction evidence changed before RESUME");
        const deliveryId = request["deliveryId"], text = request["text"];
        this.store.update(ref, id, (current) => { current.state = "resuming"; current.resume = { deliveryId, text, generation: automatic.generation, inputSequence: current.inputSequence, ...(typeof potetoGoal === "string" ? { potetoGoal } : {}), state: "sending" }; });
        const opKey = key(ref, id);
        this.resuming.add(opKey);
        liveOwners.add(opKey);
        this.controls.assertCurrent(ref, automatic);
        let nativeText;
        this.background(session, this.host.send(session, text, [], true, typeof potetoGoal === "string" ? potetoGoal : undefined, value => { nativeText = value; }).then(() => {
            const current = this.required(ref, id);
            const control = this.controls.snapshot(ref);
            const observation = nativeText !== undefined && this.host.current(session) && this.resuming.has(opKey) && current.state === "resuming" && current.inputSequence === 0 && control.durable && control.allowed && control.generation === automatic.generation && session.agent.subscribe !== undefined ? completedResumeEvidence(session, current, nativeText) : undefined;
            this.store.update(ref, id, (current) => { if (current.state === "resuming") {
                current.state = "resumed";
                if (current.resume !== undefined) {
                    current.resume.state = "admitted";
                    if (observation !== undefined)
                        current.resume.observation = observation;
                }
            } });
        }, (error) => {
            this.store.update(ref, id, (current) => { current.state = "uncertain"; current.detail = error instanceof Error ? error.message : String(error); if (current.resume !== undefined)
                current.resume.state = "uncertain"; });
        }).finally(() => { this.resuming.delete(opKey); liveOwners.delete(opKey); this.host.publish(session); }));
        return this.required(ref, id);
    }
    cancel(ref) {
        const operation = this.store.current(ref);
        if (operation === undefined || operation.state === "resumed")
            return;
        this.store.update(ref, operation.id, (current) => {
            current.state = "superseded";
            current.cancelledByStop = true;
            for (const input of current.inputs) {
                if (input.state === "queued")
                    input.state = "cancelled";
                else if (input.state === "sending")
                    input.state = "uncertain";
            }
            if (current.resume?.state === "sending")
                current.resume.state = "uncertain";
            current.detail = "Explicit stop/cancel superseded maintenance; prior accepted input remains recorded";
        });
    }
    assertEntryMutationAllowed(session) {
        for (const owner of this.compacting.values()) {
            if (owner === session)
                throw new AutomaticAdmissionRejected("The current maintenance compaction reserves model, thinking and shell mutations; retain the request for retry");
        }
    }
    abortOwnedCompaction(session) {
        const ref = identity(session);
        const operation = this.store.current(ref);
        if (operation !== undefined && this.compacting.get(key(ref, operation.id)) === session)
            session.abortCompaction?.();
    }
    pending(session) {
        return this.store.pending(identity(session));
    }
    blocksAutomatic(session) {
        const saved = this.store.current(identity(session));
        const operation = saved === undefined ? undefined : this.status(session, saved.id);
        return operation !== undefined && (liveOwners.has(key(identity(session), operation.id)) || this.compacting.has(key(identity(session), operation.id)) || this.draining.has(key(identity(session), operation.id)) || this.resuming.has(key(identity(session), operation.id)) || operation.state !== "resumed" && operation.state !== "superseded" || operation.inputs.some((input) => input.state === "queued" || input.state === "sending" || input.state === "uncertain"));
    }
    background(session, operation) {
        void operation.catch(async (error) => {
            let detail = error instanceof Error ? error.message : String(error);
            if (this.host.current(session)) {
                try {
                    if (this.controls.snapshot(identity(session)).allowed)
                        await this.controls.setAllowed(identity(session), false);
                }
                catch (failure) {
                    detail += `; automatic admission durability unconfirmed: ${failure instanceof Error ? failure.message : String(failure)}`;
                }
            }
            this.host.failure(session, detail);
        });
    }
    required(ref, id) {
        const operation = this.store.get(ref, operationId(id));
        if (operation === undefined)
            throw new AutomaticAdmissionRejected("Maintenance operation is unavailable");
        return operation;
    }
    async compact(session, id) {
        const ref = identity(session), opKey = key(ref, id);
        try {
            const operation = this.required(ref, id);
            if (!budgetMatches(session, operation)) throw new Error("Maintenance same-model context capacity changed");
            await session.compact(operation.instructions, { targetTokens: operation.targetTokens });
            const tokensAfter = contextTokens(session);
            if (!budgetMatches(session, operation) || !Number.isSafeInteger(tokensAfter) || tokensAfter < 0 || tokensAfter >= operation.targetTokens)
                throw new Error("Native compaction exceeds the same-model safe context capacity");
            const evidence = maintenanceEvidence(session.sessionFile, operation);
            if (!this.host.current(session) || evidence.compactionEntryId === undefined)
                throw new Error("Completed native compaction evidence or owning runtime is unavailable");
            this.store.update(ref, id, (current) => { Object.assign(current, evidence, { tokensAfter }); if (current.state !== "superseded")
                current.state = current.inputs.length === 0 ? "complete" : "superseded"; });
        }
        catch (error) {
            let barrierFailure = "";
            if (this.host.current(session)) {
                try {
                    if (this.required(ref, id).state !== "superseded" && this.controls.snapshot(ref).allowed)
                        await this.controls.setAllowed(ref, false);
                }
                catch (failure) {
                    barrierFailure = `; durable stop barrier unconfirmed: ${failure instanceof Error ? failure.message : String(failure)}`;
                }
            }
            this.store.update(ref, id, (current) => { if (current.state !== "superseded")
                current.state = this.host.current(session) ? "failed" : "uncertain"; current.detail = `${error instanceof Error ? error.message : String(error)}${barrierFailure}`; });
        }
        finally {
            this.compacting.delete(opKey);
            liveOwners.delete(opKey);
            this.host.end(session);
            this.host.publish(session);
        }
        const operation = this.required(ref, id);
        if (operation.state === "superseded")
            await this.drain(session, id);
    }
    async drain(session, id) {
        const ref = identity(session), opKey = key(ref, id);
        if (this.draining.has(opKey))
            return;
        this.draining.add(opKey);
        liveOwners.add(opKey);
        try {
            while (this.host.current(session)) {
                const operation = this.required(ref, id);
                if (!["complete", "superseded"].includes(operation.state))
                    return;
                const input = operation.inputs.find((item) => item.state !== "admitted" && item.state !== "cancelled");
                if (input === undefined)
                    return;
                if (input.state !== "queued") {
                    this.store.update(ref, id, (current) => { current.state = "uncertain"; current.detail = "An earlier input admission is uncertain; later accepted input must not pass it"; });
                    return;
                }
                const control = this.controls.snapshot(ref);
                if (operation.cancelledByStop === true || !control.durable || !control.allowed || control.generation !== operation.lastInputGeneration)
                    return;
                if (session.isStreaming || session.isCompacting || session.isBashRunning || this.host.humanInputPending(session))
                    return;
                this.store.update(ref, id, (current) => { current.state = "superseded"; const selected = current.inputs[input.sequence - 1]; if (selected !== undefined)
                    selected.state = "sending"; });
                try {
                    await this.host.send(session, input.text, input.images, input.echoUserMessage, input.potetoGoal);
                    this.store.update(ref, id, (current) => { const selected = current.inputs[input.sequence - 1]; if (selected !== undefined)
                        selected.state = "admitted"; });
                }
                catch (error) {
                    this.store.update(ref, id, (current) => { current.state = "uncertain"; current.detail = error instanceof Error ? error.message : String(error); const selected = current.inputs[input.sequence - 1]; if (selected !== undefined)
                        selected.state = "uncertain"; });
                    return;
                }
            }
        }
        finally {
            this.draining.delete(opKey);
            liveOwners.delete(opKey);
            this.host.publish(session);
        }
    }
}
//# sourceMappingURL=sessionMaintenanceController.js.map