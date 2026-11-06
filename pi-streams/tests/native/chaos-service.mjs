import assert from 'node:assert/strict';
import { closeSync, existsSync, fsyncSync, openSync, readFileSync, readdirSync, realpathSync, writeFileSync, writeSync } from 'node:fs';
import { join, resolve, sep } from 'node:path';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import net from 'node:net';

const scratch = realpathSync(process.env.CHAOS_SCRATCH);
const owner = process.env.CHAOS_OWNER;
assert.equal(readFileSync(join(scratch, '.chaos-owner'), 'utf8'), owner);
assert(resolve(process.env.HOME).startsWith(scratch + sep));
const root = realpathSync(process.env.PI_STACK_NATIVE_TEST_ROOT);
assert(root.includes('/.harness-heal/'), 'use an isolated prepared static package');
const connect = net.Socket.prototype.connect;
net.Socket.prototype.connect = function (...args) {
    const target = typeof args[0] === 'object' ? args[0] : { port: args[0], host: args[1] };
    assert(['127.0.0.1', 'localhost', '::1'].includes(target.host), 'external connections are forbidden');
    assert.notEqual(Number(target.port), 8504, 'production port is forbidden');
    return connect.apply(this, args);
};
globalThis.fetch = async () => { throw new Error('Provider/network fetch is forbidden in chaos-service'); };
const native = path => import(pathToFileURL(join(root, path)).href);
const require = createRequire(join(root, 'package.json'));
const Fastify = require('fastify');
const websocket = require('@fastify/websocket');
const { PiSessionService } = await native('dist/server/sessions/piSessionService.js');
const { registerSessionRoutes } = await native('dist/server/sessions/sessionRoutes.js');
const { sessionServiceDependencies } = await native('dist/server/sessiond/sessionServiceDependencies.js');
const { SessionEventHub } = await native('dist/server/realtime/sessionEventHub.js');
const { createPiSessionManagerGateway } = await native('dist/server/sessions/piSessionManagerGateway.js');
const { runStreamsDcrAdvance } = await native('dist/server/sessions/streamsDcrEvents.js');
const { AutomaticAdmissionStore } = await native('dist/server/sessions/automaticAdmissionStore.js');
const { SessionArchiveStore } = await native('dist/server/sessions/sessionArchiveStore.js');
const { SESSIOND_RUNTIME_CAPABILITIES } = await native('dist/shared/capabilities.js');
const { AgentSession } = await native('node_modules/@earendil-works/pi-coding-agent/dist/core/agent-session.js');
const { SettingsManager } = await native('node_modules/@earendil-works/pi-coding-agent/dist/core/settings-manager.js');
const { createExtensionRuntime } = await native('node_modules/@earendil-works/pi-coding-agent/dist/core/extensions/loader.js');
const { estimateTokens } = await native('node_modules/@earendil-works/pi-coding-agent/dist/core/compaction/index.js');
const { Agent } = await native('node_modules/@earendil-works/pi-agent-core/dist/agent.js');
const { AssistantMessageEventStream } = await native('node_modules/@earendil-works/pi-ai/dist/utils/event-stream.js');

