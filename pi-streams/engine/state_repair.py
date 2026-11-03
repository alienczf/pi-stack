from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from engine import StreamsError, artifacts, clock, migration
from engine.project import _write, commit_repo, git, load_stream_config


def plan(stream: Path, prefix_bytes: int, *, at: str | None = None) -> dict:
    if stream.is_symlink() or load_stream_config(stream / 'stream.toml').state_schema != 1:
        raise StreamsError('Prefix repair requires an existing canonical stream')
    raw = migration.regular_bytes(stream / 'STATE.md')
    if type(prefix_bytes) is not int or not 0 < prefix_bytes < len(raw) or raw[prefix_bytes-1:prefix_bytes] != b'\n':
        raise StreamsError('Explicit history prefix must end at an exact line boundary')
    candidate = raw[prefix_bytes:]
    before = artifacts._read_tick_data(stream).get('state_log')
    if before is not None:
        if 'pending' in before:
            raise StreamsError('A pending Log operation owns canonical repair')
        artifacts._checked_state(candidate, artifacts._book(before))
    else:
        parsed = artifacts.parse_state(candidate)
        if candidate[parsed.log.body.start:]:
            raise StreamsError('Unregistered canonical Log requires an explicit source-backed migration, not prefix repair')
    timestamp = at or clock.stamp(clock.now())
    if clock.parse(timestamp) is None:
        raise StreamsError('Invalid repair timestamp')
    seed = {'version': 1, 'root': str(stream.resolve()), 'at': timestamp, 'prefixHistoryBytes': prefix_bytes, 'source': migration.encoded(raw), 'sourceSha256': migration.digest(raw), 'after': migration.encoded(candidate), 'afterSha256': migration.digest(candidate), 'book': before}
    identity = migration.digest(migration._json(seed).encode())
    return {**seed, 'id': identity, 'history': f'history/state-prefix-repair-{identity}.md'}


def apply_locked(stream: Path, document: dict | None) -> dict:
    if stream.is_symlink() or not (stream / '.git').is_dir() or (stream / '.git').is_symlink():
        raise StreamsError('Prefix repair requires its owned real stream repository')
    root = stream.resolve()
    journal = root / 'log/state-repair.json'
    if journal.parent.is_symlink():
        raise StreamsError('Prefix repair journal directory must be owned')
    operation = json.loads(migration.regular_bytes(journal)) if journal.exists() or journal.is_symlink() else None
    if operation is None:
        if document is None:
            raise StreamsError('No prefix repair to resume')
        fresh = plan(root, document.get('prefixHistoryBytes'), at=document.get('at'))
        if fresh != document:
            raise StreamsError('Prefix repair source or exact plan changed')
        if (root / 'history').is_symlink():
            raise StreamsError('Prefix repair history must be owned')
        paths = {'STATE.md', fresh['history']}
        if paths.intersection(git(root, 'diff', '--cached', '--name-only').splitlines()):
            raise StreamsError('Prefix repair overlaps foreign staged edits')
        operation = {'version': 1, 'root': str(root), 'plan': fresh, 'base_head': git(root, 'rev-parse', 'HEAD').strip(), 'message': f"pi-streams repair-state {root.name} {fresh['id']}", 'phase': 'history'}
        _save(root, operation)
    if not isinstance(operation, dict) or operation.get('version') != 1 or operation.get('root') != str(root) or operation.get('phase') not in {'history', 'state', 'commit', 'complete'}:
        raise StreamsError('Invalid prefix repair journal')
    saved = operation['plan']
    if document is not None and saved != document:
        raise StreamsError('Different prefix repair is already recorded')
    seed = {key: value for key, value in saved.items() if key not in {'id', 'history'}}
    if saved.get('root') != str(root) or migration.digest(migration._json(seed).encode()) != saved.get('id') or saved.get('history') != f"history/state-prefix-repair-{saved['id']}.md":
        raise StreamsError('Prefix repair journal plan identity changed')
    source, after = artifacts._decode_bytes(saved['source']), artifacts._decode_bytes(saved['after'])
    if migration.digest(source) != saved['sourceSha256'] or migration.digest(after) != saved['afterSha256'] or source[saved['prefixHistoryBytes']:] != after:
        raise StreamsError('Prefix repair source hashes changed')
    book = artifacts._book(saved['book']) if saved['book'] is not None else artifacts.LogBook()
    artifacts._checked_state(after, book)
    expected = {'STATE.md': after, saved['history']: source}
    phase = operation['phase']
    if phase == 'complete':
        if not migration._own_commit(root, operation, expected, operation['commit']):
            raise StreamsError('Prefix repair completion commit changed')
        return {'id': saved['id'], 'commit': operation['commit'], 'changed': False}
    actual = migration.regular_bytes(root / 'STATE.md')
    if actual not in ((source,) if phase == 'history' else (source, after) if phase == 'state' else (after,)):
        raise StreamsError('Newer STATE superseded prefix repair')
    history = root / saved['history']
    if (root / 'history').is_symlink() or history.is_symlink() or (phase != 'history' and not history.exists()) or (history.exists() and migration.regular_bytes(history) != source):
        raise StreamsError('Prefix repair retained source changed')
    data = artifacts._read_tick_data(root)
    if data.get('state_log') not in (saved['book'], asdict(book)):
        raise StreamsError('Newer Log ownership superseded prefix repair')
    head = git(root, 'rev-parse', 'HEAD').strip()
    if head != operation['base_head']:
        if phase != 'commit' or not migration._own_commit(root, operation, expected, head) or (root / '.git/index.lock').exists() or set(expected).intersection(git(root, 'diff', '--cached', '--name-only').splitlines()):
            raise StreamsError('Prefix repair Git parent changed')
        operation.update(phase='complete', commit=head)
        _save(root, operation)
        return {'id': saved['id'], 'commit': head, 'changed': False}
    if phase == 'history':
        _write(history, source.decode('utf-8'))
        operation['phase'] = 'state'
        _save(root, operation)
    if operation['phase'] == 'state':
        _write(root / 'STATE.md', after.decode('utf-8'))
        data['state_log'] = asdict(book)
        artifacts._save_tick_data(root, data)
        operation['phase'] = 'commit'
        _save(root, operation)
    if set(expected).intersection(git(root, 'diff', '--cached', '--name-only').splitlines()):
        raise StreamsError('Prefix repair overlaps newer staged edits')
    commit_repo(root, operation['message'], paths=tuple(expected), scope_only=True)
    committed = git(root, 'rev-parse', 'HEAD').strip()
    if not migration._own_commit(root, operation, expected, committed):
        raise StreamsError('Prefix repair scoped commit is unconfirmed')
    operation.update(phase='complete', commit=committed)
    _save(root, operation)
    return {'id': saved['id'], 'commit': committed, 'changed': True}


def _save(root: Path, operation: dict) -> None:
    _write(root / 'log/state-repair.json', json.dumps(operation, indent=2, sort_keys=True) + '\n')
