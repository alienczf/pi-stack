import { createHash } from "node:crypto";
import { isRetryableAssistantError, isContextOverflow } from "@earendil-works/pi-ai/compat";
import { AutomaticAdmissionRejected } from "./automaticAdmissionStore.js";

export const RETRY_TYPE = "pi-web.stream-retry";
const hash = raw => createHash("sha256").update(raw).digest("hex");
const equal = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const evidence = item => ({ entryId: item.value.id, sha256: hash(item.raw) });
const usage = message => message.provider === "openai-codex" && /usage_limit_reached|usage_not_included|rate_limit_exceeded|chatgpt usage limit|codex usage limit/i.test(message.errorMessage ?? "");

export function retryDispositions(branch, sid, cwd) {
    const anchor = branch.filter(item => item.value.customType === "pi-web.stream-failure" && item.value.data?.sessionId === sid).at(-1)?.value.data;
    const parents = new Map();
    for (const { value } of branch) {
        const data = value.data;
        if (value.customType !== "pi-web.stream-failure" || data?.version !== 1 || data.cwd !== cwd || data.root !== anchor?.root || data.stream !== anchor?.stream || !["recovering", "watching"].includes(data.state) || typeof data.recovery?.originalSessionId !== "string" || typeof data.recovery.id !== "string") continue;
        const previous = parents.get(data.sessionId);
        if (previous !== undefined && previous !== data.recovery.originalSessionId)
            throw new AutomaticAdmissionRejected("Retry lineage changed its original session binding");
        parents.set(data.sessionId, data.recovery.originalSessionId);
    }
    const lineage = new Set([sid]);
    let current = sid;
    while (parents.has(current)) {
        current = parents.get(current);
        if (lineage.has(current)) throw new AutomaticAdmissionRejected("Retry lineage is cyclic");
        lineage.add(current);
    }
    const entries = new Map(branch.map((item, index) => [item.value.id, { ...item, index }]));
    const result = new Map();
    for (const { value } of branch) {
        if (value.customType !== RETRY_TYPE || !lineage.has(value.data?.sessionId)) continue;
        const data = value.data;
        const failed = entries.get(data.failure?.entryId);
        if (data.version !== 1 || data.cwd !== cwd || !failed || failed.index >= entries.get(value.id).index || hash(failed.raw) !== data.failure.sha256 || failed.value.message?.stopReason !== "error" || data.identity?.provider !== failed.value.message.provider || data.identity?.model !== failed.value.message.model || typeof data.identity?.thinking !== "string" || typeof data.identity?.generation !== "string" || !Number.isSafeInteger(data.attempt) || data.attempt < 1 || data.delayMs !== 5000 || !["pending", "resolved", "terminal", "cancelled", "uncertain", "superseded"].includes(data.state))
            throw new AutomaticAdmissionRejected("Native retry disposition has changed entry/hash or identity");
        const prior = result.get(data.failure.entryId);
        if (prior && (!equal(prior.identity, data.identity) || prior.attempt !== data.attempt || prior.state !== "pending" && !(prior.state === "cancelled" && prior.reason === "new-input" && data.state === "superseded") && !equal(prior, data)))
            throw new AutomaticAdmissionRejected("Native retry disposition changed immutable attempt or terminal settlement");
        if (data.state === "superseded") {
            const input = entries.get(data.input?.entryId);
            if (!input || input.index <= failed.index || input.index >= entries.get(value.id).index || hash(input.raw) !== data.input.sha256 || input.value.message?.role !== "user")
                throw new AutomaticAdmissionRejected("Superseded retry has no exact newer admitted input");
        }
        if (data.state === "resolved") {
            const completion = entries.get(data.completion?.entryId);
            if (!completion || completion.index <= failed.index || completion.index >= entries.get(value.id).index || hash(completion.raw) !== data.completion.sha256 || completion.value.message?.role !== "assistant" || completion.value.message.provider !== data.identity.provider || completion.value.message.model !== data.identity.model || completion.value.message.stopReason === "aborted" || branch.slice(failed.index + 1, completion.index).some(item => item.value.message?.role === "user" || item.value.type === "model_change" || item.value.type === "thinking_level_change"))
                throw new AutomaticAdmissionRejected("Native retry has no exact same-identity ordered completion");
        }
        result.set(data.failure.entryId, data);
    }
    return result;
}

