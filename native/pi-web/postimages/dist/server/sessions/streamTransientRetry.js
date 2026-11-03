import { createHash } from "node:crypto";
import { isRetryableAssistantError, isContextOverflow } from "@earendil-works/pi-ai/compat";
import { AutomaticAdmissionRejected } from "./automaticAdmissionStore.js";

export const RETRY_TYPE = "pi-web.stream-retry";
const hash = raw => createHash("sha256").update(raw).digest("hex");
const equal = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const evidence = item => ({ entryId: item.value.id, sha256: hash(item.raw) });
const usage = message => message.provider === "openai-codex" && /usage_limit_reached|usage_not_included|rate_limit_exceeded|chatgpt usage limit|codex usage limit/i.test(message.errorMessage ?? "");

export function retryDispositions(branch, sid, cwd) {
    const entries = new Map(branch.map((item, index) => [item.value.id, { ...item, index }]));
    const result = new Map();
    for (const { value } of branch) {
        if (value.customType !== RETRY_TYPE || value.data?.sessionId !== sid) continue;
        const data = value.data;
        const failed = entries.get(data.failure?.entryId);
        if (data.version !== 1 || data.cwd !== cwd || !failed || failed.index >= entries.get(value.id).index || hash(failed.raw) !== data.failure.sha256 || failed.value.message?.stopReason !== "error" || data.identity?.provider !== failed.value.message.provider || data.identity?.model !== failed.value.message.model || typeof data.identity?.thinking !== "string" || typeof data.identity?.generation !== "string" || !Number.isSafeInteger(data.attempt) || data.attempt < 1 || data.delayMs !== 5000 || !["pending", "resolved", "terminal", "cancelled", "uncertain"].includes(data.state))
            throw new AutomaticAdmissionRejected("Native retry disposition has changed entry/hash or identity");
        const prior = result.get(data.failure.entryId);
        if (prior && (!equal(prior.identity, data.identity) || prior.attempt !== data.attempt || prior.state !== "pending" && !equal(prior, data)))
            throw new AutomaticAdmissionRejected("Native retry disposition changed immutable attempt or terminal settlement");
        if (data.state === "resolved") {
            const completion = entries.get(data.completion?.entryId);
            if (!completion || completion.index <= failed.index || completion.index >= entries.get(value.id).index || hash(completion.raw) !== data.completion.sha256 || completion.value.message?.role !== "assistant" || completion.value.message.provider !== data.identity.provider || completion.value.message.model !== data.identity.model || completion.value.message.stopReason === "aborted" || branch.slice(failed.index + 1, completion.index).some(item => item.value.message?.role === "user" || item.value.type === "model_change" || item.value.type === "thinking_level_change"))
                throw new AutomaticAdmissionRejected("Native retry has no exact same-identity ordered completion");
        }
        result.set(data.failure.entryId, data);
    }
    return result;
}

export function unresolvedEffects(branch) {
    const calls = new Set(), jobs = new Set();
    for (const { value } of branch) {
        const message = value.message;
        if (!message) continue;
        if (message.role === "assistant" && message.stopReason !== "error")
            for (const part of message.content ?? []) if (part.type === "toolCall") {
                calls.add(part.id);
                if (part.name === "bash" && /\b(sbatch|qsub|nohup)\b|(?:^|[^&])&(?:$|[^&])/.test(part.arguments?.command ?? "")) jobs.add("unclassified-shell-submission:" + part.id);
            }
        if (message.role === "toolResult") {
            calls.delete(message.toolCallId);
            const details = message.details;
            const id = details?.jobId ?? details?.job_id ?? details?.externalJobId;
            if (id) {
                if (["completed", "succeeded", "failed", "cancelled"].includes(details.status)) jobs.delete(id);
                else jobs.add(id);
            }
        }
    }
    return calls.size > 0 || jobs.size > 0;
}

