import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { clock, errorResponse, fixture, flush, native, response } from './helpers.mjs';

const { assertFailureLifecycleFile } = await native('dist/server/sessions/sessionFailureBoundary.js');

function receipts(f) { return f.manager.getBranch().filter(e => e.customType === 'pi-web.stream-retry').map(e => e.data); }
function event(session, type) { return new Promise(resolve => { const off = session.subscribe(value => { if (value.type === type) { off(); resolve(value); } }); }); }

test('watched AgentSession retries twice at fixed five seconds and cold lifecycle honors settlement', async () => {
    const f = await fixture([errorResponse('overloaded'), errorResponse('fetch failed'), response()]);
    const time = clock();
    try {
        const started = event(f.session, 'auto_retry_start');
        const run = f.session.prompt('Continue the bounded task');
        await started;
        await flush();
        assert.equal(f.calls.length, 1);
        assert.equal(f.boundaries.snapshot(f.session).state, 'watching');
        assert.deepEqual(time.delays(), [5000]);
        await time.advance(4999);
        assert.equal(f.calls.length, 1);
        const second = event(f.session, 'auto_retry_start');
        await time.advance(1);
        await second;
        assert.equal(f.calls.length, 2);
        assert.deepEqual(time.delays(), [5000]);
        await time.advance(5000);
        await run;
        assert.equal(f.calls.length, 3);
        assert.deepEqual(f.calls.map(c => [c.model.provider, c.model.id, c.options.reasoning]), Array(3).fill(['openai-codex', 'gpt-6.1-sol', 'xhigh']));
        assert.equal(f.boundaries.snapshot(f.session).state, 'watching');
        assert.equal(receipts(f).filter(e => e.state === 'resolved').length, 2);
        assertFailureLifecycleFile(f.manager.getSessionFile(), f.session.sessionId, f.dir);
        const { SessionManager } = await native('node_modules/@earendil-works/pi-coding-agent/dist/core/session-manager.js');
        const reopened = await fixture([], {}, { manager: SessionManager.open(f.manager.getSessionFile()), control: f.control, watch: false });
        reopened.boundaries.attach(reopened.session);
        await flush();
        assert.equal(reopened.boundaries.snapshot(reopened.session).state, 'watching');
        reopened.session.dispose();
        assert.equal(readFileSync(f.manager.getSessionFile(), 'utf8').includes('overloaded'), true);
        console.log(JSON.stringify({ scenario: 'retry', session: f.session.sessionId, file: f.manager.getSessionFile(), receipts: receipts(f) }));
    } finally { time.restore(); f.session.dispose(); }
});

test('all bundled transient classes remain eligible after usage exclusions', async () => {
    const { StreamTransientRetry } = await native('dist/server/sessions/streamTransientRetry.js');
    const f = await fixture();
    const policy = new StreamTransientRetry(f.session, f.control, () => [], () => true);
    for (const text of ['overloaded', 'rate limit', 'too many requests', '429', '500', '502', '503', '504', '524', 'service unavailable', 'server error', 'internal error', 'provider returned error', 'network error', 'connection error', 'connection refused', 'connection lost', 'other side closed', 'fetch failed', 'getaddrinfo', 'ENOTFOUND', 'EAI_AGAIN', 'upstream connect', 'reset before headers', 'socket hang up', 'socket connection was closed', 'timed out', 'timeout', 'terminated', 'websocket closed', 'websocket error', 'ended without', 'stream ended before message_stop', 'stream ended before a terminal response event', 'http2 request did not get a response', 'retry delay', 'you can retry your request', 'try your request again', 'please retry your request', 'ResourceExhausted'])
        assert.equal(policy.eligible(errorResponse(text)), true, text);
    f.session.dispose();
});

test('Codex usage codes and quota/billing never enter watched retry', async () => {
    for (const text of ['rate_limit_exceeded', 'usage_limit_reached', 'usage_not_included', 'ChatGPT usage limit', 'Codex usage limit', 'insufficient_quota 429', 'quota exceeded 503', 'billing 500', 'usage-limit 429', 'usage limit 503', 'usage_limit 429']) {
        const f = await fixture([errorResponse(text)]);
        await f.session.prompt('task');
        assert.equal(f.calls.length, 1, text);
        assert.equal(receipts(f).filter(e => e.state === 'pending').length, 0, text);
        f.session.dispose();
    }
});

test('a completed tool does not execute again during inference retry', async () => {
    let count = 0;
    const tool = { name: 'counter', label: 'Counter', description: 'Count once', parameters: { type: 'object', properties: {} }, execute: async () => ({ content: [{ type: 'text', text: String(++count) }], details: { status: 'completed' } }) };
    const call = { ...response('', 'toolUse'), content: [{ type: 'toolCall', id: 'call-1', name: 'counter', arguments: {} }] };
    const f = await fixture([call, errorResponse('503 overloaded'), response()], { counter: tool });
    const time = clock();
    try {
        const started = event(f.session, 'auto_retry_start');
        const run = f.session.prompt('Execute the counter once');
        await started;
        assert.equal(count, 1);
        await flush();
        await time.advance(5000);
        await run;
        assert.equal(count, 1);
        assert.equal(f.calls.length, 3);
        assert.equal(f.calls[2].context.messages.filter(message => message.role === 'toolResult').length, 1);
    } finally { time.restore(); f.session.dispose(); }
});

