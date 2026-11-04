import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import fs, { readFileSync, writeFileSync } from 'node:fs';
import { syncBuiltinESMExports } from 'node:module';
import { join } from 'node:path';
import test from 'node:test';
import { fixture, flush, native, response, errorResponse, provider } from './helpers.mjs';

const { CleanPolicyAnalyses } = await native('dist/server/sessions/cleanPolicyAnalysis.js');
const { assertFailureLifecycleFile } = await native('dist/server/sessions/sessionFailureBoundary.js');
const { PiSessionService } = await native('dist/server/sessions/piSessionService.js');
const { SessionManager } = await native('node_modules/@earendil-works/pi-coding-agent/dist/core/session-manager.js');
const hash = value => createHash('sha256').update(value).digest('hex');
const canary = 'BENIGN_REJECTED_CANARY_CLEAN_VIEW_12ab';
const captures = [], readCaptures = [];
async function setup(answer = response('The content-policy restriction leaves the original task blocked. Preserve its evidence.'), beforeProvider) {
    const f = await fixture([response('Verified checkpoint ' + canary), errorResponse('Request rejected by the content filter')], {}, { policy: 'enrolled-prefix-v1', enroll: { policyId: 'enrolled-prefix-v1', role: 'implementation', assignment: canary } });
    f.loader.getSystemPrompt = () => 'Original system ' + canary;
    await f.session.prompt('Original prefix ' + canary);
    await f.session.prompt('Rejected unit ' + canary);
    await flush();
    for (const path of ['AGENTS.md', 'STATE.md', 'handover.md', 'SYSTEM.md', '../AGENTS.md']) writeFileSync(join(f.dir, path), path + ' ' + canary);
    const boundary = f.boundaries.snapshot(f.session);
    const request = { id: 'metadata-only', basis: 'clean-policy-analysis-v1', blockedGoalSha256: hash(canary), expected: { ...boundary, generation: boundary.parking.generation } };
    const calls = [], attempts = [];
    const runtime = new Proxy(f.session.modelRuntime, { get(target, key) {
        if (key === 'streamSimple') return (model, context, options) => {
            const capture = { model: structuredClone(model), context: structuredClone(context), reasoning: options.reasoning };
            calls.push(capture); captures.push(capture);
            beforeProvider?.(f, request, attempts);
            return provider(answer);
        };
        const value = Reflect.get(target, key);
        return typeof value === 'function' ? value.bind(target) : value;
    } });
    const hooks = { modelRuntime: runtime, boundary: session => f.boundaries.snapshot(session), quiescent: () => {
        assert.equal(f.session.isStreaming, false);
        assert.equal(f.session.pendingMessageCount, 0);
    } };
    const directory = join(f.dir, 'private-analysis');
    const analyses = new CleanPolicyAnalyses(directory, f.control, hooks);
    return { f, request, calls, attempts, analyses, directory, hooks };
}

