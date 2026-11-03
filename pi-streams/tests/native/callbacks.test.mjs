import assert from 'node:assert/strict';
import { writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import test from 'node:test';
import { clock, fixture, flush, native, root } from './helpers.mjs';
const { loadExtensionFromFactory, loadExtensions, createExtensionRuntime } = await native('node_modules/@earendil-works/pi-coding-agent/dist/core/extensions/loader.js');
const { createEventBus } = await native('node_modules/@earendil-works/pi-coding-agent/dist/core/event-bus.js');
const { callbackInventory, prepareCallbackDrops } = await native('dist/server/sessions/extensionCallbackOwnership.js');

async function declaration(f, snapshot, drop) {
    const path = join(f.dir, 'owned-extension.mjs');
    writeFileSync(path, 'export default function extension() {}');
    return loadExtensionFromFactory(pi => pi.registerCallbackOwnership(snapshot, drop), f.dir, createEventBus(), createExtensionRuntime(), path);
}

test('actual loader binds declarations to the loaded source and live active owners', async () => {
    const f = await fixture();
    let owners = [];
    const extension = await declaration(f, () => ({ kind: owners.length ? 'active' : 'none', owners: [...owners], revision: JSON.stringify(owners) }));
    const loaded = { extensions: [extension], errors: [] };
    assert.equal(callbackInventory(loaded).known, true);
    owners = ['completion-run-1'];
    assert.equal(callbackInventory(loaded).known, false);
    assert.deepEqual(callbackInventory(loaded).owners[0].owners, ['completion-run-1']);
    owners = [];
    assert.equal(callbackInventory(loaded).known, true);
    writeFileSync(extension.resolvedPath, 'changed loaded bytes');
    assert.equal(callbackInventory(loaded).known, false);
    f.session.dispose();
});

test('safe-drop waits for the actual cancellation receipt and rechecks revision', async () => {
    const f = await fixture();
    let dropped = false, release;
    const gate = new Promise(resolve => { release = resolve; });
    const extension = await declaration(f, () => ({ kind: dropped ? 'none' : 'safe-to-drop', revision: dropped ? 'closed' : 'watcher-1', owners: dropped ? [] : ['ui-watcher'] }), async revision => { await gate; dropped = true; return { droppedRevision: revision }; });
    const loaded = { extensions: [extension], errors: [] };
    let settled = false;
    const pending = prepareCallbackDrops(loaded).then(() => { settled = true; });
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(settled, false);
    release(); await pending;
    assert.equal(callbackInventory(loaded).owners[0].kind, 'none');
    assert.equal(settled, true);
    f.session.dispose();
});

test('all five real idle adapters clear and an actual batched subagent completion remains fenced', async () => {
    const f = await fixture();
    const time = clock();
    const bus = createEventBus();
    const previousFetch = globalThis.fetch;
    globalThis.fetch = () => Promise.reject(new Error('Fixture refuses outbound network'));
    const loaded = await loadExtensions(['pi-subagents/index.ts', 'pi-web-access/index.ts', 'pi-prompt-template-model/index.ts', 'pi-cursor-sdk/src/index.ts', 'pi-jupyter/extensions/index.ts'].map(path => resolve(root, '../extensions', path)), f.dir, bus, f.extensions.runtime);
    assert.deepEqual(loaded.errors, []);
    f.extensions.extensions.push(...loaded.extensions);
    f.session._buildRuntime({ activeToolNames: [], includeAllExtensionTools: false });
    try {
        await f.session._extensionRunner.emit({ type: 'session_start', reason: 'startup' });
        f.manager.appendCustomMessageEntry('subagent-notify', 'Historical completed child', false);
        const { PiSessionService } = await native('dist/server/sessions/piSessionService.js');
        const service = { subsessionChildren: new Map(), activeRuntimeForSession: () => ({ services: { resourceLoader: { getExtensions: () => loaded } } }) };
        const safety = PiSessionService.prototype.rotationSafety.call(service, f.session);
        assert.equal(safety.callbacksKnown, true, JSON.stringify(safety));
        assert.equal(safety.callbackOwners.length, 5);
        bus.emit('subagent:async-complete', { id: 'controlled-completed-child', sessionId: f.manager.getSessionFile(), completionOwnerId: globalThis[Symbol.for('pi-subagents.completion-owner-id')], source: 'async', agent: 'fixture', success: true, state: 'complete', summary: 'Controlled completion, no child was launched.', triggerTurn: false });
        assert.equal(callbackInventory(loaded).known, false, 'a real pending completion must fence recovery');
        await assert.rejects(prepareCallbackDrops(loaded), /ownership/);
        await time.advance(1000);
        assert.equal(callbackInventory(loaded).known, true, JSON.stringify(callbackInventory(loaded)));
        assert.equal(f.manager.getBranch().some(entry => entry.customType === 'subagent-notify'), true);
        const notebook = join(f.dir, 'fixture.ipynb');
        writeFileSync(notebook, '{"cells":[],"metadata":{},"nbformat":4,"nbformat_minor":5}');
        const jupyter = loaded.extensions.find(extension => extension.resolvedPath.includes('pi-jupyter'));
        for (const handler of jupyter.handlers.get('tool_call') ?? []) await handler({ input: { path: notebook } }, { cwd: f.dir });
        assert.equal(callbackInventory(loaded).owners.find(owner => owner.path.includes('pi-jupyter')).kind, 'safe-to-drop');
        writeFileSync(notebook, '{"cells":[],"metadata":{"changed":true},"nbformat":4,"nbformat_minor":5}');
        await flush();
        await prepareCallbackDrops(loaded);
        await time.advance(200);
        assert.equal(callbackInventory(loaded).owners.every(owner => owner.kind === 'none'), true);
        assert.equal(f.calls.length, 0, 'watcher cancellation cannot launch a turn');
        console.log(JSON.stringify({ scenario: 'real-extension-idle-and-drop', owners: callbackInventory(loaded).owners }));
    } finally {
        await f.session._extensionRunner.emit({ type: 'session_shutdown', reason: 'quit' });
        time.restore(); globalThis.fetch = previousFetch; f.session.dispose();
    }
});

test('stale watcher errors and queued restart timers cannot reactivate dropped ownership', async () => {
    const { createJiti } = await native('node_modules/@earendil-works/pi-coding-agent/node_modules/jiti/lib/jiti.mjs');
    const jiti = createJiti(import.meta.url, { interopDefault: true });
    const { createResultWatcher } = await jiti.import(resolve(root, '../extensions/pi-subagents/src/runs/background/result-watcher.ts'));
    const fs = await import('node:fs');
    const f = await fixture();
    const errors = [], scheduled = [];
    let watches = 0;
    const state = { currentSessionId: f.session.sessionId, watcher: null, watcherRestartTimer: null };
    const watcher = createResultWatcher({ events: createEventBus() }, state, f.dir, 60000, {
        platform: 'linux', resultScanLogging: 'off',
        fs: { ...fs, watch: () => { watches++; return { on: (_, handler) => { errors.push(handler); }, close: () => {}, unref: () => {} }; } },
        timers: { setTimeout: callback => { scheduled.push(callback); return { unref() {} }; }, clearTimeout: () => {}, setInterval: () => ({ unref() {} }), clearInterval: () => {} },
    });
    watcher.startResultWatcher();
    assert.equal(watches, 1);
    const failure = Object.assign(new Error('Controlled watcher failure'), { code: 'ENOENT' });
    const log = console.error; console.error = () => {};
    try { errors[0](failure); } finally { console.error = log; }
    assert.equal(scheduled.length, 1);
    watcher.stopResultWatcher();
    errors[0](failure);
    scheduled[0]();
    assert.equal(watches, 1);
    assert.equal(scheduled.length, 1);
    assert.equal(watcher.callbackState().resources, false);
    f.session.dispose();
});

test('unknown failed-load and declaration exceptions refuse rather than infer no callbacks', async () => {
    const f = await fixture();
    assert.equal(callbackInventory({ extensions: [{ resolvedPath: '/unknown' }], errors: [] }).known, false);
    const extension = await declaration(f, () => { throw new Error('snapshot unavailable'); });
    assert.equal(callbackInventory({ extensions: [extension], errors: [] }).known, false);
    assert.equal(callbackInventory({ extensions: [], errors: [{ path: 'failed', error: 'load error' }] }).known, false);
    await assert.rejects(prepareCallbackDrops({ extensions: [extension], errors: [] }), /ownership/);
    f.session.dispose();
});
