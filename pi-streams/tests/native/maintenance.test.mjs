import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import test from 'node:test';
import { clock, errorResponse, fixture, flush, native, response } from './helpers.mjs';

const { SessionMaintenanceController } = await native('dist/server/sessions/sessionMaintenanceController.js');
const { SessionMaintenanceStore } = await native('dist/server/sessions/sessionMaintenanceStore.js');
const { estimateTokens } = await native('node_modules/@earendil-works/pi-coding-agent/dist/core/compaction/index.js');
const { expandPotetoInvocation } = await native('dist/server/sessions/potetoInvocation.js');
const { SessionManager } = await native('node_modules/@earendil-works/pi-coding-agent/dist/core/session-manager.js');
const { PiSessionService } = await native('dist/server/sessions/piSessionService.js');

async function scenario({ oversizedHook = false } = {}) {
    const f = await fixture(Array.from({ length: 4 }, () => response('## Goal\nContinue the bounded implementation assignment.\n## Progress\nThe old exchanges were checked.\n## Next steps\nRead current STATE.')));
    if (oversizedHook) {
        const { loadExtensionFromFactory, createExtensionRuntime } = await native('node_modules/@earendil-works/pi-coding-agent/dist/core/extensions/loader.js');
        const { createEventBus } = await native('node_modules/@earendil-works/pi-coding-agent/dist/core/event-bus.js');
        const { writeFileSync } = await import('node:fs');
        const source = join(f.dir, 'oversized-summary.mjs'); writeFileSync(source, 'export default function extension() {}');
        const extension = await loadExtensionFromFactory(pi => pi.on('session_before_compact', event => ({ compaction: { summary: 'Oversized extension summary '.repeat(60000), firstKeptEntryId: event.preparation.firstKeptEntryId, tokensBefore: event.preparation.tokensBefore } })), f.dir, createEventBus(), createExtensionRuntime(), source);
        f.extensions.extensions.push(extension);
        f.session._buildRuntime({ activeToolNames: [], includeAllExtensionTools: false });
    }
    for (let index = 0; index < 8; index++) {
        f.manager.appendMessage({ role: 'user', content: 'Historical context '.repeat(3000), timestamp: Date.now() });
        f.manager.appendMessage(response('Historical evidence '.repeat(3000)));
    }
    f.session.agent.state.messages = f.manager.buildSessionContext().messages;
    const ref = { id: f.session.sessionId, cwd: f.dir };
    const store = new SessionMaintenanceStore(join(f.dir, 'maintenance'));
    const work = new Set();
    const failures = [];
    const host = { current: () => true, busy: session => session.isStreaming || session.isCompacting || session.isBashRunning, humanInputPending: () => false, begin: () => {}, end: () => {}, publish: () => {}, failure: (_, detail) => failures.push(detail), send: (session, text, images, echo, goal, admitted) => { const expanded = expandPotetoInvocation(session, text, goal); admitted?.(expanded); const run = session.prompt(expanded, { expandPromptTemplates: false }); work.add(run); run.finally(() => work.delete(run)); return run; } };
    const controller = new SessionMaintenanceController(store, f.control, host);
    const before = f.session.messages.reduce((sum, message) => sum + estimateTokens(message), 0);
    const control = f.control.snapshot(ref);
    controller.start(f.session, { id: 'dcr-1', instructions: 'Retain current STATE and the bounded worker role.' }, { sessionId: ref.id, cwd: ref.cwd, generation: control.generation, entryId: f.manager.getLeafId() });
    while (controller.compacting.size) await flush();
    const operation = controller.status(f.session, 'dcr-1');
    assert.equal(operation.state, 'complete', JSON.stringify({ operation, failures }));
    const after = f.session.messages.reduce((sum, message) => sum + estimateTokens(message), 0);
    assert(before > 150000, `${before} must exceed the maintenance threshold`);
    assert(after < 150000, `${after} must be below the maintenance threshold`);
    assert(after < before, `${after} must be less than ${before}`);
    assert.equal(operation.tokensAfter, after);
    assert.equal(operation.targetTokens, 320000);
    assert.equal(f.manager.getEntry(operation.compactionEntryId).type, 'compaction');
    return { ...f, ref, store, controller, work, operation, before, after, compactionCalls: f.calls.length };
}

