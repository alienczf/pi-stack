import assert from 'node:assert/strict';
import { writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import test from 'node:test';
import { setTimeout as wait } from 'node:timers/promises';
import { fixture, flush, native, response } from './helpers.mjs';

const { PiSessionService } = await native('dist/server/sessions/piSessionService.js');
const { SessionControlGoalController } = await native('dist/server/sessions/sessionControlGoal.js');
const { expandPotetoInvocation } = await native('dist/server/sessions/potetoInvocation.js');
const { loadExtensionFromFactory, createExtensionRuntime } = await native('node_modules/@earendil-works/pi-coding-agent/dist/core/extensions/loader.js');
const { createEventBus } = await native('node_modules/@earendil-works/pi-coding-agent/dist/core/event-bus.js');
const sourceRoot = fileURLToPath(new URL('../../', import.meta.url));
const bridge = `
import hashlib, json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from engine import artifacts, blocked_goals, delivery, sessionlog
value = json.load(sys.stdin)
stream = Path(value['cwd'])
(stream / 'log').mkdir(exist_ok=True)
if not (stream / 'STATE.md').exists():
    (stream / 'STATE.md').write_text((Path(sys.argv[1]) / 'templates/stream/STATE.md').read_text().replace('ratified: no', 'ratified: 2026-11-03 Owned fixture confirmation'))
    (stream / 'stream.toml').write_text('project = "fixture"\\npi_stack_revision = "fixture"\\nstate_schema = 1\\n')
if value['action'] == 'prepare':
    checkpoint = sessionlog.control_checkpoint(Path(value['file']), value['sid'], value['cwd'], value['leaf'])
    delivery.prepare_control_locked(stream, value['id'], value['sid'], value['goal'], hashlib.sha256(value['goal'].encode()).hexdigest(), 'native-source', value['sequence'], value['token'])
    record = delivery._get(stream, value['id'])
    record.control.checkpoint = checkpoint
    delivery._save(stream, record)
else:
    record = delivery._get(stream, value['id'])
    record.state, record.control.state = 'transport_accepted', 'ended'
    delivery._save(stream, record)
    if value['acknowledge']:
        blocked_goals.receive(stream, value['goal'], 'delivery:' + value['id'], sent=value['id'])
    blocked_goals.observe(stream, value['goal'], value['sid'], value['file'], dispatch=value['id'], leaf=value['leaf'])
allowed = blocked_goals.permit(stream, value['goal'])
record = artifacts._read_tick_data(stream).get('blocked_goals', {}).get(blocked_goals.fingerprint(value['goal']), {})
print(json.dumps({'allowed': allowed, 'outcomes': record.get('outcomes', {})}))
`;

function source(f, request) {
    const input = { cwd: f.dir, sid: f.session.sessionId, file: f.manager.getSessionFile(), leaf: f.manager.getLeafId(), ...request };
    const result = spawnSync('python3', ['-c', bridge, sourceRoot], { input: JSON.stringify(input), encoding: 'utf8', env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' } });
    assert.equal(result.status, 0, result.stdout + result.stderr);
    return JSON.parse(result.stdout);
}

function serviceFor(f) {
    const skill = join(f.dir, 'poteto-mode.md');
    writeFileSync(skill, '---\nname: poteto-mode\ndescription: Owned fixture\n---\nPerform only the bounded authorized unit.');
    f.loader.getSkills = () => ({ skills: [{ name: 'poteto-mode', filePath: skill, baseDir: f.dir }] });
    const controller = new SessionControlGoalController(f.control, { current: () => true, maintenanceOwns: () => false, busy: session => session.isStreaming, humanInputPending: () => false, publish: () => {}, failure: (_session, text) => assert.fail(text), send: (session, text, goal) => session.prompt(expandPotetoInvocation(session, text, goal), { expandPromptTemplates: false }) });
    return { automaticAdmissionStore: f.control, controlGoals: controller, assertWritable: async () => {}, maintenanceSession: async () => f.session };
}

async function dispatch(f, service, goal, sequence, acknowledge = false) {
    const ref = { id: f.session.sessionId, cwd: f.dir };
    const token = { sessionId: ref.id, cwd: ref.cwd, generation: f.control.snapshot(ref).generation, kind: 'wake' };
    const id = 'handled-' + sequence;
    source(f, { action: 'prepare', id, goal, sequence, token });
    await PiSessionService.prototype.controlGoal.call(service, ref, { id, runId: 'native-source', sequence, text: '/poteto-mode ' + goal, potetoGoal: goal, automaticAdmission: token });
    const deadline = Date.now() + 5000;
    while (f.control.controlGoal(ref)?.state !== 'ended' && Date.now() < deadline) { await flush(); await wait(5); }
    assert.equal(f.control.controlGoal(ref).state, 'ended');
    return source(f, { action: 'observe', id, goal, acknowledge });
}

test('source observer ignores actual ended controls handled without inference and preserves blocked acknowledgements', async () => {
    for (const historical of ['Blocked. Missing the owned fixture dependency.', 'Completed the historical fixture and verified its artifact.']) {
        const goal = 'Review the bounded fixture unit';
        const f = await fixture([response(historical)]);
        try {
            await f.session.prompt(goal);
            const historicalLeaf = f.manager.getLeafId();
            const extensionPath = join(f.dir, 'handled-input.mjs');
            writeFileSync(extensionPath, 'export default function extension() {}');
            const extension = await loadExtensionFromFactory(pi => pi.on('input', () => ({ action: 'handled' })), f.dir, createEventBus(), createExtensionRuntime(), extensionPath);
            f.extensions.extensions.push(extension);
            f.session._buildRuntime({ activeToolNames: [], includeAllExtensionTools: false });
            const service = serviceFor(f);
            for (let sequence = 1; sequence <= 3; sequence++) {
                const acknowledged = historical.startsWith('Completed');
                const observed = await dispatch(f, service, goal, sequence, acknowledged);
                assert.equal(f.manager.getLeafId(), historicalLeaf);
                assert.equal(Object.values(observed.outcomes).filter(item => item.native).length, 0);
                assert.equal(Object.keys(observed.outcomes).length, acknowledged ? sequence : 0);
                assert.equal(observed.allowed, !(acknowledged && sequence === 3));
            }
            assert.equal(f.calls.length, 1);
            assert.equal(f.manager.getBranch().filter(entry => entry.message?.role === 'user').length, 1);
        } finally { f.session.dispose(); }
    }
});

test('source observer correlates real expanded turns for three-block suppression, progress reset and acknowledgement deduplication', async () => {
    for (const progress of [false, true]) {
        const answers = ['Blocked. Missing fixture dependency.', progress ? 'Installed and verified the authorized dependency.' : 'Blocked. Still missing fixture dependency.', 'Blocked. Missing fixture dependency.'];
        const f = await fixture([response('Historical work.'), ...answers.map(text => response(text))]);
        try {
            await f.session.prompt('Historical input.');
            const service = serviceFor(f);
            let observed;
            for (let sequence = 1; sequence <= 3; sequence++) observed = await dispatch(f, service, 'Review the bounded fixture unit', sequence, true);
            assert.equal(observed.allowed, progress);
            assert.equal(Object.keys(observed.outcomes).length, 3);
            assert.deepEqual(Object.values(observed.outcomes).map(item => item.state), progress ? ['blocked', 'progress', 'blocked'] : ['blocked', 'blocked', 'blocked']);
            assert.equal(new Set(Object.values(observed.outcomes).map(item => item.native.userEntryId)).size, 3);
            assert.equal(f.calls.length, 4);
        } finally { f.session.dispose(); }
    }
});
