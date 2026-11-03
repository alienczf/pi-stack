import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import test from 'node:test';
import { existsSync, renameSync, unlinkSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { fixture, flush, native, response, errorResponse } from './helpers.mjs';

const { SessionFailureRecoveries } = await native('dist/server/sessions/sessionFailureRecovery.js');
const { SessionManager } = await native('node_modules/@earendil-works/pi-coding-agent/dist/core/session-manager.js');
const { sessionServiceDependencies } = await native('dist/server/sessiond/sessionServiceDependencies.js');
const { SessionMaintenanceController } = await native('dist/server/sessions/sessionMaintenanceController.js');
const { SessionMaintenanceStore } = await native('dist/server/sessions/sessionMaintenanceStore.js');
const { SessionFailureRetirements } = await native('dist/server/sessions/sessionFailureRetirement.js');
const { expandPotetoInvocation } = await native('dist/server/sessions/potetoInvocation.js');
const { estimateTokens } = await native('node_modules/@earendil-works/pi-coding-agent/dist/core/compaction/index.js');

async function parked(role = 'coordinator', enrolled = true) {
    const deps = sessionServiceDependencies({});
    const f = await fixture([...Array.from({ length: 8 }, () => response('A verified good turn. '.repeat(2000))), errorResponse('Codex login expired')], {}, { policy: deps.engineRecoveryPolicy, ...(enrolled ? { enroll: { policyId: 'enrolled-prefix-v1', role, assignment: 'Implement only the bounded native regression in this owned worktree.' } } : {}) });
    for (let index = 0; index < 8; index++) await f.session.prompt('A good turn ' + index);
    await f.session.prompt('The bounded continuation');
    const boundary = f.boundaries.snapshot(f.session);
    assert.equal(boundary.state, 'parked');
    const authority = { kind: 'engine-policy', policyId: 'enrolled-prefix-v1', enrollmentId: boundary.enrollment?.id ?? f.session.sessionId };
    let forks = 0, fork;
    const recovery = new SessionFailureRecoveries(f.control, { policy: deps.engineRecoveryPolicy, boundary: session => f.boundaries.snapshot(session), quiescent: session => assert.equal(session.isStreaming || session.isCompacting || session.isBashRunning, false), fork: async (session, operation) => {
        forks++;
        const manager = SessionManager.open(session.sessionManager.getSessionFile());
        manager.createBranchedSession(operation.checkpoint.entryId);
        fork = await fixture(Array.from({ length: 4 }, () => response('Continue the current bounded assignment after actual compaction.')), {}, { manager, control: f.control, boundaries: f.boundaries, watch: false });
        await f.boundaries.holdRecovery(fork.session, operation);
        return { session: fork.session, cancelled: false };
    }, resolveFork: async () => fork.session, maintenance: async () => ({}) });
    const assignment = 'Implement only the bounded native regression in this owned worktree.';
    const continuation = { role, assignment, assignmentSha256: createHash('sha256').update(assignment).digest('hex') };
    const request = { id: 'owned-recovery', episode: 'exact-episode', authority, continuation, expected: { ...boundary, generation: f.control.snapshot({ id: f.session.sessionId, cwd: f.dir }).generation } };
    return { ...f, recovery, request, forks: () => forks, fork: () => fork };
}

test('enrolled coordinator and worker fork the actual good prefix without verifier, handover or failed acknowledgement', async () => {
    for (const role of ['coordinator', 'implementation']) {
        const f = await parked(role);
        const result = await f.recovery.fork(f.session, f.request);
        assert.equal(result.state, 'forked');
        assert.equal(result.authority.kind, 'engine-policy');
        assert.equal(result.noticeId, undefined);
        assert.equal(result.provenance, undefined);
        assert.notEqual(result.forkSessionId, f.session.sessionId);
        assert.equal(f.fork().manager.getHeader().parentSession, f.manager.getSessionFile());
        const again = await f.recovery.fork(f.session, f.request);
        assert.deepEqual(again, result);
        assert.equal(f.forks(), 1);
        const prepared = await f.recovery.maintenance(f.session, { id: result.id, action: 'prepare', expectedForkGeneration: result.forkGeneration });
        assert.equal(prepared.operation.maintenance.phase, 'ready');
        assert.equal(prepared.automaticAdmission.allowed, true);
        const fork = f.fork(), ref = { id: fork.session.sessionId, cwd: fork.dir };
        const store = new SessionMaintenanceStore(join(f.dir, 'recovery-maintenance'));
        const sends = new Set();
        const controller = new SessionMaintenanceController(store, f.control, { current: () => true, busy: session => session.isStreaming || session.isCompacting, humanInputPending: () => false, begin: () => {}, end: () => {}, publish: () => {}, failure: (_, detail) => assert.fail(detail), send: (session, text, images, echo, goal, admitted) => {
            const expanded = expandPotetoInvocation(session, text, goal); admitted?.(expanded);
            const run = session.prompt(expanded, { expandPromptTemplates: false }); sends.add(run); return run;
        } });
        const skill = join(f.dir, 'recovery-poteto.md');
        writeFileSync(skill, '---\nname: poteto-mode\ndescription: Controlled fixture\n---\nRead current STATE. Retain the original bounded role.');
        fork.loader.getSkills = () => ({ skills: [{ name: 'poteto-mode', filePath: skill, baseDir: f.dir }] });
        const before = fork.session.messages.reduce((sum, message) => sum + estimateTokens(message), 0);
        let compacted;
        await f.boundaries.runRecovery(fork.session, prepared.operation, async () => {
            controller.start(fork.session, { id: result.id, instructions: 'Retain current STATE and the original role.' }, { sessionId: ref.id, cwd: ref.cwd, generation: prepared.automaticAdmission.generation, entryId: fork.manager.getLeafId() });
            while (controller.compacting.size) await flush();
            compacted = controller.status(fork.session, result.id);
            assert.equal(compacted.state, 'complete');
            const after = fork.session.messages.reduce((sum, message) => sum + estimateTokens(message), 0);
            assert(after < before);
            const goal = 'Verify the current assigned native unit.';
            const text = `Retain role ${role}. Current STATE applies. Do not replay the original command.\n/poteto-mode ${goal}`;
            controller.resume(fork.session, { id: result.id, text, potetoGoal: goal, deliveryId: result.id + ':resume', compactionEntryId: compacted.compactionEntryId, inputSequence: 0, automaticAdmission: { sessionId: ref.id, cwd: ref.cwd, generation: prepared.automaticAdmission.generation, kind: 'resume' } });
            await Promise.all([...sends]); await flush();
        });
        const resumed = controller.status(fork.session, result.id);
        assert.equal(resumed.resume.observation.kind, 'assistant-stop');
        let archived;
        const retirement = new SessionFailureRetirements(store, f.control, { configured: () => true, authorized: operation => f.recovery.authorized(operation), boundary: session => f.boundaries.snapshot(session), resolve: async target => target.id === f.session.sessionId ? f.session : fork.session, operation: (session, id) => f.recovery.operation(session, id), quiescent: session => assert.equal(session.isStreaming || session.isCompacting, false), archived: async () => archived, archive: async (session, id, guard) => {
            guard(); const originalPath = session.sessionManager.getSessionFile(), archivePath = originalPath + '.owned-archive'; renameSync(originalPath, archivePath);
            archived = { sessionId: session.sessionId, cwd: f.dir, originalPath, archivePath, archivedAt: '2026-11-03T00:00:00Z', recoveryOperationId: id };
        }, delete: async (record, id, guard) => { guard(); unlinkSync(record.archivePath); }, release: (session, operation) => f.boundaries.releaseRecovery(session, operation) });
        f.boundaries.permitsRelease = (session, id, original) => retirement.permitsRelease(session, id, original);
        const retired = await retirement.retire({ id: f.session.sessionId, cwd: f.dir }, { id: result.id, forkSessionId: fork.session.sessionId });
        assert.equal(retired.state, 'released');
        assert.equal(existsSync(f.manager.getSessionFile()), false);
        assert.equal(f.boundaries.snapshot(fork.session).state, 'watching');
        assert.deepEqual(await retirement.retire({ id: f.session.sessionId, cwd: f.dir }, { id: result.id, forkSessionId: fork.session.sessionId }), retired);
        console.log(JSON.stringify({ scenario: 'enrolled-recovery-resume-retirement', role, original: f.session.sessionId, fork: fork.session.sessionId, forkFile: fork.manager.getSessionFile(), cacheFile: retired.cacheFile, compaction: resumed.compactionEntryId, compactionSha256: resumed.compactionSha256, observation: resumed.resume.observation, sourceSha256: retired.sourceSha256 }));
        fork.responses.length = 0;
        fork.responses.push(errorResponse('A terminal provider model error'));
        await fork.session.prompt('Continue the same bounded assignment');
        const secondBoundary = f.boundaries.snapshot(fork.session);
        assert.equal(secondBoundary.state, 'parked');
        assert.equal(secondBoundary.enrollment.id, fork.session.sessionId);
        assert.equal(secondBoundary.enrollment.role, role);
        assert.equal(secondBoundary.parking.owned, true);
        let next;
        const secondRecovery = new SessionFailureRecoveries(f.control, { policy: 'enrolled-prefix-v1', boundary: session => f.boundaries.snapshot(session), quiescent: session => assert.equal(session.isStreaming, false), fork: async (session, operation) => {
            const manager = SessionManager.open(session.sessionManager.getSessionFile());
            manager.createBranchedSession(operation.checkpoint.entryId);
            next = await fixture([], {}, { manager, control: f.control, boundaries: f.boundaries, watch: false });
            await f.boundaries.holdRecovery(next.session, operation);
            return { session: next.session, cancelled: false };
        } });
        const second = await secondRecovery.fork(fork.session, { id: 'second-owned-recovery', episode: 'second-episode', authority: { kind: 'engine-policy', policyId: 'enrolled-prefix-v1', enrollmentId: fork.session.sessionId }, expected: { ...secondBoundary, generation: secondBoundary.parking.generation } });
        assert.equal(second.state, 'forked');
        assert.notEqual(second.forkSessionId, fork.session.sessionId);
        next.session.dispose();
        f.session.dispose(); fork.session.dispose();
    }
});

test('historical failure-owned parking recovers without enrollment while a newer stop still wins', async () => {
    const historical = await parked('coordinator', false);
    const result = await historical.recovery.fork(historical.session, historical.request);
    assert.equal(result.state, 'forked');
    assert.equal(historical.forks(), 1);
    assert.equal(result.noticeId, undefined);
    historical.fork().session.dispose();
    historical.session.dispose();
    const stopped = await parked();
    await stopped.control.setAllowed({ id: stopped.session.sessionId, cwd: stopped.dir }, false);
    await assert.rejects(stopped.recovery.fork(stopped.session, stopped.request), /stale/);
    assert.equal(stopped.forks(), 0);
    stopped.session.dispose();
});

test('actual service recovery adapter crosses the parked 409 boundary while ordinary writes remain denied', async () => {
    const f = await parked();
    const { PiSessionService } = await native('dist/server/sessions/piSessionService.js');
    const service = {
        failureBoundaries: f.boundaries, failureRecoveries: f.recovery,
        getArchived: async () => undefined,
        activeForLookup: () => ({ runtime: { session: f.session } }),
        getOrOpen: async () => f.session,
        assertWritable: PiSessionService.prototype.assertWritable,
    };
    const ref = { id: f.session.sessionId, cwd: f.dir };
    await assert.rejects(service.assertWritable(ref), /parked/);
    const result = await PiSessionService.prototype.forkFailureAtCheckpoint.call(service, ref, f.request);
    assert.equal(result.state, 'forked');
    assert.equal(f.forks(), 1);
    f.fork().session.dispose(); f.session.dispose();
});

test('actual same-provider readiness detects simulated auth refresh without token inspection', async () => {
    const f = await parked();
    const { PiSessionService } = await native('dist/server/sessions/piSessionService.js');
    let authenticated = false;
    f.session.modelRuntime.checkAuth = async provider => { assert.equal(provider, 'openai-codex'); return { authenticated }; };
    const service = { assertWritable: async () => {}, getOrOpen: async () => f.session };
    const ref = { id: f.session.sessionId, cwd: f.dir };
    assert.equal((await PiSessionService.prototype.recoveryReadiness.call(service, ref)).authenticated, false);
    authenticated = true;
    const ready = await PiSessionService.prototype.recoveryReadiness.call(service, ref);
    assert.equal(ready.authenticated, true);
    assert.equal(ready.provider, 'openai-codex');
    assert.equal(ready.model, 'gpt-6.1-sol');
    assert.equal(ready.resourceReady, true);
    f.session.dispose();
});

test('native known pre-effect refusal carries exact admission proof and can later fork once', async () => {
    const f = await parked();
    const { AutomaticAdmissionRejected } = await native('dist/server/sessions/automaticAdmissionStore.js');
    const quiescent = f.recovery.hooks.quiescent;
    f.recovery.hooks.quiescent = () => { throw new AutomaticAdmissionRejected('Controlled busy boundary'); };
    await assert.rejects(f.recovery.fork(f.session, f.request), error => {
        assert.equal(error.admission.state, 'refused-before-effect');
        assert.equal(error.admission.id, f.request.id);
        assert.match(error.admission.intentSha256, /^[0-9a-f]{64}$/);
        return true;
    });
    assert.equal(f.forks(), 0);
    f.recovery.hooks.quiescent = quiescent;
    assert.equal((await f.recovery.fork(f.session, f.request)).state, 'forked');
    assert.equal(f.forks(), 1);
    f.fork().session.dispose(); f.session.dispose();
});

test('a caller cannot replace engine-owned policy with arbitrary authority', async () => {
    const f = await parked();
    const request = { ...f.request, authority: { kind: 'arbitrary-label' } };
    await assert.rejects(f.recovery.fork(f.session, request), /authority/);
    assert.equal(f.forks(), 0);
    f.session.dispose();
});