test('actual AgentSession compaction reduces rebuilt context and completed exact-goal RESUME is correlated', async () => {
    const f = await scenario();
    const skill = join(f.dir, 'poteto-mode.md');
    const { writeFileSync } = await import('node:fs');
    writeFileSync(skill, '---\nname: poteto-mode\ndescription: Controlled fixture mode\n---\nRetain the implementation role. Read STATE.');
    f.loader.getSkills = () => ({ skills: [{ name: 'poteto-mode', filePath: skill, baseDir: f.dir }] });
    const goal = 'Verify the current bounded implementation assignment.';
    const text = 'Keep role implementation in its owned worktree. Never coordinate the stream.\n/poteto-mode ' + goal;
    f.controller.resume(f.session, { id: 'dcr-1', text, potetoGoal: goal, deliveryId: 'dcr-1:resume', compactionEntryId: f.operation.compactionEntryId, inputSequence: 0, automaticAdmission: { sessionId: f.ref.id, cwd: f.ref.cwd, generation: f.operation.generation, kind: 'resume' } });
    await Promise.all([...f.work]);
    await flush();
    const result = f.controller.status(f.session, 'dcr-1');
    assert.equal(result.state, 'resumed');
    assert.equal(result.resume.observation.kind, 'assistant-stop');
    assert.equal(result.resume.observation.deliveryId, 'dcr-1:resume');
    const user = f.manager.getEntry(result.resume.observation.userEntryId).message;
    const actual = user.content.map(part => part.text).join('');
    assert(actual.startsWith('Keep role implementation in its owned worktree. Never coordinate the stream.\n<skill name="poteto-mode"'));
    assert(actual.endsWith('</skill>\n\n' + goal));
    assert.equal(f.manager.getEntry(result.resume.observation.assistantEntryId).message.stopReason, 'stop');
    console.log(JSON.stringify({ scenario: 'native-compaction-resume', session: f.ref.id, file: f.manager.getSessionFile(), tokensBefore: f.before, tokensAfter: f.after, compaction: { entryId: result.compactionEntryId, sha256: result.compactionSha256 }, observation: result.resume.observation }));
    f.session.dispose();
});

test('completed compaction superseded by newer explicit input releases only obsolete maintenance ownership', async () => {
    const f = await scenario();
    await f.control.explicitInput(f.ref);
    f.manager.appendMessage({ role: 'user', content: 'A newer authorized objective', timestamp: Date.now() });
    const request = { id: 'dcr-1', text: '/poteto-mode old goal', potetoGoal: 'old goal', deliveryId: 'dcr-1:resume', compactionEntryId: f.operation.compactionEntryId, inputSequence: 0, automaticAdmission: { sessionId: f.ref.id, cwd: f.ref.cwd, generation: f.operation.generation, kind: 'resume' } };
    assert.throws(() => f.controller.resume(f.session, request), /superseded|generation|stale/);
    assert.equal(f.controller.blocksAutomatic(f.session), false);
    assert.equal(f.controller.status(f.session, 'dcr-1').state, 'superseded');
    assert.equal(f.calls.length, f.compactionCalls, 'obsolete RESUME never dispatches');
    const source = readFileSync(f.manager.getSessionFile(), 'utf8');
    assert(source.includes('A newer authorized objective'));
    assert(source.includes(f.operation.compactionEntryId));
    f.session.dispose();
});

test('oversized extension summaries fall back to actual provider compaction below the target', async () => {
    const f = await scenario({ oversizedHook: true });
    assert.equal(f.manager.getEntry(f.operation.compactionEntryId).fromHook, false);
    assert(f.calls.length > 0, 'native provider summarization actually ran');
    assert.equal(f.session.settingsManager.getCompactionSettings().keepRecentTokens, 20000);
    f.session.dispose();
});

test('transparent failure-checkpoint metadata does not supersede completed compaction RESUME', async () => {
    const f = await scenario();
    f.manager.appendCustomEntry('pi-web.stream-failure', f.boundaries.snapshot(f.session));
    f.controller.resume(f.session, { id: 'dcr-1', text: 'Continue permitted current goal', deliveryId: 'dcr-1:resume', compactionEntryId: f.operation.compactionEntryId, inputSequence: 0, automaticAdmission: { sessionId: f.ref.id, cwd: f.ref.cwd, generation: f.operation.generation, kind: 'resume' } });
    await Promise.all([...f.work]); await flush();
    assert.equal(f.controller.status(f.session, 'dcr-1').state, 'resumed');
    f.session.dispose();
});

