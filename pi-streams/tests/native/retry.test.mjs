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
    for (const text of ['rate_limit_exceeded', 'usage_limit_reached', 'usage_not_included', 'ChatGPT usage limit', 'Codex usage limit', 'insufficient_quota 429', 'quota exceeded 503', 'billing 500']) {
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
