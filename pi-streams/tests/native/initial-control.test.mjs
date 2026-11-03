import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import test from 'node:test';
import { errorResponse, fixture, flush, native, response } from './helpers.mjs';

const { AutomaticAdmissionStore } = await native('dist/server/sessions/automaticAdmissionStore.js');
const { PiSessionService } = await native('dist/server/sessions/piSessionService.js');
const { SessionControlGoalController } = await native('dist/server/sessions/sessionControlGoal.js');
const { registerSessionRoutes } = await native('dist/server/sessions/sessionRoutes.js');
const { default: Fastify } = await native('node_modules/fastify/fastify.js');

function storeFixture() {
    const cwd = mkdtempSync(join(process.env.TMPDIR, 'initial-control-'));
    return { ref: { id: 'legacy-coordinator', cwd }, store: new AutomaticAdmissionStore(join(cwd, 'controls')) };
}

async function api(t) {
    const f = await fixture([], {}, { watch: false });
    t.after(() => f.session.dispose());
    const ref = { id: f.session.sessionId, cwd: f.dir };
    const store = new AutomaticAdmissionStore(join(f.dir, 'legacy-controls'));
    const service = {
        automaticAdmissionStore: store,
        automaticControlIdentity: async lookup => { assert.equal(lookup, ref.id); return ref; },
        assertWritable: async () => {},
        failureBoundaries: f.boundaries,
        getOrOpen: async () => f.session,
        activeForLookup: () => ({ runtime: { session: f.session } }),
        controlGoals: new SessionControlGoalController(store, {
            current: () => true, busy: () => false, humanInputPending: () => false, maintenanceOwns: () => false,
            send: async (session, text) => session.prompt(text), publish: () => {}, failure: () => {},
        }),
    };
    service.setAutomaticAdmission = (...args) => PiSessionService.prototype.setAutomaticAdmission.call(service, ...args);
    const app = Fastify();
    registerSessionRoutes(app, service, {}, '/api');
    t.after(() => app.close());
    const request = (payload, initialize = payload.initializeIfAbsent !== undefined) => app.inject({ method: 'POST', url: `/api/sessions/${ref.id}/automatic-admission${initialize ? '/initialize' : ''}`, payload });
    return { f, ref, store, request };
}

const bootstrap = { allowed: true, initializeIfAbsent: true };

test('ordinary generation CAS cannot infer initial authority from unarmed or trust labels', async t => {
    const { store, ref, request } = await api(t);
    const result = await request({ allowed: true, expectedGeneration: 'unarmed', trust: 'ratified', authority: 'human' });
    assert.equal(result.statusCode, 409);
    assert.deepEqual(store.snapshot(ref), { sessionId: ref.id, cwd: ref.cwd, generation: 'unarmed', allowed: false, durable: false });
});

test('explicit absent-only API creates a durable initial epoch without inference, queue clearing or model changes', async t => {
    const { f, store, ref, request } = await api(t);
    await f.session.steer('Retain the unanswered bounded instruction.');
    await f.boundaries.watch(f.session, { stream: 'fixture', root: f.dir });
    const branch = structuredClone(f.manager.getBranch());
    const queue = [...f.session.getSteeringMessages()];
    const result = await request(bootstrap);
    assert.equal(result.statusCode, 200, result.body);
    const state = result.json();
    assert.deepEqual(state, { sessionId: ref.id, cwd: ref.cwd, generation: state.generation, allowed: true, durable: true });
    assert.notEqual(state.generation, 'unarmed');
    assert.deepEqual(new AutomaticAdmissionStore(store.directory).snapshot(ref), state);
    assert.deepEqual(f.manager.getBranch(), branch);
    assert.deepEqual(f.session.getSteeringMessages(), queue);
    assert.equal(f.session.model.id, 'gpt-6.1-sol');
    assert.equal(f.session.model.provider, 'openai-codex');
    assert.equal(f.session.thinkingLevel, 'xhigh');
    assert.equal(f.calls.length, 0);
});

test('absent-only initialization is idempotent after retries and cold reopen', async () => {
    const { store, ref } = storeFixture();
    const first = await store.initializeIfAbsent(ref);
    const bytes = readFileSync(store.file(ref), 'utf8');
    assert.deepEqual(await store.initializeIfAbsent(ref), first);
    assert.deepEqual(await new AutomaticAdmissionStore(store.directory).initializeIfAbsent(ref), first);
    assert.equal(readFileSync(store.file(ref), 'utf8'), bytes);
    assert.equal(first.allowed, true);
    assert.equal(first.durable, true);
});