test('unknown changed checkpoint releases obsolete completed maintenance without replay', async () => {
    const f = await scenario();
    f.manager.appendCustomEntry('extension.changed-checkpoint', { state: 'newer' });
    assert.equal(f.controller.status(f.session, 'dcr-1').state, 'superseded');
    assert.equal(f.controller.blocksAutomatic(f.session), false);
    assert.equal(f.calls.length, f.compactionCalls);
    f.session.dispose();
});

test('watched native summarization retries at fixed five seconds without changing global retry settings', async () => {
    const f = await fixture([errorResponse('503 overloaded'), errorResponse('fetch failed'), response('A concise summary of permitted work.')]);
    for (let index = 0; index < 8; index++) {
        f.manager.appendMessage({ role: 'user', content: 'Historical context '.repeat(3000), timestamp: Date.now() });
        f.manager.appendMessage(response('Historical evidence '.repeat(3000)));
    }
    f.manager.appendCustomEntry('pi-web.maintenance', { id: 'bounded-summary' });
    f.session.agent.state.messages = f.manager.buildSessionContext().messages;
    const time = clock();
    const scheduled = () => new Promise(resolve => { const off = f.session.subscribe(event => { if (event.type === 'summarization_retry_scheduled') { off(); resolve(event); } }); });
    try {
        let waiting = scheduled();
        const run = f.session.compact('Retain current permitted goal.', { targetTokens: 150000 });
        await waiting; await flush();
        assert.deepEqual(time.delays(), [5000]);
        await time.advance(4999); assert.equal(f.calls.length, 1);
        waiting = scheduled(); await time.advance(1); await waiting; await flush();
        assert.deepEqual(time.delays(), [5000]);
        await time.advance(5000);
        const result = await run;
        assert(result.estimatedTokensAfter < 150000);
        assert.equal(f.calls.length, 3);
        assert.equal(f.session.settingsManager.getRetrySettings().baseDelayMs, 2000);
    } finally { time.restore(); f.session.dispose(); }
});

test('an oversized actual provider summary cannot report bounded compaction success', async () => {
    const f = await fixture([response('Provider summary remains oversized. '.repeat(30000))]);
    for (let index = 0; index < 8; index++) {
        f.manager.appendMessage({ role: 'user', content: 'Historical context '.repeat(3000), timestamp: Date.now() });
        f.manager.appendMessage(response('Historical evidence '.repeat(3000)));
    }
    f.manager.appendCustomEntry('pi-web.maintenance', { id: 'oversized-summary' });
    f.session.agent.state.messages = f.manager.buildSessionContext().messages;
    await assert.rejects(f.session.compact('Retain permitted facts.', { targetTokens: 150000 }), /did not reduce rebuilt context below 150000/);
    assert(f.session.messages.reduce((sum, message) => sum + estimateTokens(message), 0) >= 150000);
    f.session.dispose();
});

test('cold service binding and status reconcile only eligible persisted superseded queues without replaying the admitted prefix', async () => {
    for (const fence of ['none', 'stop', 'question', 'sending', 'uncertain', 'generation']) {
        const f = await scenario();
        const ref = f.ref;
        const control = await f.control.explicitInput(ref);
        f.store.update(ref, 'dcr-1', op => {
            op.state = 'superseded'; op.inputSequence = 2; op.lastInputGeneration = control.generation;
            op.inputs = [{ id: 'already-admitted', sequence: 1, text: 'Do not replay admitted input', kind: 'followUp', images: [], attachments: [], echoUserMessage: true, generation: control.generation, state: fence === 'sending' || fence === 'uncertain' ? fence : 'admitted' }, { id: 'persisted-queued', sequence: 2, text: 'Continue the current authorized fixture unit', kind: 'followUp', images: [], attachments: [], echoUserMessage: true, generation: control.generation, state: 'queued' }];
        });
        if (fence === 'stop') await f.control.setAllowed(ref, false);
        if (fence === 'generation') await f.control.explicitInput(ref);
        const file = f.manager.getSessionFile();
        f.session.dispose();
        const cold = await fixture([response('Current authorized fixture unit continued.')], {}, { manager: SessionManager.open(file), control: f.control, watch: false });
        const store = new SessionMaintenanceStore(join(f.dir, 'maintenance'));
        const controller = new SessionMaintenanceController(store, f.control, { current: () => true, busy: session => session.isStreaming, humanInputPending: () => fence === 'question', begin: () => {}, end: () => {}, publish: () => {}, failure: (_, detail) => assert.fail(detail), send: (session, text) => session.prompt(text) });
        const service = { active: new Map(), maintenance: controller, failureBoundaries: cold.boundaries, events: { publish: () => {} }, reconcileQueuedMaintenance: PiSessionService.prototype.reconcileQueuedMaintenance, sessionForStatusOrDialogClose: async () => cold.session, statusFromSession: session => ({ sessionId: session.sessionId }), publishActivityForEvent: () => {}, abortRunScopedExtensionDialogs: () => {}, scheduleCompactionQueueDrain: () => {}, publishStatus: () => {}, updateSubsessionTracking: () => {} };
        PiSessionService.prototype.bindRuntime.call(service, { runtime: { session: cold.session }, unsubscribe: () => {} });
        await PiSessionService.prototype.status.call(service, ref);
        for (let index = 0; index < 50; index++) await flush();
        const result = store.get(ref, 'dcr-1');
        assert.equal(result.inputs[1].state, fence === 'none' ? 'admitted' : 'queued', fence);
        assert.equal(cold.calls.length, fence === 'none' ? 1 : 0, fence);
        if (fence === 'none') {
            assert.equal(cold.calls[0].context.messages.at(-1).content[0].text, 'Continue the current authorized fixture unit');
            assert.equal(cold.calls[0].model.id, 'gpt-6.1-sol');
        }
        assert.equal(f.calls.length, f.compactionCalls);
        cold.session.dispose();
    }
});

