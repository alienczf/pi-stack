import assert from 'node:assert/strict';
import { existsSync, mkdtempSync, readFileSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import test from 'node:test';

const root = resolve(process.env.PI_STACK_NATIVE_TEST_ROOT ?? '');
assert(root.includes('/.harness-heal/'), 'use an explicit disposable native fixture');
const { SessionArchiveStore } = await import(pathToFileURL(join(root, 'dist/server/sessions/sessionArchiveStore.js')).href);

function fixture(t, archived) {
    const directory = mkdtempSync(join(process.env.TMPDIR, 'archive-retention-'));
    t.after(() => rmSync(directory, { recursive: true, force: true }));
    const source = join(directory, 'source.jsonl');
    const destination = join(directory, 'archive', 'source.jsonl');
    writeFileSync(source, 'Complete current source bytes.\n');
    mkdirSync(join(directory, 'archive'));
    writeFileSync(destination, archived);
    const store = new SessionArchiveStore(join(directory, 'archives.json'), join(directory, 'archive'));
    const input = { sessionId: 'retired', cwd: directory, path: source, created: '2026-11-07T00:00:00Z', modified: '2026-11-07T00:01:00Z', messageCount: 2, firstMessage: 'Owned fixture' };
    return { store, input, source, destination };
}

test('archive refuses different existing bytes before removing the live source', async t => {
    const { store, input, source, destination } = fixture(t, 'Earlier incomplete archive bytes.\n');
    await assert.rejects(store.archive(input), /archive.*differ|differ.*archive/i);
    assert.equal(readFileSync(source, 'utf8'), 'Complete current source bytes.\n');
    assert.equal(readFileSync(destination, 'utf8'), 'Earlier incomplete archive bytes.\n');
    assert.deepEqual(await store.list(), []);
});

test('archive reconciles identical bytes and retains the exact source', async t => {
    const { store, input, source, destination } = fixture(t, 'Complete current source bytes.\n');
    const record = await store.archive(input);
    assert.equal(record.sessionId, 'retired');
    assert.equal(record.archivePath, destination);
    assert.equal(existsSync(source), false);
    assert.equal(readFileSync(destination, 'utf8'), 'Complete current source bytes.\n');
    assert.equal((await store.list())[0].sessionId, 'retired');
});
