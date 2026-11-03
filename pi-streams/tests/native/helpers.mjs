import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

export const root = resolve(process.env.PI_STACK_NATIVE_TEST_ROOT ?? '');
assert(process.env.PI_STACK_NATIVE_TEST_ROOT, 'an explicit disposable native root is required');
assert(root.includes('/.harness-heal/'), 'native tests only accept an owned .harness-heal fixture');
export const native = path => import(pathToFileURL(join(root, path)).href);
const { AgentSession } = await native('node_modules/@earendil-works/pi-coding-agent/dist/core/agent-session.js');
const { SessionManager } = await native('node_modules/@earendil-works/pi-coding-agent/dist/core/session-manager.js');
const { SettingsManager } = await native('node_modules/@earendil-works/pi-coding-agent/dist/core/settings-manager.js');
const { createExtensionRuntime } = await native('node_modules/@earendil-works/pi-coding-agent/dist/core/extensions/loader.js');
const { Agent } = await native('node_modules/@earendil-works/pi-agent-core/dist/agent.js');
const { AutomaticAdmissionStore } = await native('dist/server/sessions/automaticAdmissionStore.js');
const { SessionFailureBoundaries } = await native('dist/server/sessions/sessionFailureBoundary.js');
const { AssistantMessageEventStream } = await native('node_modules/@earendil-works/pi-ai/dist/utils/event-stream.js');

export const model = { provider: 'openai-codex', id: 'gpt-6.1-sol', name: 'Controlled fixture', api: 'openai-codex-responses', baseUrl: 'http://127.0.0.1:9', reasoning: true, input: ['text'], contextWindow: 400000, maxTokens: 4096, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 } };
export const response = (text = 'continued', stopReason = 'stop') => ({ role: 'assistant', content: [{ type: 'text', text }], api: model.api, provider: model.provider, model: model.id, stopReason, timestamp: Date.now(), usage: { input: 100, output: 10, cacheRead: 0, cacheWrite: 0, totalTokens: 110, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } } });
export const errorResponse = text => ({ ...response('', 'error'), content: [], errorMessage: text });
export function provider(result) {
    const stream = new AssistantMessageEventStream();
    queueMicrotask(() => {
        stream.push(result.stopReason === 'error' ? { type: 'error', reason: 'error', error: result } : { type: 'done', reason: result.stopReason, message: result });
        stream.end();
    });
    return stream;
}

export async function fixture(responses = [], tools = {}) {
    const dir = mkdtempSync(join(process.env.TMPDIR, 'native-session-'));
    const manager = SessionManager.create(dir, join(dir, 'sessions'));
    const extensionRuntime = createExtensionRuntime();
    const extensions = { extensions: [], errors: [], runtime: extensionRuntime };
    const loader = { getExtensions: () => extensions, getPrompts: () => ({ prompts: [] }), getSkills: () => ({ skills: [] }), getAgentsFiles: () => ({ agentsFiles: [] }), getSystemPrompt: () => 'Controlled test. No network or shell.', getAppendSystemPrompt: () => [] };
    const calls = [];
    const agent = new Agent({ initialState: { model, thinkingLevel: 'xhigh', tools: Object.values(tools), systemPrompt: 'Controlled test.' }, streamFn: (selected, context, options) => { calls.push({ model: structuredClone(selected), context: { systemPrompt: context.systemPrompt, messages: structuredClone(context.messages) }, options }); assert(responses.length, 'unexpected provider request'); return provider(responses.shift()); } });
    const runtime = { hasConfiguredAuth: () => true, checkAuth: async () => ({ authenticated: true }), isUsingOAuth: () => false, getAuth: async () => ({ auth: {} }), getProviders: () => [], getAll: () => [model] };
    const session = new AgentSession({ agent, sessionManager: manager, settingsManager: SettingsManager.inMemory({ compaction: { enabled: false, keepRecentTokens: 100 }, retry: { enabled: true, maxRetries: 3, baseDelayMs: 2000 } }), resourceLoader: loader, cwd: dir, modelRuntime: runtime, baseToolsOverride: tools });
    const control = new AutomaticAdmissionStore(join(dir, 'controls'));
    await control.initialize({ id: session.sessionId, cwd: dir });
    const boundaries = new SessionFailureBoundaries(control);
    await boundaries.watch(session, { stream: 'fixture', root: dir });
    return { dir, session, manager, calls, control, boundaries, loader, extensions };
}

export async function flush() {
    for (let index = 0; index < 25; index++) await new Promise(resolve => setImmediate(resolve));
}

export function clock() {
    const realSetTimeout = globalThis.setTimeout;
    const realClearTimeout = globalThis.clearTimeout;
    let now = 0, sequence = 0;
    const timers = new Map();
    globalThis.setTimeout = (callback, delay, ...args) => { const key = ++sequence; timers.set(key, { at: now + delay, callback: () => callback(...args), delay }); return key; };
    globalThis.clearTimeout = key => timers.delete(key);
    return { async advance(ms) { now += ms; for (const [key, timer] of [...timers]) if (timer.at <= now) { timers.delete(key); timer.callback(); } await flush(); }, delays: () => [...timers.values()].map(timer => timer.delay), restore() { globalThis.setTimeout = realSetTimeout; globalThis.clearTimeout = realClearTimeout; } };
}
