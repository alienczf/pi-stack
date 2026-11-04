import assert from 'node:assert/strict';
import test from 'node:test';
import { fixture, native, response } from './helpers.mjs';

const { PiSessionService } = await native('dist/server/sessions/piSessionService.js');
function service(f) {
    const host = { subsessionChildren: new Map(), activeRuntimeForSession: () => ({ services: { resourceLoader: { getExtensions: () => f.extensions } } }), isCurrentActiveSession: () => true, isSessionEntryMutationActive: () => false, compactionQueuedMessages: () => [], pendingAskStore: { pendingAsk: () => undefined }, pendingExtensionDialogStore: { pendingDialogs: () => [] } };
    host.rotationSafety = session => PiSessionService.prototype.rotationSafety.call(host, session);
    return host;
}

test('native replacement accepts a complete ordinary turn without a rotation acknowledgement', async () => {
    const f = await fixture([response('A normal completed turn')]);
    await f.session.prompt('Bounded task');
    assert.doesNotThrow(() => PiSessionService.prototype.assertReplacementCheckpoint.call(service(f), f.session, f.manager.getLeafId()));
    f.session.dispose();
});

test('native replacement retains an unclassified external shell submission', async () => {
    const f = await fixture();
    f.manager.appendMessage({ ...response('', 'toolUse'), content: [{ type: 'toolCall', id: 'submitted', name: 'bash', arguments: { command: 'sbatch controlled-job' } }] });
    f.manager.appendMessage({ role: 'toolResult', toolCallId: 'submitted', toolName: 'bash', content: [{ type: 'text', text: 'Submitted, not reconciled' }], details: { exitCode: 0 }, timestamp: Date.now() });
    assert.throws(() => PiSessionService.prototype.assertReplacementCheckpoint.call(service(f), f.session, f.manager.getLeafId()), /unresolved external effects/);
    f.session.dispose();
});
