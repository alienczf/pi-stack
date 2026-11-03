import assert from 'node:assert/strict';
import test from 'node:test';
import { fixture, flush, native, response } from './helpers.mjs';

const { PiSessionService } = await native('dist/server/sessions/piSessionService.js');
const { SessionManager } = await native('node_modules/@earendil-works/pi-coding-agent/dist/core/session-manager.js');

test('actual control entry suppresses the fourth blocked goal even after cold reopen without changing generation or model', async () => {
    const goal = 'Verify the bounded offline fixture unit.';
    const f = await fixture(Array.from({ length: 3 }, () => response('Blocked. The authorized fixture dependency is unavailable.')));
    for (let index = 0; index < 3; index++) await f.session.prompt(goal);
    const file = f.manager.getSessionFile();
    f.session.dispose();
    const cold = await fixture([], {}, { manager: SessionManager.open(file), control: f.control, watch: false });
    const ref = { id: cold.session.sessionId, cwd: cold.dir };
    const before = cold.control.snapshot(ref);
    const service = { automaticAdmissionStore: cold.control, controlGoals: { submit: () => assert.fail('Fourth identical blocked goal must not dispatch') }, assertWritable: async () => {}, maintenanceSession: async () => cold.session };
    try {
        await assert.rejects(PiSessionService.prototype.controlGoal.call(service, ref, { id: 'fourth-dispatch', text: goal }), /Blocked-goal escalation/);
        await assert.rejects(PiSessionService.prototype.controlGoal.call(service, ref, { id: 'fifth-dispatch', text: goal }), /Blocked-goal escalation/);
        assert.deepEqual(cold.control.snapshot(ref), before);
        const records = cold.manager.getBranch().filter(entry => entry.customType === 'pi-web.blocked-goal');
        assert.equal(records.length, 1);
        assert.equal(records[0].data.sent.length, 3);
        assert.equal(records[0].data.received.length, 3);
        assert.equal(records[0].data.disposition, 'suppressed');
        assert.equal(cold.session.model.provider, 'openai-codex');
        assert.equal(cold.session.model.id, 'gpt-6.1-sol');
        assert.equal(cold.calls.length, 0);
    } finally { cold.session.dispose(); }
});

test('successful progress does not become blocked history and resets earlier blocked outcomes', async () => {
    for (const answers of [
        ['Completed permitted unit one and verified its artifact.', 'Passed the authorized integration check.', 'Blocked. A new dependency is unavailable.'],
        ['Blocked. Missing fixture dependency.', 'Installed and verified the authorized dependency.', 'Validated the artifact and passed its check.'],
    ]) {
        const f = await fixture([...answers.map(text => response(text)), response('Continued the authorized unit.')]);
        const goal = 'Verify the bounded offline unit';
        for (const _ of answers) await f.session.prompt(goal);
        const service = { automaticAdmissionStore: f.control, controlGoals: { submit: async (session, request) => { await session.prompt(request.text); return { state: 'ended' }; } }, assertWritable: async () => {}, maintenanceSession: async () => f.session };
        try {
            assert.equal((await PiSessionService.prototype.controlGoal.call(service, { id: f.session.sessionId, cwd: f.dir }, { id: 'permitted-fourth', text: goal })).state, 'ended');
            assert.equal(f.calls.length, 4);
            assert.equal(f.control.snapshot({ id: f.session.sessionId, cwd: f.dir }).allowed, true);
        } finally { f.session.dispose(); }
    }
});

test('completed units with no blockers and different authorized goals still dispatch', async () => {
    const f = await fixture(Array.from({ length: 4 }, () => response('Finite unit complete. No blockers. Standing goal unfinished.')));
    const ref = { id: f.session.sessionId, cwd: f.dir };
    const service = { automaticAdmissionStore: f.control, controlGoals: { submit: async (session, request) => { await session.prompt(request.text); return { state: 'ended' }; } }, assertWritable: async () => {}, maintenanceSession: async () => f.session };
    try {
        for (let index = 0; index < 4; index++) assert.equal((await PiSessionService.prototype.controlGoal.call(service, ref, { id: 'unit-' + index, text: 'Verify the finite fixture unit' })).state, 'ended');
        await flush();
        assert.equal(f.calls.length, 4);
    } finally { f.session.dispose(); }
});
