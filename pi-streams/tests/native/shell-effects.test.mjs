import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { native } from './helpers.mjs';

const { unresolvedEffects } = await native('dist/server/sessions/streamTransientRetry.js');
const cases = JSON.parse(readFileSync(new URL('../fixtures/shell-effects.json', import.meta.url), 'utf8'));

test('native unresolved effects match the shared exact-branch shell cases', () => {
    for (const item of cases) {
        const messages = [{ role: 'assistant', stopReason: 'toolUse', content: [{ type: 'toolCall', id: 'owned', name: 'bash', arguments: { command: item.command } }] }];
        if (item.result) messages.push(item.result);
        assert.equal(unresolvedEffects(messages.map(message => ({ value: { message } }))), item.unresolved, item.name);
    }
});
