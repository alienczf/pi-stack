import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import test from 'node:test';
import { clock, errorResponse, fixture, flush, native, response } from './helpers.mjs';

const { unresolvedEffects } = await native('dist/server/sessions/streamTransientRetry.js');
const { SessionManager } = await native('node_modules/@earendil-works/pi-coding-agent/dist/core/session-manager.js');
const { SessionMaintenanceController } = await native('dist/server/sessions/sessionMaintenanceController.js');
const { SessionMaintenanceStore } = await native('dist/server/sessions/sessionMaintenanceStore.js');
const { SessionFailureRecoveries } = await native('dist/server/sessions/sessionFailureRecovery.js');
const { PiSessionService } = await native('dist/server/sessions/piSessionService.js');
const { estimateTokens } = await native('node_modules/@earendil-works/pi-coding-agent/dist/core/compaction/index.js');
const heredoc = "python3 - <<'PY'\nprint('finished')\nPY";
const call = command => ({ ...response('', 'toolUse'), content: [{ type: 'toolCall', id: 'foreground', name: 'bash', arguments: { command } }] });
const item = value => ({ value, raw: JSON.stringify(value) + '\n' });

test('completed foreground shell syntax resolves without jobId while unmatched and detached launches stay fenced', () => {
    for (const command of [heredoc, 'echo "$HOME"', 'printf `pwd`', '[[ -f fixture ]] && echo yes', "eval 'printf done'", 'bash -c "printf done"', 'printf done > fixture 2>&1']) {
        const branch = [item({ id: 'call', message: call(command) }), item({ id: 'result', message: { role: 'toolResult', toolCallId: 'foreground', details: { exitCode: 0 } } })];
        assert.equal(unresolvedEffects(branch), false, command);
        assert.equal(unresolvedEffects(branch.slice(0, 1)), true, command);
    }
    for (const command of ['sleep 1 &', 'nohup fixture', 'setsid fixture', 'disown', 'sbatch fixture', 'qsub fixture', 'tmux new-session -d fixture', 'screen -dmS fixture', "bash -c 'sleep 1 &'", 'printf "$(sleep 1 &)"']) {
        const branch = [item({ id: 'call', message: call(command) }), item({ id: 'result', message: { role: 'toolResult', toolCallId: 'foreground', details: { exitCode: 0 } } })];
        assert.equal(unresolvedEffects(branch), true, command);
        branch.push(item({ id: 'proof', message: { role: 'toolResult', toolCallId: 'foreground', details: { jobId: 'exact-job', status: 'completed' } } }));
        assert.equal(unresolvedEffects(branch), false, command);
    }
});

test('effects window requires the exact successful checkpoint and cannot be moved past an earlier failure by metadata', () => {
    const good = item({ id: 'good', message: response('A verified good turn') });
    const failed = item({ id: 'failure', message: errorResponse('terminated') });
    const boundary = { version: 1, sessionId: 'owned', cwd: '/owned', checkpoint: { entryId: 'good', sha256: createHash('sha256').update(good.raw).digest('hex') }, failure: { entryId: 'failure', sha256: createHash('sha256').update(failed.raw).digest('hex') } };
    const branch = [good, failed, item({ id: 'boundary', customType: 'pi-web.stream-failure', data: boundary })];
    assert.equal(unresolvedEffects(branch, boundary), false);
    branch.push(item({ id: 'unmatched', message: call(heredoc) }));
    assert.equal(unresolvedEffects(branch, boundary), true);
    assert.throws(() => unresolvedEffects(branch, { ...boundary, checkpoint: { ...boundary.checkpoint, sha256: '0'.repeat(64) } }), /checkpoint/);
    const forged = { ...boundary, checkpoint: { entryId: 'later', sha256: '' } };
    const later = item({ id: 'later', message: response('Arbitrary later text') });
    forged.checkpoint.sha256 = createHash('sha256').update(later.raw).digest('hex');
    assert.throws(() => unresolvedEffects([...branch, later, item({ id: 'forged', customType: 'pi-web.stream-failure', data: forged })], forged), /checkpoint/);
});