test('concurrent first initializers converge on one durable receiving epoch', async () => {
    const { store, ref } = storeFixture();
    const reopened = new AutomaticAdmissionStore(store.directory);
    assert.equal(store.snapshot(ref).generation, 'unarmed');
    assert.equal(reopened.snapshot(ref).generation, 'unarmed');
    const states = await Promise.all([store.initializeIfAbsent(ref), reopened.initializeIfAbsent(ref), store.initializeIfAbsent(ref)]);
    assert.equal(states[0].allowed, true);
    assert.equal(states[0].durable, true);
    assert.deepEqual(states[1], states[0]);
    assert.deepEqual(states[2], states[0]);
    assert.deepEqual(new AutomaticAdmissionStore(store.directory).snapshot(ref), states[0]);
});

test('bootstrap preserves a genuine disabled durable generation and its bytes', async t => {
    const { store, ref, request } = await api(t);
    const stopped = await store.setAllowed(ref, false);
    const bytes = readFileSync(store.file(ref), 'utf8');
    const result = await request(bootstrap);
    assert.equal(result.statusCode, 200);
    assert.deepEqual(result.json(), stopped);
    assert.equal(stopped.allowed, false);
    assert.equal(readFileSync(store.file(ref), 'utf8'), bytes);
});

test('bootstrap preserves an existing allowed generation and queued goal without implicitly dispatching it', async t => {
    const { f, store, ref, request } = await api(t);
    const state = await store.initialize(ref);
    const goal = { version: 1, sessionId: ref.id, cwd: ref.cwd, id: 'retained', runId: 'existing-run', sequence: 1, text: '/poteto-mode Keep current authorized work.', potetoGoal: 'Keep current authorized work.', state: 'queued', automaticAdmission: { sessionId: ref.id, cwd: ref.cwd, generation: state.generation, kind: 'wake' } };
    await store.saveControlGoal(ref, goal);
    f.responses.push(response('This queued input must not run during bootstrap.'));
    const result = await request(bootstrap);
    await new Promise(resolve => setTimeout(resolve, 100));
    await flush();
    assert.equal(result.statusCode, 200);
    assert.deepEqual(result.json(), state);
    assert.deepEqual(store.controlGoal(ref), goal);
    assert.equal(f.calls.length, 0);
});

test('a stop queued before bootstrap wins without changing its durable generation', async () => {
    const { store, ref } = storeFixture();
    const stopping = store.setAllowed(ref, false);
    const initializing = store.initializeIfAbsent(ref);
    const stopped = await stopping;
    assert.deepEqual(await initializing, stopped);
    assert.equal(store.snapshot(ref).allowed, false);
});

test('a stop concurrent with initial publication prevents an allowed bootstrap receipt', async () => {
    const { store, ref } = storeFixture();
    const persist = store.persist.bind(store);
    let entered, release;
    const started = new Promise(resolve => { entered = resolve; });
    const gate = new Promise(resolve => { release = resolve; });
    store.persist = async (...args) => { entered(); await gate; return persist(...args); };
    const initializing = store.initializeIfAbsent(ref);
    await started;
    const stopping = store.setAllowed(ref, false);
    release();
    const initial = await initializing;
    const stopped = await stopping;
    assert.equal(initial.allowed, false);
    assert.equal(initial.durable, true);
    assert.deepEqual(new AutomaticAdmissionStore(store.directory).snapshot(ref), stopped);
    assert.equal(stopped.allowed, false);
    assert.notEqual(stopped.generation, initial.generation);
});

test('a later genuine stop invalidates the initial token and bootstrap cannot rearm it', async () => {
    const { store, ref } = storeFixture();
    const initial = await store.initializeIfAbsent(ref);
    const stopped = await store.setAllowed(ref, false);
    assert.throws(() => store.assertCurrent(ref, { sessionId: ref.id, cwd: ref.cwd, generation: initial.generation, kind: 'wake' }), /stale, disabled or not durable/);
    assert.deepEqual(await store.initializeIfAbsent(ref), stopped);
    assert.equal(stopped.allowed, false);
});

