import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { fixture, flush, native, response, errorResponse } from './helpers.mjs';

const { SessionFailureRecoveries } = await native('dist/server/sessions/sessionFailureRecovery.js');
const direct = await native('node_modules/@earendil-works/pi-ai/dist/utils/retry.js');
const nested = await native('node_modules/@earendil-works/pi-coding-agent/node_modules/@earendil-works/pi-ai/dist/utils/retry.js');
const errors = ['This content was flagged for possible cybersecurity risk', '503 content_policy_violation, please retry your request', '429 usage limit hint with content-policy refusal', 'Request rejected by the content filter', 'Safety policy refusal', 'ResponsibleAIPolicyViolation'];

async function policyPark(message, rejected = 'A bounded continuation') {
    const f = await fixture([response('Verified permitted checkpoint'), errorResponse(message)], {}, { policy: 'enrolled-prefix-v1', enroll: { policyId: 'enrolled-prefix-v1', role: 'coordinator', assignment: 'Verify only permitted offline fixture behavior' } });
    await f.session.prompt('A permitted fixture turn');
    await f.session.prompt(rejected);
    await flush();
    return f;
}

test('native policy refusals never enter either retry classifier and remain durably parked', async () => {
    for (const message of errors) {
        const error = errorResponse(message);
        assert.equal(direct.isRetryableAssistantError(error), false);
        assert.equal(nested.isRetryableAssistantError(error), false);
        const f = await policyPark(message);
        try {
            assert.equal(f.calls.length, 2);
            assert.equal(f.boundaries.snapshot(f.session).failure.kind, 'content-policy');
            assert.equal(f.boundaries.snapshot(f.session).state, 'parked');
            assert.equal(f.control.snapshot({ id: f.session.sessionId, cwd: f.dir }).allowed, false);
            assert.equal(f.boundaries.retrySnapshot(f.session), undefined);
        } finally { f.session.dispose(); }
    }
});

test('native resume and fork refuse historical model-error policy failures before any recovery effect', async () => {
    const f = await policyPark(errors[0]);
    try {
        const boundary = f.boundaries.snapshot(f.session);
        boundary.failure.kind = 'model-error';
        f.session.sessionManager.appendCustomEntry('pi-web.stream-failure', boundary);
        f.boundaries.records.set(f.session, boundary);
        const ref = { id: f.session.sessionId, cwd: f.dir };
        const before = f.control.snapshot(ref);
        const expected = { ...boundary, generation: before.generation };
        await assert.rejects(f.boundaries.resume(f.session, expected), /Content-policy blocker/);
        let forks = 0;
        const recoveries = new SessionFailureRecoveries(f.control, { policy: 'enrolled-prefix-v1', boundary: session => f.boundaries.snapshot(session), quiescent: session => assert.equal(session.isStreaming, false), fork: async () => { forks++; assert.fail('Policy content must not be replayed'); } });
        await assert.rejects(recoveries.fork(f.session, { id: 'policy-recovery', episode: 'policy-episode', authority: { kind: 'engine-policy', policyId: 'enrolled-prefix-v1', enrollmentId: boundary.enrollment.id }, expected }), /Content-policy blocker/);
        assert.equal(forks, 0);
        assert.equal(recoveries.operations(f.session).size, 0);
        assert.deepEqual(f.control.snapshot(ref), before);
        assert.equal(f.calls.length, 2);
        assert.equal(f.boundaries.snapshot(f.session).state, 'parked');
    } finally { f.session.dispose(); }
});

test('permitted analysis itself rejected by policy is a durable blocker, not another same-content recovery', async () => {
    const assignment = 'Explain the content-policy restriction and record a blocker. Do not perform the rejected task or any external effects.';
    const f = await policyPark(errors[0], assignment);
    try {
        const boundary = f.boundaries.snapshot(f.session);
        const recovery = new SessionFailureRecoveries(f.control, { policy: 'enrolled-prefix-v1', boundary: session => f.boundaries.snapshot(session), quiescent: () => {}, fork: async () => assert.fail('Rejected analysis must not replay') });
        const continuation = { mode: 'permitted-analysis-v1', role: 'coordinator', assignment, assignmentSha256: createHash('sha256').update(assignment).digest('hex'), blockedGoalSha256: 'b'.repeat(64), policyFailure: { entryId: boundary.failure.entryId, sha256: boundary.failure.sha256 } };
        await assert.rejects(recovery.fork(f.session, { id: 'policy-repeat', episode: 'repeat', authority: { kind: 'engine-policy', policyId: 'enrolled-prefix-v1', enrollmentId: boundary.enrollment.id }, continuation, expected: { ...boundary, generation: boundary.parking.generation } }), /Content-policy blocker/);
        assert.equal(recovery.operations(f.session).size, 0);
        assert.equal(f.control.snapshot({ id: f.session.sessionId, cwd: f.dir }).allowed, false);
    } finally { f.session.dispose(); }
});

test('historical policy records and unsafe saved restricted operations cannot expose prefix, AGENTS or tools to recovery inference', async () => {
    const f = await policyPark(errors[0], 'REJECTED-ASSIGNMENT-CANARY');
    try {
        const boundary = f.boundaries.snapshot(f.session);
        boundary.failure.kind = 'model-error';
        f.session.sessionManager.appendCustomEntry('pi-web.stream-failure', boundary);
        f.boundaries.records.set(f.session, boundary);
        const before = readFileSync(f.manager.getSessionFile());
        const control = f.control.snapshot({ id: f.session.sessionId, cwd: f.dir });
        const continuation = { mode: 'permitted-analysis-v1', role: 'coordinator', assignment: 'Explain only the restriction' };
        const recovery = new SessionFailureRecoveries(f.control, { policy: 'enrolled-prefix-v1', boundary: session => f.boundaries.snapshot(session), quiescent: () => {}, fork: async () => assert.fail('Unsafe policy fork must not exist') });
        await assert.rejects(recovery.fork(f.session, { id: 'clean-view-unproven', episode: 'policy', authority: { kind: 'engine-policy', policyId: 'enrolled-prefix-v1', enrollmentId: boundary.enrollment.id }, continuation, expected: { ...boundary, generation: control.generation } }), /No clean model context/);
        await assert.rejects(f.boundaries.runRecovery(f.session, { id: 'old-unsafe-operation', continuation }, () => f.session.prompt('Do not run inherited context')), /Historical restricted operation/);
        assert.deepEqual(readFileSync(f.manager.getSessionFile()), before);
        assert.deepEqual(f.control.snapshot({ id: f.session.sessionId, cwd: f.dir }), control);
        assert.equal(f.calls.length, 2);
        assert.equal(recovery.operations(f.session).size, 0);
    } finally { f.session.dispose(); }
});