test('actual SDK factory excludes complete rejected prefix/system/resources and retains source bytes and model', async () => {
    const r = await setup();
    const original = readFileSync(r.f.manager.getSessionFile());
    const control = r.f.control.snapshot({ id: r.f.session.sessionId, cwd: r.f.dir });
    const restorations = [];
    for (const [target, name] of [[fs, 'readFileSync'], [fs, 'readFile'], [fs, 'openSync'], [fs.promises, 'readFile'], [fs.promises, 'open']]) {
        const original = target[name];
        target[name] = (...args) => { readCaptures.push({ operation: name, path: String(args[0]) }); return original(...args); };
        restorations.push(() => { target[name] = original; });
    }
    syncBuiltinESMExports();
    try {
        const [receipt, repeated] = await Promise.all([r.analyses.run(r.f.session, r.request), r.analyses.run(r.f.session, r.request)]);
        assert.deepEqual(repeated, receipt);
        assert.equal(receipt.state, 'analyzed', JSON.stringify(receipt));
        assert.equal(receipt.basis, 'clean-policy-analysis-v1');
        assert.equal(receipt.originalTaskBlocked, true);
        assert.equal(receipt.provider + '/' + receipt.model, 'openai-codex/gpt-6.1-sol');
        assert.equal(receipt.thinking, 'xhigh');
        assert.equal(r.f.session.model.provider + '/' + r.f.session.model.id, 'openai-codex/gpt-6.1-sol');
        assert.equal(r.f.session.thinkingLevel, 'xhigh');
        assert.notEqual(receipt.analysisSessionId, r.f.session.sessionId);
        assert.deepEqual(readFileSync(receipt.audit.retainedSource), original);
        assert.equal(receipt.audit.sourceSha256, hash(original));
        assert.deepEqual(readFileSync(r.f.manager.getSessionFile()), original);
        assert.deepEqual(r.f.control.snapshot({ id: r.f.session.sessionId, cwd: r.f.dir }), control);
        assert.equal(r.calls.length, 1);
        assert.equal(r.calls[0].reasoning, 'xhigh');
        assert.deepEqual(r.calls[0].context.tools, []);
        assert.equal(r.calls[0].context.messages.length, 1);
        assert(r.calls[0].context.systemPrompt.startsWith('You are an expert coding assistant operating inside pi'));
        assert(!JSON.stringify(r.calls).includes(canary));
        assert(!JSON.stringify(r.calls).includes(receipt.audit.sourceSha256));
        assert(!JSON.stringify(r.calls).includes(receipt.audit.sourceFile));
        assert.deepEqual(readCaptures.filter(read => /(?:AGENTS|STATE|handover|SYSTEM)\.md$/.test(read.path)), []);
        const physical = readFileSync(receipt.analysisFile, 'utf8');
        const observed = physical.match(/[^\n]*\n|[^\n]+$/g).find(raw => JSON.parse(raw).id === receipt.observation.entryId);
        assert.equal(hash(observed), receipt.observation.sha256);
        assert(!physical.includes(canary));
        assert(!physical.includes('compaction'));
        assert(!physical.includes('resume-observed'));
        const privateManager = SessionManager.open(receipt.analysisFile);
        assert.throws(() => assertFailureLifecycleFile(receipt.analysisFile, receipt.analysisSessionId, privateManager.getCwd()), /Private metadata analysis/);
        await assert.rejects(PiSessionService.prototype.createSessionRuntime.call({}, privateManager, privateManager.getCwd(), {}, {}), /Private metadata analysis cannot reopen/);
        assert.deepEqual(await r.analyses.run(r.f.session, r.request), receipt);
        assert.equal(r.calls.length, 1);
    } finally { restorations.forEach(restore => restore()); syncBuiltinESMExports(); r.f.session.dispose(); }
});

test('native absence of tools prevents read, shell, browser and delegated execution, with no follow-up inference', async () => {
    const tools = ['read', 'bash', 'web_search', 'subagent', 'fetch_content'];
    const message = { ...response('', 'toolUse'), content: tools.map((name, index) => ({ type: 'toolCall', id: 'attempt-' + index, name, arguments: { path: '/not-authorized/STATE.md', command: 'printf forbidden' } })) };
    const r = await setup(message);
    try {
        const result = await r.analyses.run(r.f.session, r.request);
        assert.equal(result.state, 'blocked');
        assert.deepEqual(result.toolAttempts.map(call => call.name), tools);
        assert.equal(r.calls.length, 1);
        const transcript = readFileSync(result.analysisFile, 'utf8');
        assert(transcript.includes('not found'));
        assert(!transcript.includes(canary));
        const cold = new CleanPolicyAnalyses(r.directory, r.f.control, r.hooks);
        assert.deepEqual(await cold.run(r.f.session, r.request), result);
        await assert.rejects(cold.run(r.f.session, { ...r.request, id: 'cosmetic-retry' }), /immutable analysis intent/);
        assert.equal(r.calls.length, 1);
    } finally { r.f.session.dispose(); }
});

test('rejected safe analysis remains durable across reopen and cannot be iterated under another ID', async () => {
    for (const answer of [errorResponse('Request rejected by the content filter'), response("I can't help analyze this request under the safety policy.")]) {
        const r = await setup(answer);
        try {
            const result = await r.analyses.run(r.f.session, r.request);
            assert.equal(result.state, 'rejected');
            assert.equal(result.originalTaskBlocked, true);
            const cold = new CleanPolicyAnalyses(r.directory, r.f.control, r.hooks);
            assert.deepEqual(await cold.run(r.f.session, r.request), result);
            await assert.rejects(cold.run(r.f.session, { ...r.request, id: 'other-analysis' }), /no iterative attempts/);
            const relabeled = structuredClone(r.f.boundaries.snapshot(r.f.session));
            relabeled.failure.kind = 'model-error';
            r.f.manager.appendCustomEntry('pi-web.stream-failure', relabeled);
            r.f.boundaries.records.set(r.f.session, relabeled);
            await assert.rejects(cold.run(r.f.session, { ...r.request, id: 'relabeled-retry', expected: { ...relabeled, generation: relabeled.parking.generation } }), /no iterative attempts/);
            assert.equal(r.calls.length, 1);
            assert(!JSON.stringify(r.calls).includes(canary));
        } finally { r.f.session.dispose(); }
    }
});

