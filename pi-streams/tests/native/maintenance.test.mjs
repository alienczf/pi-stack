import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import test from 'node:test';
import { fixture, flush, native, response } from './helpers.mjs';

const { SessionMaintenanceController } = await native('dist/server/sessions/sessionMaintenanceController.js');
const { SessionMaintenanceStore } = await native('dist/server/sessions/sessionMaintenanceStore.js');
const { estimateTokens } = await native('node_modules/@earendil-works/pi-coding-agent/dist/core/compaction/index.js');
const { expandPotetoInvocation } = await native('dist/server/sessions/potetoInvocation.js');

async function scenario() {
    const f = await fixture(Array.from({ length: 4 }, () => response('## Goal\nContinue the bounded implementation assignment.\n## Progress\nThe old exchanges were checked.\n## Next steps\nRead current STATE.')));
    for (let index = 0; index < 8; index++) {
        f.manager.appendMessage({ role: 'user', content: 'Historical context '.repeat(2000), timestamp: Date.now() });
        f.manager.appendMessage(response('Historical evidence '.repeat(2000)));
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
    assert(after < before, `${after} must be less than ${before}`);
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