test('lost live retry ownership and corrupt settlement refuse cold lifecycle', async () => {
    const f = await fixture([errorResponse('overloaded'), response()]);
    const time = clock();
    try {
        const started = event(f.session, 'auto_retry_start');
        const run = f.session.prompt('task');
        await started;
        assert.throws(() => assertFailureLifecycleFile(f.manager.getSessionFile(), f.session.sessionId, f.dir), /settlement/);
        await flush();
        await time.advance(5000);
        await run;
        const settled = structuredClone(receipts(f).at(-1));
        settled.completion.sha256 = '0'.repeat(64);
        f.manager.appendCustomEntry('pi-web.stream-retry', settled);
        assert.throws(() => assertFailureLifecycleFile(f.manager.getSessionFile(), f.session.sessionId, f.dir), /settlement|completion/);
    } finally { time.restore(); f.session.dispose(); }
});

test('cold reattachment durably marks an orphaned scheduled retry uncertain instead of recreating a timer', async () => {
    const f = await fixture();
    const failed = errorResponse('overloaded');
    const entry = f.manager.appendMessage(failed);
    await f.session._runtimeRetryPolicy.messageEnded(failed, entry);
    assert.equal(receipts(f).at(-1).state, 'pending');
    f.session.dispose();
    const { SessionManager } = await native('node_modules/@earendil-works/pi-coding-agent/dist/core/session-manager.js');
    const reopened = await fixture([], {}, { manager: SessionManager.open(f.manager.getSessionFile()), control: f.control, watch: false });
    reopened.boundaries.attach(reopened.session);
    await flush();
    assert.equal(receipts(reopened).at(-1).state, 'uncertain');
    assert.equal(reopened.boundaries.snapshot(reopened.session).state, 'uncertain');
    assert.equal(reopened.calls.length, 0);
    reopened.session.dispose();
});

test('configured retry count exhausts into one exact terminal boundary without increasing the count', async () => {
    const f = await fixture(Array.from({ length: 4 }, () => errorResponse('503 overloaded')));
    const time = clock();
    try {
        let scheduled = event(f.session, 'auto_retry_start');
        const run = f.session.prompt('task');
        await scheduled;
        for (let attempt = 1; attempt <= 3; attempt++) {
            await flush();
            assert.deepEqual(time.delays(), [5000]);
            if (attempt < 3) scheduled = event(f.session, 'auto_retry_start');
            await time.advance(5000);
            if (attempt < 3) await scheduled;
        }
        await run;
        assert.equal(f.calls.length, 4);
        assert.equal(receipts(f).at(-1).state, 'terminal');
        assert.equal(f.boundaries.snapshot(f.session).state, 'parked');
    } finally { time.restore(); f.session.dispose(); }
});

test('unresolved external jobs and unclassified shell submissions are not retried', async () => {
    for (const details of [{ jobId: 'fixture-job', status: 'unknown' }, { exitCode: 0 }]) {
        let submitted = 0;
        const tool = { name: 'bash', label: 'Controlled submission', description: 'No real shell', parameters: { type: 'object', properties: { command: { type: 'string' } } }, execute: async () => ({ content: [{ type: 'text', text: 'Controlled job result ' + ++submitted }], details }) };
        const call = { ...response('', 'toolUse'), content: [{ type: 'toolCall', id: 'submission', name: 'bash', arguments: { command: 'sbatch fixture-job' } }] };
        const f = await fixture([call, errorResponse('503 overloaded')], { bash: tool });
        await f.session.prompt('Inspect the controlled submission');
        assert.equal(submitted, 1);
        assert.equal(f.calls.length, 2);
        assert.equal(receipts(f).length, 0);
        assert.equal(f.boundaries.snapshot(f.session).state, 'parked');
        f.session.dispose();
    }
});

test('unwatched sessions retain their configured exponential retry delays', async () => {
    const f = await fixture([errorResponse('overloaded'), errorResponse('overloaded'), response()], {}, { watch: false });
    const time = clock();
    try {
        let scheduled = event(f.session, 'auto_retry_start');
        const run = f.session.prompt('task');
        await scheduled; await flush();
        assert.deepEqual(time.delays(), [2000]);
        scheduled = event(f.session, 'auto_retry_start');
        await time.advance(2000); await scheduled; await flush();
        assert.deepEqual(time.delays(), [4000]);
        await time.advance(4000); await run;
        assert.equal(f.calls.length, 3);
        assert.equal(receipts(f).length, 0);
    } finally { time.restore(); f.session.dispose(); }
});

test('stop generation and accepted input win the retry deadline', async () => {
    for (const action of ['stop', 'input', 'identity', 'abort']) {
        const f = await fixture([errorResponse('503 overloaded')]);
        const time = clock();
        try {
            const started = event(f.session, 'auto_retry_start');
            const run = f.session.prompt('task');
            await started;
            await flush();
            if (action === 'stop') await f.control.setAllowed({ id: f.session.sessionId, cwd: f.dir }, false);
            if (action === 'input') await f.control.explicitInput({ id: f.session.sessionId, cwd: f.dir });
            if (action === 'identity') f.session.agent.state.thinkingLevel = 'off';
            if (action === 'abort') f.session.abortRetry();
            await time.advance(5000);
            await run;
            assert.equal(f.calls.length, 1, action);
            assert.equal(receipts(f).at(-1).state, 'cancelled', action);
        } finally { time.restore(); f.session.dispose(); }
    }
});
