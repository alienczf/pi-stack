import assert from 'node:assert/strict';
import { resolve } from 'node:path';
import test from 'node:test';
import { fixture, native, root } from './helpers.mjs';

const { loadExtensions } = await native('node_modules/@earendil-works/pi-coding-agent/dist/core/extensions/loader.js');
const { createEventBus } = await native('node_modules/@earendil-works/pi-coding-agent/dist/core/event-bus.js');
const { callbackInventory } = await native('dist/server/sessions/extensionCallbackOwnership.js');

test('disabled subagent child entry declares no callback owner without loading parent machinery', async () => {
    process.env.PI_SUBAGENT_CHILD = '1';
    const f = await fixture();
    try {
        const loaded = await loadExtensions([resolve(root, '../extensions/pi-subagents/index.ts')], f.dir, createEventBus(), f.extensions.runtime);
        assert.deepEqual(loaded.errors, []);
        assert.equal(callbackInventory(loaded).known, true);
        assert.deepEqual(callbackInventory(loaded).owners.map(owner => [owner.kind, owner.revision, owner.owners]), [['none', 'child-disabled', []]]);
        assert.equal(loaded.extensions[0].tools.size, 0);
    } finally { f.session.dispose(); delete process.env.PI_SUBAGENT_CHILD; }
});
