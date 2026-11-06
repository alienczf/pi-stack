import assert from 'node:assert/strict';
import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import test from 'node:test';
import { fixture, flush, native, response } from './helpers.mjs';

const { SessionMaintenanceController } = await native('dist/server/sessions/sessionMaintenanceController.js');
const { SessionMaintenanceStore } = await native('dist/server/sessions/sessionMaintenanceStore.js');
const { loadExtensionFromFactory, createExtensionRuntime } = await native('node_modules/@earendil-works/pi-coding-agent/dist/core/extensions/loader.js');
const { createEventBus } = await native('node_modules/@earendil-works/pi-coding-agent/dist/core/event-bus.js');

for (const stopped of [false, true]) {
    test(`expired hung compaction fences late native writes and preserves stop=${stopped}`, async () => {
        const f = await fixture([]);
        let release;
        let entered = false;
        const pending = new Promise(resolve => { release = resolve; });
        const source = join(f.dir, 'hung-summary.mjs');
        writeFileSync(source, 'export default function extension() {}');
        const extension = await loadExtensionFromFactory(pi => pi.on('session_before_compact', async event => {
            entered = true;
            await pending;
            return { compaction: { summary: 'Late summary must never persist.', firstKeptEntryId: event.preparation.firstKeptEntryId, tokensBefore: event.preparation.tokensBefore } };
        }), f.dir, createEventBus(), createExtensionRuntime(), source);
        f.extensions.extensions.push(extension);
        f.session._buildRuntime({ activeToolNames: [], includeAllExtensionTools: false });
        for (let index = 0; index < 8; index++) {
            f.manager.appendMessage({ role: 'user', content: 'Retained checkpoint context '.repeat(3000), timestamp: Date.now() });
            f.manager.appendMessage(response('Retained completed work '.repeat(3000)));
        }
        f.session.agent.state.messages = f.manager.buildSessionContext().messages;
        const ref = { id: f.session.sessionId, cwd: f.dir };
        const store = new SessionMaintenanceStore(join(f.dir, 'bounded-maintenance'));
        const failures = [];
        const controller = new SessionMaintenanceController(store, f.control, { current: () => true, busy: session => session.isStreaming || session.isCompacting, humanInputPending: () => false, begin: () => {}, end: () => {}, publish: () => {}, failure: (_, detail) => failures.push(detail), send: () => assert.fail('retired compaction must not send input') });
        const generation = f.control.snapshot(ref).generation;
        try {
            controller.start(f.session, { id: 'hung', instructions: 'Keep the saved checkpoint.' }, { sessionId: ref.id, cwd: ref.cwd, generation, entryId: f.manager.getLeafId() });
            await flush();
            assert.equal(entered, true);
            assert.equal(store.get(ref, 'hung').state, 'compacting');
            assert.equal(f.session.isCompacting, true);
            const before = readFileSync(f.manager.getSessionFile());
            if (stopped) await f.control.setAllowed(ref, false);
            const admission = f.control.snapshot(ref);
            store.update(ref, 'hung', operation => { operation.lease.deadline = Number(process.hrtime.bigint() / 1000000n) - 1; });
            const retired = controller.status(f.session, 'hung');
            assert.equal(retired.state, 'failed');
            assert.equal(retired.compactionRetirement.writerFenced, true);
            assert.equal(f.session.isCompacting, false);
            assert.equal(controller.blocksAutomatic(f.session), true);
            release();
            await flush();
            assert.deepEqual(readFileSync(f.manager.getSessionFile()), before);
            assert.equal(store.get(ref, 'hung').compactionEntryId, undefined);
            assert.equal(store.get(ref, 'hung').state, 'failed');
            assert.deepEqual(f.control.snapshot(ref), admission);
            assert.equal(f.calls.length, 0);
            assert.deepEqual(failures, []);
        } finally {
            release();
            for (const timer of controller.deadlines.values()) clearTimeout(timer);
            f.session.dispose();
        }
    });
}

const { SessionManager } = await native('node_modules/@earendil-works/pi-coding-agent/dist/core/session-manager.js');
const { AssistantMessageEventStream } = await native('node_modules/@earendil-works/pi-ai/dist/utils/event-stream.js');

test('held provider lease fences same-manager and cold late writers', async () => {
    const f = await fixture();
    const held = new AssistantMessageEventStream();
    f.session.agent.streamFunction = () => held;
    for (let index = 0; index < 8; index++) {
        f.manager.appendMessage({ role: 'user', content: 'Owned historical input '.repeat(3000), timestamp: Date.now() });
        f.manager.appendMessage(response('Owned completed work '.repeat(3000)));
    }
    f.session.agent.state.messages = f.manager.buildSessionContext().messages;
    const ref = { id: f.session.sessionId, cwd: f.dir };
    const store = new SessionMaintenanceStore(join(f.dir, 'maintenance'));
    const failures = [];
    let ended = 0;
    const controller = new SessionMaintenanceController(store, f.control, {
        current: () => true,
        busy: session => session.isStreaming || session.isCompacting || session.isBashRunning,
        humanInputPending: () => false,
        begin: () => {},
        end: () => { ended++; },
        publish: () => {},
        failure: (_, detail) => failures.push(detail),
        send: () => assert.fail('retired maintenance must not submit a prompt'),
    });
    try {
        controller.start(f.session, { id: 'held-compaction', instructions: 'Retain the owned validated dump.' }, {
            sessionId: ref.id, cwd: ref.cwd, generation: f.control.snapshot(ref).generation, entryId: f.manager.getLeafId(),
        });
        await flush();
        assert.equal(controller.status(f.session, 'held-compaction').state, 'compacting');
        const before = readFileSync(f.manager.getSessionFile());
        store.update(ref, 'held-compaction', op => { op.lease.deadline = 1; });
        const retired = controller.status(f.session, 'held-compaction');
        assert.equal(retired.state, 'failed');
        assert.equal(retired.compactionRetirement.writerFenced, true);
        assert.equal(controller.compacting.size, 0);
        assert.equal(ended, 1);
        assert.throws(() => f.manager.appendCustomEntry('late-writer', {}), /read-only/);
        const cold = SessionManager.open(f.manager.getSessionFile());
        assert.throws(() => cold.appendCustomEntry('cold-late-writer', {}), /read-only/);
        held.push({ type: 'done', reason: 'stop', message: response('A late summary must not persist.') });
        held.end();
        await flush();
        assert.deepEqual(readFileSync(f.manager.getSessionFile()), before);
        assert.equal(controller.status(f.session, 'held-compaction').state, 'failed');
        assert.equal(ended, 1);
        assert.deepEqual(failures, []);
        console.log(JSON.stringify({ result: 'PASS', injectedFault: 'held simulated provider and expired persisted lease', actualModules: true, sameManagerAndColdWriterFenced: true, lateResultPreservedExactBytes: true }));
    } finally {
        for (const timer of controller.deadlines.values()) clearTimeout(timer);
        f.session.dispose();
    }
});