export class StreamTransientRetry {
    constructor(session, control, branch, watching, cancelled) {
        this.session = session;
        this.control = control;
        this.branch = branch;
        this.watching = watching;
        this.cancelled = cancelled;
        this.active = undefined;
    }
    get delayMs() { return this.watching() ? 5000 : undefined; }
    identity() {
        const state = this.control.snapshot({ id: this.session.sessionId, cwd: this.session.sessionManager.getCwd() });
        if (!state.durable || !state.allowed) throw new AutomaticAdmissionRejected("Retry receiving admission is stopped or uncertain");
        return { provider: this.session.model?.provider, model: this.session.model?.id, thinking: this.session.thinkingLevel, generation: state.generation };
    }
    eligible(message) {
        if (!this.watching()) return true;
        if (usage(message) || /usage.?limit/i.test(message.errorMessage ?? "") || !isRetryableAssistantError(message) || isContextOverflow(message, this.session.model?.contextWindow ?? 0)) return false;
        try {
            this.identity();
            return !this.session.pendingMessageCount && !unresolvedEffects(this.branch(this.session));
        } catch { return false; }
    }
    save(data) {
        this.session.sessionManager.appendCustomEntry(RETRY_TYPE, structuredClone(data));
        this.branch(this.session);
        this.active = data.state === "pending" ? data : undefined;
    }
    reconcile() {
        for (const data of retryDispositions(this.branch(this.session), this.session.sessionId, this.session.sessionManager.getCwd()).values())
            if (data.state === "pending") this.save({ ...data, state: "uncertain", detail: "The live retry owner was lost; no inference is replayed" });
    }
    async messageEnded(message, entryId) {
        if (!this.watching() || message.role !== "assistant") return;
        const branch = this.branch(this.session);
        const item = branch.find(item => item.value.id === entryId);
        if (!item) throw new AutomaticAdmissionRejected("Retry response is not persisted");
        if (this.active) {
            let unchanged = false;
            try { unchanged = equal(this.identity(), this.active.identity) && !this.session.pendingMessageCount; } catch { /* A stop owns the receiving generation. */ }
            this.save({ ...this.active, state: unchanged && message.stopReason !== "aborted" ? "resolved" : "cancelled", completion: evidence(item) });
        }
        const settings = this.session.settingsManager.getRetrySettings();
        if (message.stopReason === "error" && settings.enabled && this.session._retryAttempt < settings.maxRetries && this.session._isRetryableError(message)) {
            this.save({ version: 1, sessionId: this.session.sessionId, cwd: this.session.sessionManager.getCwd(), failure: evidence(item), identity: this.identity(), attempt: this.session._retryAttempt + 1, delayMs: 5000, state: "pending", phase: "scheduled" });
        } else if (message.stopReason === "error" && !usage(message) && isRetryableAssistantError(message) && this.session._retryAttempt >= settings.maxRetries && this.session._retryAttempt > 0) {
            this.save({ version: 1, sessionId: this.session.sessionId, cwd: this.session.sessionManager.getCwd(), failure: evidence(item), identity: this.identity(), attempt: this.session._retryAttempt, delayMs: 5000, state: "terminal", detail: "The configured native retry count is exhausted" });
        }
    }
    async cancel(detail) {
        if (this.active) {
            this.save({ ...this.active, state: "cancelled", detail });
            await this.cancelled();
        }
    }
    assertAttempt() {
        const settings = this.session.settingsManager.getRetrySettings();
        if (!this.active || !settings.enabled || this.active.attempt > settings.maxRetries || !equal(this.identity(), this.active.identity) || this.session.pendingMessageCount || unresolvedEffects(this.branch(this.session)))
            throw new AutomaticAdmissionRejected("Retry superseded by stop, input, settings or unresolved effects");
    }
    async beforeAttempt() {
        if (!this.watching()) return true;
        try {
            this.assertAttempt();
            this.save({ ...this.active, phase: "attempting" });
            return true;
        } catch (error) { await this.cancel(error.message); return false; }
    }
    assertInference() {
        if (this.active !== undefined) this.assertAttempt();
    }
    owns(data) { return this.active?.failure.entryId === data.failure.entryId && equal(this.active, data); }
}