test('new stop and generation deny analysis before inference without changing the original', async () => {
    for (const allowed of [false, true]) {
        const r = await setup();
        const before = readFileSync(r.f.manager.getSessionFile());
        try {
            await r.f.control.setAllowed({ id: r.f.session.sessionId, cwd: r.f.dir }, allowed);
            await assert.rejects(r.analyses.run(r.f.session, r.request), /superseded clean analysis/);
            assert.equal(r.calls.length, 0);
            assert.deepEqual(readFileSync(r.f.manager.getSessionFile()), before);
        } finally { r.f.session.dispose(); }
    }
});

test('a concurrent stop or newly accepted source input invalidates the result without another inference', async () => {
    for (const kind of ['stop', 'input']) {
        let mutation;
        const r = await setup(response('Metadata analysis completed.'), f => {
            if (kind === 'stop') mutation = f.control.setAllowed({ id: f.session.sessionId, cwd: f.dir }, false);
            else f.manager.appendMessage({ role: 'user', content: 'New human input remains owned ' + canary, timestamp: Date.now() });
        });
        try {
            const result = await r.analyses.run(r.f.session, r.request);
            await mutation;
            assert.equal(result.state, 'superseded');
            assert.equal(r.calls.length, 1);
            assert(!JSON.stringify(r.calls).includes(canary));
            assert.equal(result.originalTaskBlocked, true);
        } finally { r.f.session.dispose(); }
    }
});

test('questions, callbacks and unknown effects stay fenced; a clean assertion cannot supply resources or task text', async () => {
    const r = await setup();
    try {
        await assert.rejects(r.analyses.run(r.f.session, { ...r.request, clean: true }), /caller content\/resources are forbidden/);
        for (const owner of ['question', 'queued input', 'callback']) {
            const blocked = new CleanPolicyAnalyses(r.directory, r.f.control, { ...r.hooks, quiescent: () => { throw Error('Unresolved ' + owner); } });
            await assert.rejects(blocked.run(r.f.session, r.request), /Unresolved/);
        }
        r.f.manager.appendMessage({ role: 'assistant', ...response('', 'toolUse'), content: [{ type: 'toolCall', id: 'unknown', name: 'bash', arguments: { command: 'opaque_job &' } }] });
        await assert.rejects(r.analyses.run(r.f.session, r.request), /unknown external effects/);
        assert.equal(r.calls.length, 0);
    } finally { r.f.session.dispose(); }
});

test('a lost running owner becomes durably uncertain rather than creating another metadata request', async () => {
    const r = await setup();
    try {
        const result = await r.analyses.run(r.f.session, r.request);
        const record = join(result.audit.retainedSource, '..', 'receipt.json');
        const interrupted = { ...result, state: 'running' };
        writeFileSync(record, JSON.stringify(interrupted));
        const cold = new CleanPolicyAnalyses(r.directory, r.f.control, r.hooks);
        const receipt = await cold.run(r.f.session, r.request);
        assert.equal(receipt.state, 'uncertain');
        assert.equal(JSON.parse(readFileSync(record)).state, 'uncertain');
        assert.equal(r.calls.length, 1);
    } finally { r.f.session.dispose(); }
});

test('complete provider contexts are retained for independent leak review, with compaction requests explicitly absent', () => {
    assert(captures.length >= 5);
    assert(captures.every(call => call.context.messages.length === 1 && call.context.tools.length === 0));
    assert(!JSON.stringify(captures).includes(canary));
    const evidence = { attemptedReads: readCaptures, contexts: captures, compactionContexts: captures.filter(call => call.context.systemPrompt.startsWith('You are a context summarization assistant')), compactionPermitted: false };
    assert.deepEqual(evidence.compactionContexts, []);
    if (process.env.POLICY_ANALYSIS_EVIDENCE) writeFileSync(process.env.POLICY_ANALYSIS_EVIDENCE, JSON.stringify(evidence, null, 2));
});