test('actual foreground heredoc executes once and inference retries on the same identity', async () => {
    const { createBashTool } = await native('node_modules/@earendil-works/pi-coding-agent/dist/core/tools/bash.js');
    let f, executions = 0;
    const bash = { ...createBashTool('.'), execute: (...args) => { executions++; return createBashTool(f.dir).execute(...args); } };
    f = await fixture([call(heredoc), errorResponse('fetch failed'), response('Continued without replay')], { bash });
    const time = clock();
    try {
        const scheduled = new Promise(resolve => { const off = f.session.subscribe(event => { if (event.type === 'auto_retry_start') { off(); resolve(); } }); });
        const run = f.session.prompt('Run the owned foreground command once');
        await scheduled; await flush(); await time.advance(5000); await run;
        assert.equal(executions, 1);
        assert.equal(f.calls.length, 3);
        const result = f.manager.getBranch().find(entry => entry.message?.role === 'toolResult').message;
        assert.equal(result.details?.jobId, undefined);
        assert.equal(result.content[0].text.trim(), 'finished');
        assert.deepEqual(f.calls.map(c => [c.model.provider, c.model.id, c.options.reasoning]), Array(3).fill(['openai-codex', 'gpt-6.1-sol', 'xhigh']));
        assert.equal(f.boundaries.snapshot(f.session).state, 'watching');
    } finally { time.restore(); f.session.dispose(); }
});

test('manual resume, recovery fork, and rotation open for completed foreground commands but not unknown jobs', async () => {
    for (const command of [heredoc, 'sbatch controlled-job']) {
        const f = await fixture([], {}, { policy: 'enrolled-prefix-v1', enroll: { policyId: 'enrolled-prefix-v1', role: 'implementation', assignment: 'Verify only the owned recovery fixture.' } });
        f.manager.appendMessage(response('Last verified good turn'));
        await f.boundaries.observe(f.session);
        f.manager.appendMessage(call(command));
        f.manager.appendMessage({ role: 'toolResult', toolCallId: 'foreground', toolName: 'bash', content: [{ type: 'text', text: 'finished' }], details: { exitCode: 0 }, isError: false, timestamp: Date.now() });
        f.manager.appendMessage(errorResponse('A terminal model failure'));
        f.session.agent.state.messages = f.manager.buildSessionContext().messages;
        await f.boundaries.observe(f.session);
        const boundary = f.boundaries.snapshot(f.session), ref = { id: f.session.sessionId, cwd: f.dir };
        const expected = { ...boundary, generation: f.control.snapshot(ref).generation };
        const service = { failureBoundaries: f.boundaries, rotationSafety: () => ({ entryId: f.manager.getLeafId(), callbacksKnown: true, nativeChildCallbacks: [] }), isCurrentActiveSession: () => true, isSessionEntryMutationActive: () => false, compactionQueuedMessages: () => [], pendingAskStore: { pendingAsk: () => undefined }, pendingExtensionDialogStore: { pendingDialogs: () => [] } };
        if (command === heredoc) {
            assert.equal((await f.boundaries.resume(f.session, expected)).state, 'parked');
            PiSessionService.prototype.assertReplacementCheckpoint.call(service, f.session, f.manager.getLeafId());
            let fork;
            const recoveries = new SessionFailureRecoveries(f.control, { policy: 'enrolled-prefix-v1', boundary: session => f.boundaries.snapshot(session), quiescent: () => {}, fork: async (session, operation) => {
                const manager = SessionManager.open(session.sessionManager.getSessionFile()); manager.createBranchedSession(operation.checkpoint.entryId);
                fork = await fixture([], {}, { manager, control: f.control, boundaries: f.boundaries, watch: false });
                await f.boundaries.holdRecovery(fork.session, operation); return { session: fork.session, cancelled: false };
            } });
            const current = f.boundaries.snapshot(f.session);
            const result = await recoveries.fork(f.session, { id: 'foreground-recovery', episode: 'owned-episode', authority: { kind: 'engine-policy', policyId: 'enrolled-prefix-v1', enrollmentId: current.enrollment.id }, expected: { ...current, generation: f.control.snapshot(ref).generation } });
            assert.equal(result.state, 'forked');
            assert.equal(fork.session.model.id, 'gpt-6.1-sol'); fork.session.dispose();
        } else {
            await assert.rejects(f.boundaries.resume(f.session, expected), /effects|checkpoint/);
            assert.throws(() => PiSessionService.prototype.assertReplacementCheckpoint.call(service, f.session, f.manager.getLeafId()), /effects|checkpoint/);
        }
        f.session.dispose();
    }
});