function shellSubmission(command) {
    if (typeof command !== "string") return true;
    const operators = ["&>>", "&>", "&&", "||", "|&", ">>", "<>", ">|", ">&", "<&", ">", "<", ";", "|", "&", "\n"];
    const redirects = new Set(["&>>", "&>", ">>", "<>", ">|", ">&", "<&", ">", "<"]);
    const opaqueWords = new Set(["sbatch", "qsub", "nohup", "setsid", "disown"]);
    command = command.replace(/<<-?\s*(['"]?)(\w+)\1([^\n]*)\n([\s\S]*?)\n\t*\2(?=\n|$)/g, (all, quote, end, tail, body) => tail + "\n" + (/(?:^|[;|\s])(?:bash|sh|dash|ksh|zsh)\s/.test(command.slice(0, command.indexOf(all))) ? body + "\n" : ""));
    const tokens = [];
    let word, index = 0;
    while (index < command.length) {
        let char = command[index];
        if (char === "\\") {
            if (++index === command.length) break;
            if (command[index] !== "\n") word = (word ?? "") + command[index];
            index++;
            continue;
        }
        if (char === "'" || char === '"') {
            const quote = char;
            word ??= "";
            index++;
            while (index < command.length && command[index] !== quote) {
                char = command[index];
                if (quote === '"' && char === "$" && command[index + 1] === "(") {
                    const end = command.indexOf(")", index + 2);
                    if (end >= 0 && shellSubmission(command.slice(index + 2, end))) return true;
                }
                if (quote === '"' && char === "`") {
                    const end = command.indexOf("`", index + 1);
                    if (end >= 0 && shellSubmission(command.slice(index + 1, end))) return true;
                }
                if (quote === '"' && char === "\\" && index + 1 < command.length && '$`"\\\n'.includes(command[index + 1])) {
                    char = command[++index];
                    if (char === "\n") { index++; continue; }
                }
                word += char;
                index++;
            }
            if (index === command.length) break;
            index++;
            continue;
        }
        if (char === "#" && word === undefined) {
            while (index < command.length && command[index] !== "\n") index++;
            continue;
        }
        if ("(){}[]`".includes(char)) {
            if (word !== undefined) { tokens.push(["word", word]); word = undefined; }
            tokens.push(["operator", char]);
            index++;
            continue;
        }
        const operator = operators.find(value => command.startsWith(value, index));
        if (" \t".includes(char) || operator !== undefined) {
            if (word !== undefined) { tokens.push(["word", word]); word = undefined; }
            if (operator !== undefined) tokens.push([redirects.has(operator) ? "redirect" : "operator", operator]);
            index += operator?.length ?? 1;
            continue;
        }
        word = (word ?? "") + char;
        index++;
    }
    if (word !== undefined) tokens.push(["word", word]);
    let atCommand = true;
    for (let index = 0; index < tokens.length; index++) {
        const [kind, word] = tokens[index];
        if (kind === "operator") {
            if (word === "&") return true;
            if ([";", "|", "|&", "&&", "||", "\n", "(", "{", "`"].includes(word)) atCommand = true;
            continue;
        }
        if (kind !== "word" || !atCommand) continue;
        const text = word.split("/").at(-1);
        if (/^[A-Za-z_][A-Za-z0-9_]*=/.test(word) || word.startsWith("-") || ["env", "command", "exec", "sudo", "time", "builtin"].includes(text)) continue;
        atCommand = false;
        if (opaqueWords.has(text)) return true;
        const end = tokens.findIndex(([kind], at) => at > index && kind === "operator");
        const rest = tokens.slice(index + 1, end < 0 ? undefined : end);
        if (["eval", "bash", "sh", "dash", "ksh", "zsh"].includes(text))
            for (const [kind, script] of rest) if (kind === "word" && /[\s;&]/.test(script) && shellSubmission(script)) return true;
        if (text === "tmux" && rest.some(([, value]) => /^(?:-.*d.*|detach|detach-client)$/.test(value))) return true;
        if (text === "screen" && rest.some(([, value]) => /^-.*[dD].*$/.test(value))) return true;
    }
    return false;
}

export function effectWindow(branch, boundary) {
    if (!boundary?.checkpoint) return branch;
    const checkpoint = boundary.checkpoint;
    const at = branch.findIndex(item => item.value.id === checkpoint.entryId);
    const receipt = branch.findIndex(item => item.value.customType === "pi-web.stream-failure" && equal(item.value.data, boundary));
    const retries = retryDispositions(branch, boundary.sessionId, boundary.cwd);
    const prefix = branch.slice(0, at + 1);
    const terminal = prefix.at(-1)?.value.message;
    if (at < 0 || receipt <= at || hash(branch[at].raw) !== checkpoint.sha256 || !["assistant", "toolResult"].includes(terminal?.role) || terminal.role === "assistant" && terminal.stopReason !== "stop" || terminal.isError || prefix.some(item => item.value.message?.stopReason === "error" && !["resolved", "superseded"].includes(retries.get(item.value.id)?.state)))
        throw new AutomaticAdmissionRejected("Effects checkpoint is not the verified successful native boundary/entry/hash/branch");
    if (boundary.failure) {
        const failed = branch.findIndex(item => item.value.id === boundary.failure.entryId);
        if (failed <= at || hash(branch[failed].raw) !== boundary.failure.sha256)
            throw new AutomaticAdmissionRejected("Effects checkpoint changed its exact failure binding");
    }
    return branch.slice(at + 1);
}

export function unresolvedEffects(branch, boundary) {
    branch = effectWindow(branch, boundary);
    const calls = new Set(), jobs = new Set();
    for (const { value } of branch) {
        const message = value.message;
        if (!message) continue;
        if (message.role === "assistant" && !["error", "aborted"].includes(message.stopReason))
            for (const part of message.content ?? []) if (part.type === "toolCall") {
                calls.add(part.id);
                if (part.name === "bash" && shellSubmission(part.arguments?.command)) jobs.add("unclassified-shell-submission:" + part.id);
            }
        if (message.role === "toolResult") {
            calls.delete(message.toolCallId);
            const details = message.details;
            const id = details?.jobId ?? details?.job_id ?? details?.externalJobId;
            if (typeof id === "string" && id) {
                jobs.delete("unclassified-shell-submission:" + message.toolCallId);
                if (["completed", "succeeded", "failed", "cancelled"].includes(details.status)) jobs.delete(id);
                else jobs.add(id);
            }
        }
    }
    return calls.size > 0 || jobs.size > 0;
}

export class StreamTransientRetry {
    constructor(session, control, branch, watching, cancelled, boundary = () => undefined) {
        this.session = session;
        this.control = control;
        this.branch = branch;
        this.watching = watching;
        this.cancelled = cancelled;
        this.boundary = boundary;
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
            return !this.session.pendingMessageCount && !unresolvedEffects(this.branch(this.session), this.boundary());
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
        if (!this.watching()) return;
        const branch = this.branch(this.session);
        if (message.role === "user") {
            const input = branch.find(item => item.value.id === entryId);
            for (const data of retryDispositions(branch, this.session.sessionId, this.session.sessionManager.getCwd()).values())
                if (data.state === "cancelled" && data.reason === "new-input") this.save({ ...data, state: "superseded", input: evidence(input) });
            return;
        }
        if (message.role !== "assistant") return;
        const persisted =  this.branch(this.session);
        const item = persisted.find(item => item.value.id === entryId);
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
    async yieldToInput() {
        const control = this.control.snapshot({ id: this.session.sessionId, cwd: this.session.sessionManager.getCwd() });
        if (this.active && control.durable && control.allowed && (this.session.pendingMessageCount || control.generation !== this.active.identity.generation)) {
            this.save({ ...this.active, state: "cancelled", reason: "new-input", detail: "Newer accepted input owns continuation; failed inference is not replayed" });
            return true;
        }
        return false;
    }
    async cancel(detail) {
        if (await this.yieldToInput()) return;
        if (this.active) {
            this.save({ ...this.active, state: "cancelled", detail });
            await this.cancelled();
        }
    }
    assertAttempt() {
        const settings = this.session.settingsManager.getRetrySettings();
        if (!this.active || !settings.enabled || this.active.attempt > settings.maxRetries || !equal(this.identity(), this.active.identity) || this.session.pendingMessageCount || unresolvedEffects(this.branch(this.session), this.boundary()))
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
