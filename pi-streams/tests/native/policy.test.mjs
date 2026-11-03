import assert from 'node:assert/strict';
import test from 'node:test';
import { fixture, flush, native, response, errorResponse } from './helpers.mjs';

const { SessionFailureRecoveries } = await native('dist/server/sessions/sessionFailureRecovery.js');
const direct = await native('node_modules/@earendil-works/pi-ai/dist/utils/retry.js');
const nested = await native('node_modules/@earendil-works/pi-coding-agent/node_modules/@earendil-works/pi-ai/dist/utils/retry.js');
const errors = ['This content was flagged for possible cybersecurity risk', '503 content_policy_violation, please retry your request', '429 usage limit hint with content-policy refusal', 'Request rejected by the content filter', 'Safety policy refusal', 'ResponsibleAIPolicyViolation'];

async function policyPark(message) {
    const f = await fixture([response('Verified permitted checkpoint'), errorResponse(message)], {}, { policy: 'enrolled-prefix-v1', enroll: { policyId: 'enrolled-prefix-v1', role: 'coordinator', assignment: 'Verify only permitted offline fixture behavior' } });
    await f.session.prompt('A permitted fixture turn');
    await f.session.prompt('A bounded continuation');
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