test('cold parked terminated and fetch-failed classifications refresh without rearming an explicit stop', async () => {
    for (const text of ['terminated', 'fetch failed', 'insufficient_quota', 'content policy refusal']) {
        const f = await fixture();
        f.manager.appendMessage(response('Verified prefix'));
        await f.boundaries.observe(f.session);
        const entryId = f.manager.appendMessage(errorResponse(text));
        const raw = readFileSync(f.manager.getSessionFile(), 'utf8').split(/(?<=\n)/).find(line => { try { return JSON.parse(line).id === entryId; } catch { return false; } });
        const stopped = await f.control.setAllowed({ id: f.session.sessionId, cwd: f.dir }, false);
        f.manager.appendCustomEntry('pi-web.stream-failure', { ...f.boundaries.snapshot(f.session), state: 'parked', failure: { entryId, sha256: createHash('sha256').update(raw).digest('hex'), kind: 'model-error' }, parking: { generation: stopped.generation, owned: false } });
        const file = f.manager.getSessionFile(); f.session.dispose();
        const cold = await fixture([], {}, { manager: SessionManager.open(file), control: f.control, watch: false });
        cold.boundaries.attach(cold.session); await flush();
        assert.equal(cold.boundaries.snapshot(cold.session).failure.kind, text === 'insufficient_quota' ? 'model-error' : text === 'content policy refusal' ? 'content-policy' : 'transient');
        assert.equal(f.control.snapshot({ id: cold.session.sessionId, cwd: f.dir }).generation, stopped.generation);
        assert.equal(cold.calls.length, 0);
        cold.session.dispose();
    }
});

test('same-model native 200k compaction completes, legacy gate reconciles, and empty dead ownership releases without replay', async () => {
    const f = await fixture([response('S'.repeat(800000)), response('Resumed permitted work')]);
    f.manager.appendMessage({ role: 'user', content: 'Historical context '.repeat(40000), timestamp: Date.now() });
    f.manager.appendMessage(response('Historical completed work'));
    f.session.agent.state.messages = f.manager.buildSessionContext().messages;
    const ref = { id: f.session.sessionId, cwd: f.dir }, store = new SessionMaintenanceStore(join(f.dir, 'maintenance'));
    const work = [];
    const host = { current: () => true, busy: session => session.isStreaming || session.isCompacting, humanInputPending: () => false, begin: () => {}, end: () => {}, publish: () => {}, failure: (_, detail) => assert.fail(detail), send: (session, text, images, echo, goal, admitted) => { admitted?.(text); const run = session.prompt(text); work.push(run); return run; } };
    const controller = new SessionMaintenanceController(store, f.control, host);
    controller.start(f.session, { id: 'capacity', instructions: 'Retain permitted work' }, { sessionId: ref.id, cwd: ref.cwd, generation: f.control.snapshot(ref).generation, entryId: f.manager.getLeafId() });
    while (controller.compacting.size) await flush();
    let result = controller.status(f.session, 'capacity');
    assert.equal(result.state, 'complete', result.detail);
    assert(result.tokensAfter >= 200000 && result.tokensAfter < 201000, String(result.tokensAfter));
    assert.equal(result.tokensAfter, f.session.messages.reduce((sum, message) => sum + estimateTokens(message), 0));
    assert.equal(result.targetTokens, 320000);
    store.update(ref, 'capacity', op => { op.state = 'failed'; op.targetTokens = 150000; delete op.contextBudget; op.detail = 'Native compaction did not reduce rebuilt context below 150000 tokens'; });
    result = controller.status(f.session, 'capacity');
    assert.equal(result.state, 'complete', result.detail);
    assert.equal(result.tokensAfter >= 200000, true);
    controller.resume(f.session, { id: 'capacity', text: 'Continue only the permitted owned unit', deliveryId: 'capacity:resume', compactionEntryId: result.compactionEntryId, inputSequence: 0, automaticAdmission: { sessionId: ref.id, cwd: ref.cwd, generation: result.generation, kind: 'resume' } });
    await Promise.all(work); await flush();
    assert.equal(controller.status(f.session, 'capacity').resume.observation.kind, 'assistant-stop');
    const completed = controller.status(f.session, 'capacity');
    store.update(ref, 'capacity', op => { op.state = 'uncertain'; op.resume.state = 'uncertain'; });
    assert.equal(controller.blocksAutomatic(f.session), true);
    store.update(ref, 'capacity', op => { delete op.resume; op.state = 'failed'; op.detail = 'Controlled dead failure'; });
    assert.equal(controller.blocksAutomatic(f.session), false);
    assert.equal(store.get(ref, 'capacity').state, 'superseded');
    assert.equal(store.get(ref, 'capacity').compactionSha256, completed.compactionSha256);
    assert.equal(f.calls.length, 2);
    f.session.dispose();
});