test('cached absence cannot overwrite a stop published by a reopened receiver', async () => {
    const { store, ref } = storeFixture();
    assert.equal(store.snapshot(ref).generation, 'unarmed');
    const stopped = await new AutomaticAdmissionStore(store.directory).setAllowed(ref, false);
    assert.deepEqual(await store.initializeIfAbsent(ref), stopped);
    assert.deepEqual(new AutomaticAdmissionStore(store.directory).snapshot(ref), stopped);
});

test('bootstrap observes a persisted stop instead of returning a stale cached allowed epoch', async () => {
    const { store, ref } = storeFixture();
    const initial = await store.initialize(ref);
    const stopped = await new AutomaticAdmissionStore(store.directory).setAllowed(ref, false);
    assert.notEqual(stopped.generation, initial.generation);
    assert.deepEqual(await store.initializeIfAbsent(ref), stopped);
    assert.equal(store.snapshot(ref).allowed, false);
});

test('filesystem absent CAS preserves a stop arriving after the initial absence check', async () => {
    const { store, ref } = storeFixture();
    const persist = store.persist.bind(store);
    let entered, release;
    const started = new Promise(resolve => { entered = resolve; });
    const gate = new Promise(resolve => { release = resolve; });
    store.persist = async (...args) => { entered(); await gate; return persist(...args); };
    const initializing = store.initializeIfAbsent(ref);
    await started;
    const stopped = await new AutomaticAdmissionStore(store.directory).setAllowed(ref, false);
    release();
    assert.deepEqual(await initializing, stopped);
    assert.equal(stopped.allowed, false);
    assert.deepEqual(new AutomaticAdmissionStore(store.directory).snapshot(ref), stopped);
});

test('an unavailable durable store cannot issue an initial allowed receipt', async () => {
    const { ref } = storeFixture();
    const store = new AutomaticAdmissionStore();
    await assert.rejects(store.initializeIfAbsent(ref), /durable|Durable/);
    assert.deepEqual(store.snapshot(ref), { sessionId: ref.id, cwd: ref.cwd, generation: 'unarmed', allowed: false, durable: false });
});

test('failed publication cannot be retried as proof that no prior epoch exists', async () => {
    const { ref } = storeFixture();
    const file = join(ref.cwd, 'not-a-directory');
    writeFileSync(file, 'retained');
    const store = new AutomaticAdmissionStore(file);
    await assert.rejects(store.initializeIfAbsent(ref));
    await assert.rejects(store.initializeIfAbsent(ref));
    assert.equal(readFileSync(file, 'utf8'), 'retained');
});

test('invalid bootstrap unions refuse before publishing any admission', async t => {
    const { store, ref, request } = await api(t);
    for (const payload of [
        { allowed: false, initializeIfAbsent: true },
        { ...bootstrap, expectedGeneration: 'unarmed' },
        { allowed: true, initializeIfAbsent: 'ratified' },
        { allowed: true, initializeIfAbsent: false },
    ]) {
        const result = await request(payload);
        assert.equal(result.statusCode, 409, result.body);
        assert.deepEqual(store.snapshot(ref), { sessionId: ref.id, cwd: ref.cwd, generation: 'unarmed', allowed: false, durable: false });
    }
});

test('bootstrap fields cannot fall through to ordinary unconditional rearming', async t => {
    const { store, ref, request } = await api(t);
    const stopped = await store.setAllowed(ref, false);
    const result = await request(bootstrap, false);
    assert.equal(result.statusCode, 409);
    assert.deepEqual(store.snapshot(ref), stopped);
    assert.equal(stopped.allowed, false);
});

test('parked historical workers cannot be revived through the initial-control API', async t => {
    const { f, store, ref, request } = await api(t);
    await f.boundaries.watch(f.session, { stream: 'fixture', root: f.dir });
    f.manager.appendMessage(errorResponse('Codex login expired'));
    await f.boundaries.observe(f.session);
    assert.equal(f.boundaries.snapshot(f.session).state, 'parked');
    const result = await request(bootstrap);
    assert.equal(result.statusCode, 409, result.body);
    assert.deepEqual(store.snapshot(ref), { sessionId: ref.id, cwd: ref.cwd, generation: 'unarmed', allowed: false, durable: false });
    assert.equal(f.calls.length, 0);
});