const journal = value => {
    const descriptor = openSync(process.env.CHAOS_JOURNAL, 'a');
    try {
        writeSync(descriptor, JSON.stringify({ owner, pid: process.pid, at: new Date().toISOString(), ...value }) + '\n');
        fsyncSync(descriptor);
    } finally { closeSync(descriptor); }
};
const model = { provider: 'openai-codex', id: 'gpt-6.1-sol', name: 'Simulated provider transport', api: 'openai-codex-responses', baseUrl: 'http://127.0.0.1:9', reasoning: true, thinkingLevelMap: { xhigh: 'xhigh' }, input: ['text'], contextWindow: 400000, maxTokens: 4096, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 } };
const plans = new Map();
const owned = new Map();
const calls = [];
const events = [];
const requests = [];
let authenticated = true;
const runtime = { refresh: async () => ({}), getAvailableSnapshot: () => [model], hasConfiguredAuth: () => true, checkAuth: async () => ({ authenticated }), isUsingOAuth: () => false, getAuth: async () => ({ auth: {} }), streamSimple: (selected, context, options) => controlledStream(selected, context, options, options.sessionId, scratch), getProviders: () => [], getAll: () => [model], getAvailable: async () => [model], getModel: (provider, id) => provider === model.provider && id === model.id ? model : undefined, registerProvider: () => {}, unregisterProvider: () => {}, registerNativeProvider: () => {} };
const textOf = message => typeof message?.content === 'string' ? message.content : (message?.content ?? []).filter(p => p.type === 'text').map(p => p.text).join('\n');
const response = (text, error, tokens = 100) => ({ role: 'assistant', content: error ? [] : [{ type: 'text', text }], api: model.api, provider: model.provider, model: model.id, stopReason: error ? 'error' : 'stop', ...(error ? { errorMessage: error } : {}), timestamp: Date.now(), usage: { input: tokens, output: 10, cacheRead: 0, cacheWrite: 0, totalTokens: tokens + 10, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } } });
const execute = promisify(execFile);
function controlledStream(selected, context, options, sid, cwd) {
    assert.equal(selected.provider, model.provider);
    assert.equal(selected.id, model.id);
    const title = context.systemPrompt?.startsWith('Generate a concise title');
    const summary = context.systemPrompt?.startsWith('You are a context summarization assistant');
    const call = { summary, session: sid, at: Date.now(), monotonicMs: performance.now(), provider: selected.provider, model: selected.id, reasoning: options.reasoning, title, systemPrompt: context.systemPrompt, messages: structuredClone(context.messages), tools: structuredClone(context.tools) };
    calls.push(call);
    const stream = new AssistantMessageEventStream();
    void (async () => {
        const plan = title || summary ? {} : (plans.get(sid)?.shift() ?? {});
        const last = textOf(context.messages.findLast(m => m.role === 'user'));
        let text = plan.text ?? (summary ? '## Goal\nContinue only the current permitted goal in STATE.\n## Progress\nHistorical fixture exchanges were checked.\n## Next steps\nRead STATE and retain the bounded role.' : owned.has(sid) ? 'Permitted fixture work completed. The authorized overall outcome remains unfinished.' : 'The content-policy refusal applies to the original task. Only failure metadata was analyzed. Preserve evidence and keep the original task blocked.');
        if (!title && !summary && !plan.error && plan.ready !== false && last.includes('SYNC/DUMP for same-session DCR')) {
            const operation = /SYNC\/DUMP for same-session DCR ([a-zA-Z0-9-]+)/.exec(last)?.[1];
            const streamRoot = findStream(cwd);
            const args = ['dcr', 'ready', streamRoot.split(sep).at(-1), '--home', process.env.CHAOS_INDEX, '--session', sid, '--operation', operation];
            journal({ effect: 'controlled-agent-dcr-ready', session: sid, args });
            const result = await execute(process.env.PI_STREAMS_BIN, args, { cwd, timeout: 30000 });
            if (plan.acknowledgeReady !== false) text = JSON.parse(result.stdout).acknowledgement;
        }
        if (!title && !summary && process.env.CHAOS_LOAD_ACK === '1' && last.includes('Do not perform task effects or replay commands during this load.')) {
            text = /Dump checkpoint loaded: [a-zA-Z0-9-]+/.exec(last)?.[0] ?? text;
        }
        if (!title && !summary && process.env.CHAOS_LOAD_ERROR === '1' && last.includes('Do not perform task effects or replay commands during this load.')) {
            plan.error = 'Terminal model error: unsupported fixture checkpoint load';
        }
        call.result = { text, error: plan.error ?? null };
        const message = response(text, plan.error, context.messages.reduce((sum, message) => sum + estimateTokens(message), 0));
        stream.push(plan.error ? { type: 'error', reason: 'error', error: message } : { type: 'done', reason: 'stop', message });
        stream.end();
    })().catch(error => {
        call.fixtureError = String(error);
        const message = response('', 'Controlled fixture error: ' + error.message);
        stream.push({ type: 'error', reason: 'error', error: message });
        stream.end();
    });
    return stream;
}
async function createRuntime({ cwd, sessionManager, agentDir }) {
    assert(resolve(cwd).startsWith(scratch + sep), 'session cwd must be owned');
    const sid = sessionManager.getSessionId();
    journal({ effect: 'own-session-before-runtime', session: sid, cwd, file: sessionManager.getSessionFile() });
    owned.set(sid, { cwd, file: sessionManager.getSessionFile() });
    const extensions = { extensions: [], errors: [], runtime: createExtensionRuntime() };
    const skill = join(scratch, 'poteto-mode.md');
    const loader = { getExtensions: () => extensions, getPrompts: () => ({ prompts: [], diagnostics: [] }), getSkills: () => ({ skills: [{ name: 'poteto-mode', filePath: skill, baseDir: scratch }], diagnostics: [] }), getThemes: () => ({ themes: [], diagnostics: [] }), getAgentsFiles: () => ({ agentsFiles: [] }), getSystemPrompt: () => 'Isolated controlled verification. No tools, network, credentials, or external effects.', getAppendSystemPrompt: () => [] };
    const agent = new Agent({ initialState: { model, messages: sessionManager.buildSessionContext().messages, thinkingLevel: 'xhigh', tools: [], systemPrompt: loader.getSystemPrompt() }, streamFn: (selected, context, options) => controlledStream(selected, context, options, sid, cwd) });
    const settingsManager = SettingsManager.inMemory({ compaction: { enabled: false }, retry: { enabled: true, maxRetries: 3, baseDelayMs: 2000 } });
    const session = new AgentSession({ agent, sessionManager, settingsManager, resourceLoader: loader, cwd, modelRuntime: runtime, baseToolsOverride: {} });
    session.subscribe(event => {
        if (['agent_end', 'auto_retry_start', 'auto_retry_end', 'compaction_end'].includes(event.type)) events.push({ session: sid, at: Date.now(), type: event.type, delayMs: event.delayMs });
    });
    return { session, extensionsResult: extensions, services: { cwd, agentDir, resourceLoader: loader, settingsManager, modelRuntime: runtime }, diagnostics: [] };
}
function findStream(cwd) {
    const pointer = join(cwd, '.stream');
    try { return readFileSync(pointer, 'utf8').trim(); } catch { return cwd; }
}
const eventHub = new SessionEventHub();
const sessions = new PiSessionService(eventHub, { ...sessionServiceDependencies({ modelRuntime: runtime, automaticAdmissionStore: new AutomaticAdmissionStore(join(scratch, 'controls')), maintenanceDirectory: join(scratch, 'maintenance'), streamsDcrAdvance: async request => {
    journal({ effect: 'dcr-event-advance', request });
    await runStreamsDcrAdvance(request);
}, agentDir: join(scratch, 'agent'), sessionManager: createPiSessionManagerGateway({ agentDir: join(scratch, 'agent'), env: process.env, sessionDirEnvKeys: [] }) }), archiveStore: new SessionArchiveStore(join(scratch, 'archives.json')), createRuntime });
const app = Fastify({ logger: false, bodyLimit: 16 * 1024 * 1024 });
await app.register(websocket);
app.addHook('onRequest', async request => {
    requests.push({ id: request.id, at: Date.now(), method: request.method, url: request.url });
    journal({ effect: 'http-request-before-handler', method: request.method, url: request.url });
});
app.addHook('onResponse', async (request, reply) => {
    const record = requests.findLast(item => item.id === request.id);
    if (record) record.status = reply.statusCode;
});
registerSessionRoutes(app, sessions, eventHub, '/api');
app.get('/api/runtime', () => ({ component: 'sessiond', capabilities: SESSIOND_RUNTIME_CAPABILITIES }));
app.get('/__chaos/snapshot', async () => {
    const evidence = [];
    for (const [sid, ref] of owned) {
        const active = sessions.active.get(sid)?.runtime.session;
        evidence.push({ session: sid, ...ref, estimatedTokens: active?.messages.reduce((sum, message) => sum + estimateTokens(message), 0), entries: active?.sessionManager.getEntries() });
    }
    const persisted = {};
    for (const directory of ['controls', 'maintenance']) {
        const base = join(scratch, directory);
        if (!existsSync(base)) continue;
        for (const file of readdirSync(base, { recursive: true })) {
            if (file.endsWith('.json')) persisted[join(directory, file)] = JSON.parse(readFileSync(join(base, file), 'utf8'));
        }
    }
    return { persisted, owner, simulatedProviderTransport: true, contextMeasurement: 'native estimateTokens over rebuilt messages; usage is simulated', calls, events, requests, evidence, archives: await sessions.archiveStore.list(), activeSessions: sessions.activeCount() };
});
app.post('/__chaos/plan', async request => {
    const { session, responses = [], authenticated: ready } = request.body;
    assert(owned.has(session), 'only exact owned sessions may be faulted');
    journal({ effect: 'arm-controlled-transport', session, responses, authenticated: ready });
    plans.set(session, responses);
    if (ready !== undefined) authenticated = ready;
    return { armed: true };
});
app.post('/__chaos/policy-canaries', async request => {
    const { session: sid, canary } = request.body;
    assert(owned.has(sid));
    assert.equal(typeof canary, 'string');
    const session = await sessions.getOrOpen(sid);
    const active = sessions.active.get(sid).runtime;
    const cwd = session.sessionManager.getCwd();
    for (const path of [join(cwd, 'AGENTS.md'), join(cwd, 'handover-canary.md'), join(scratch, 'AGENTS.md'), join(scratch, 'agent', 'AGENTS.md')]) writeFileSync(path, canary);
    active.services.resourceLoader.getSystemPrompt = () => 'Source system ' + canary;
    active.services.resourceLoader.getAgentsFiles = () => ({ agentsFiles: [{ path: join(cwd, 'AGENTS.md'), content: canary }] });
    session.sessionManager.appendMessage({ role: 'user', content: 'Inclusive checkpoint contains ' + canary, timestamp: Date.now() });
    session.sessionManager.appendMessage(response('Verified historical evidence ' + canary));
    session.agent.state.messages = session.sessionManager.buildSessionContext().messages;
    return { seeded: true };
});
app.post('/__chaos/history', async request => {
    const { session: sid } = request.body;
    assert(owned.has(sid));
    const session = await sessions.getOrOpen(sid);
    assert(!session.isStreaming && !session.isCompacting);
    journal({ effect: 'seed-controlled-history', session: sid });
    for (let i = 0; i < 8; i++) {
        session.sessionManager.appendMessage({ role: 'user', content: 'Historical permitted context '.repeat(3000), timestamp: Date.now() });
        session.sessionManager.appendMessage(response('Historical permitted evidence '.repeat(3000), undefined, session.sessionManager.buildSessionContext().messages.reduce((sum, message) => sum + estimateTokens(message), 0)));
    }
    session.agent.state.messages = session.sessionManager.buildSessionContext().messages;
    return { estimatedTokens: session.messages.reduce((sum, message) => sum + estimateTokens(message), 0), label: 'simulated history, real persisted context and native token estimates' };
});
let closing = false;
async function shutdown() {
    if (closing) return;
    closing = true;
    await sessions.dispose();
    await app.close();
    journal({ effect: 'service-stopped', activeSessions: sessions.activeCount() });
}
process.once('SIGTERM', () => { void shutdown(); });
process.once('SIGINT', () => { void shutdown(); });
const address = await app.listen({ host: '127.0.0.1', port: 0 });
assert.notEqual(app.server.address().port, 8504);
process.env.PI_WEB_URL = address;
writeFileSync(join(scratch, 'ready.json'), JSON.stringify({ owner, pid: process.pid, url: address }));
journal({ effect: 'service-listening', url: address });