test('mandatory maintenance on a small session performs actual native summarization instead of failing Nothing to compact', async () => {
    const f = await fixture([response('A verified good small-session turn.'), response('Summary of the verified small-session turn.'), response('Resumed the authorized small-session unit.')]);
    try {
        await f.session.prompt('Verify the small owned fixture unit.');
        const store = new SessionMaintenanceStore(join(f.dir, 'small-maintenance'));
        const sends = [];
        const controller = new SessionMaintenanceController(store, f.control, { current: () => true, busy: session => session.isStreaming, humanInputPending: () => false, begin: () => {}, end: () => {}, publish: () => {}, failure: (_, detail) => assert.fail(detail), send: (session, text, images, echo, goal, admitted) => { admitted?.(text); const run = session.prompt(text); sends.push(run); return run; } });
        const ref = { id: f.session.sessionId, cwd: f.dir };
        const generation = f.control.snapshot(ref).generation;
        const before = f.session.messages.reduce((sum, message) => sum + estimateTokens(message), 0);
        assert(before < 150000);
        controller.start(f.session, { id: 'small-dcr', instructions: 'Retain the verified small unit and current scope.' }, { sessionId: ref.id, cwd: ref.cwd, generation, entryId: f.manager.getLeafId() });
        while (controller.compacting.size) await flush();
        const result = controller.status(f.session, 'small-dcr');
        assert.equal(result.state, 'complete', result.detail);
        assert.equal(f.manager.getEntry(result.compactionEntryId).type, 'compaction');
        assert.equal(f.calls.length, 2);
        assert(JSON.stringify(f.calls[1].context).includes('A verified good small-session turn.'));
        controller.resume(f.session, { id: 'small-dcr', text: 'Continue the authorized small-session unit.', deliveryId: 'small-dcr:resume', compactionEntryId: result.compactionEntryId, inputSequence: 0, automaticAdmission: { sessionId: ref.id, cwd: ref.cwd, generation, kind: 'resume' } });
        await Promise.all(sends); await flush();
        assert.equal(controller.status(f.session, 'small-dcr').resume.observation.kind, 'assistant-stop');
        assert(f.calls.every(call => call.model.provider === 'openai-codex' && call.model.id === 'gpt-6.1-sol'));
    } finally { f.session.dispose(); }
});

test('stop and uncertain maintenance remain fenced', async () => {
    const f = await scenario();
    await f.control.setAllowed(f.ref, false);
    f.controller.status(f.session, 'dcr-1');
    assert.equal(f.control.snapshot(f.ref).allowed, false);
    f.store.update(f.ref, 'dcr-1', op => { op.state = 'uncertain'; op.resume = { deliveryId: 'dcr-1:resume', text: 'unknown', generation: op.generation, inputSequence: 0, state: 'uncertain' }; });
    assert.equal(f.controller.blocksAutomatic(f.session), true);
    assert.equal(f.controller.status(f.session, 'dcr-1').state, 'uncertain');
    f.session.dispose();
});
