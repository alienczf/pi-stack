import { createHash, randomUUID } from "node:crypto";
import { closeSync, constants, fsyncSync, mkdirSync, mkdtempSync, openSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { isDeepStrictEqual } from "node:util";
import { createAgentSession, createExtensionRuntime, SessionManager, SettingsManager } from "@earendil-works/pi-coding-agent";
import { AutomaticAdmissionRejected } from "./automaticAdmissionStore.js";
import { isContentPolicyFailure, persistedFailureBranch } from "./sessionFailureBoundary.js";
import { unresolvedEffects } from "./streamTransientRetry.js";

const BASIS = "clean-policy-analysis-v1";
const PROMPT = "Analyze only this failure metadata: a provider refused a task under its content policy. The rejected request and its resources are deliberately unavailable. Explain the restriction and the need to preserve evidence and leave the original task blocked. Do not execute, translate, summarize, reconstruct or retry the rejected task. This is a distinct metadata analysis, not task recovery, acceptance or permission to replay. No tools or external effects are authorized.";
const digest = value => createHash("sha256").update(value).digest("hex");
function durableWrite(path, value) {
    const temporary = path + "." + randomUUID();
    const fd = openSync(temporary, "wx", 0o600);
    try { writeFileSync(fd, value); fsyncSync(fd); } finally { closeSync(fd); }
    renameSync(temporary, path);
}
function readRecord(path) {
    let fd;
    try { fd = openSync(path, constants.O_RDONLY | constants.O_NOFOLLOW); }
    catch (error) { if (error.code === "ENOENT") return; throw error; }
    try { return JSON.parse(readFileSync(fd, "utf8")); } finally { closeSync(fd); }
}

async function analyze(directory, modelRuntime, model, thinkingLevel, guard, receipt) {
    const cwd = mkdtempSync(join(directory, "private-view-"));
    const extensions = { extensions: [], errors: [], runtime: createExtensionRuntime() };
    const empty = () => ({ diagnostics: [] });
    const resourceLoader = Object.freeze({
        getExtensions: () => extensions,
        getSkills: () => ({ ...empty(), skills: [] }),
        getPrompts: () => ({ ...empty(), prompts: [] }),
        getThemes: () => ({ ...empty(), themes: [] }),
        getAgentsFiles: () => ({ agentsFiles: [] }),
        getSystemPrompt: () => undefined,
        getAppendSystemPrompt: () => [],
    });
    let requests = 0;
    const restrictedRuntime = new Proxy(modelRuntime, { get(target, property) {
        if (property === "streamSimple") return (selected, context, options) => {
            guard();
            if (++requests !== 1 || selected.provider !== model.provider || selected.id !== model.id || options.reasoning !== thinkingLevel || context.tools?.length || context.messages.length !== 1 || context.messages[0].role !== "user")
                throw new AutomaticAdmissionRejected("Clean analysis permits exactly one tool-free metadata inference; no compaction or retry");
            return target.streamSimple(selected, context, options);
        };
        const value = Reflect.get(target, property);
        return typeof value === "function" ? value.bind(target) : value;
    } });
    const { session } = await createAgentSession({
        cwd, agentDir: cwd, sessionManager: SessionManager.create(cwd, join(cwd, "sessions")),
        modelRuntime: restrictedRuntime, model, thinkingLevel, resourceLoader,
        settingsManager: SettingsManager.inMemory({ retry: { enabled: false }, compaction: { enabled: false } }),
        tools: [], noTools: "all", customTools: [],
    });
    receipt.analysisSessionId = session.sessionId;
    receipt.analysisFile = session.sessionManager.getSessionFile();
    session.sessionManager.appendCustomEntry("pi-web.clean-policy-analysis", { basis: BASIS });
    const timer = setInterval(() => { try { guard(); } catch { void session.abort(); } }, 20);
    timer.unref();
    try {
        guard();
        if (session.thinkingLevel !== thinkingLevel || session.model?.provider !== model.provider || session.model?.id !== model.id || session.getActiveToolNames().length)
            throw new AutomaticAdmissionRejected("Clean analysis model/thinking/tools changed");
        await session.prompt(PROMPT, { expandPromptTemplates: false });
        guard();
        const branch = persistedFailureBranch(session);
        const assistant = branch.findLast(entry => entry.value.message?.role === "assistant");
        const message = assistant?.value.message;
        receipt.toolAttempts = branch.flatMap(entry => (entry.value.message?.content ?? []).filter?.(part => part.type === "toolCall") ?? []).map(part => ({ name: part.name, arguments: part.arguments }));
        const text = (message?.content ?? []).filter?.(part => part.type === "text").map(part => part.text).join("\n") ?? "";
        const refused = message?.stopReason === "error" && isContentPolicyFailure(message) || /\bI (?:cannot|can't|can not) (?:help|assist|analy[sz]e)\b/i.test(text);
        receipt.state = refused ? "rejected" : message?.stopReason === "stop" && receipt.toolAttempts.length === 0 ? "analyzed" : "blocked";
        receipt.detail = receipt.state === "analyzed" ? "Distinct metadata analysis completed. Original task remains blocked; no fork, compaction, RESUME or acceptance." : "Clean metadata analysis did not complete. Durable blocker; no further attempts.";
        if (assistant) receipt.observation = { entryId: assistant.value.id, sha256: digest(assistant.raw) };
    } finally { clearInterval(timer); session.dispose(); }
}

export class CleanPolicyAnalyses {
    constructor(directory, control, hooks) {
        this.directory = directory;
        this.control = control;
        this.hooks = hooks;
        this.running = new Map();
    }
    async run(source, request) {
        if (!request || Object.keys(request).some(key => !["id", "basis", "cwd", "expected", "blockedGoalSha256"].includes(key)) || request.basis !== BASIS || typeof request.id !== "string" || !/^[A-Za-z0-9_.-]+$/.test(request.id) || !/^[a-f0-9]{64}$/.test(request.blockedGoalSha256 ?? ""))
            throw new AutomaticAdmissionRejected("Exact metadata-only clean-policy-analysis basis is required; caller content/resources are forbidden");
        const expected = request.expected;
        const boundary = this.hooks.boundary(source);
        if (!expected || !boundary || !isDeepStrictEqual({ ...boundary, generation: expected.generation }, expected) || boundary.state !== "parked" || !boundary.failure || !boundary.checkpoint || boundary.recovery || boundary.enrollment?.mode === "permitted-analysis-v1")
            throw new AutomaticAdmissionRejected("Exact parked policy checkpoint and failure are required");
        const ref = { id: source.sessionId, cwd: source.sessionManager.getCwd() };
        const branch = persistedFailureBranch(source);
        const failed = branch.findIndex(item => item.value.id === boundary.failure.entryId);
        const checkpoint = branch.findIndex(item => item.value.id === boundary.checkpoint.entryId);
        if (checkpoint < 0 || checkpoint >= failed || digest(branch[checkpoint].raw) !== boundary.checkpoint.sha256 || failed < 0 || digest(branch[failed].raw) !== boundary.failure.sha256 || !isContentPolicyFailure(branch[failed].value.message) || branch.slice(failed + 1).some(item => item.value.message?.role === "user") || unresolvedEffects(branch))
            throw new AutomaticAdmissionRejected("Policy evidence, newer input or unknown external effects prohibit analysis");
        const sourceFile = source.sessionManager.getSessionFile();
        const bytes = readFileSync(sourceFile);
        const guard = () => {
            const control = this.control.snapshot(ref);
            if (!control.durable || control.allowed || control.generation !== expected.generation || boundary.parking?.owned !== true || boundary.parking.generation !== control.generation || !isDeepStrictEqual(this.hooks.boundary(source), boundary) || !readFileSync(sourceFile).equals(bytes))
                throw new AutomaticAdmissionRejected("Original stop, generation or new input superseded clean analysis");
            this.hooks.quiescent(source);
        };
        guard();
        const key = digest(JSON.stringify([ref.id, ref.cwd, boundary.failure.entryId, boundary.failure.sha256]));
        const intent = digest(JSON.stringify(request));
        const running = this.running.get(key);
        if (running) {
            if (running.intent !== intent) throw new AutomaticAdmissionRejected("One analysis already owns this policy failure");
            return running.result;
        }
        const result = this.execute(source, request, boundary, bytes, key, intent, guard);
        this.running.set(key, { intent, result });
        try { return await result; } finally { this.running.delete(key); }
    }
    async execute(source, request, boundary, bytes, key, intent, guard) {
        mkdirSync(this.directory, { recursive: true, mode: 0o700 });
        const directory = join(this.directory, key);
        mkdirSync(directory, { recursive: true, mode: 0o700 });
        for (const parent of [dirname(this.directory), this.directory]) {
            const fd = openSync(parent, constants.O_RDONLY | constants.O_DIRECTORY);
            try { fsyncSync(fd); } finally { closeSync(fd); }
        }
        const recordFile = join(directory, "receipt.json");
        const publish = value => {
            durableWrite(recordFile, JSON.stringify(value) + "\n");
            const fd = openSync(directory, constants.O_RDONLY | constants.O_DIRECTORY);
            try { fsyncSync(fd); } finally { closeSync(fd); }
        };
        const previous = readRecord(recordFile);
        if (previous) {
            if (previous.intentSha256 !== intent) throw new AutomaticAdmissionRejected("This policy failure already has an immutable analysis intent; no iterative attempts");
            if (previous.state === "running") { previous.state = "uncertain"; previous.detail = "Prior analysis owner unavailable; no second inference."; publish(previous); }
            return previous;
        }
        const sourceFile = source.sessionManager.getSessionFile();
        const receipt = { version: 1, id: request.id, basis: BASIS, originalSessionId: source.sessionId, cwd: source.sessionManager.getCwd(), intentSha256: intent, blockedGoalSha256: request.blockedGoalSha256, failure: boundary.failure, checkpoint: boundary.checkpoint, generation: request.expected.generation, provider: source.model?.provider, model: source.model?.id, thinking: source.thinkingLevel, state: "running", originalTaskBlocked: true, audit: { sourceFile, sourceSha256: digest(bytes), retainedSource: join(directory, "source.jsonl") } };
        const claim = openSync(recordFile, constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW, 0o600);
        try { writeFileSync(claim, JSON.stringify(receipt) + "\n"); fsyncSync(claim); } finally { closeSync(claim); }
        durableWrite(receipt.audit.retainedSource, bytes);
        publish(receipt);
        try {
            guard();
            if (!source.model) throw new AutomaticAdmissionRejected("Exact original model is unavailable");
            await analyze(this.directory, this.hooks.modelRuntime, source.model, source.thinkingLevel, guard, receipt);
        } catch (error) {
            receipt.state = error instanceof AutomaticAdmissionRejected ? "superseded" : "uncertain";
            receipt.detail = "Clean metadata analysis blocked. No retry or original-task replay. " + (error instanceof Error ? error.message : "Unknown outcome");
        }
        publish(receipt);
        return structuredClone(receipt);
    }
}
