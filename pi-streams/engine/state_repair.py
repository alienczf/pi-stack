from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import re
from typing import Literal

from engine import StreamsError, artifacts, clock, migration
from engine.project import _write, commit_repo, git, load_stream_config


PrefixTarget = Literal['history', 'rules']
RepairTarget = Literal['history', 'rules', 'sections']


def _candidate(raw: bytes, prefix_bytes: int, target: PrefixTarget, before: dict | None) -> bytes:
    if target not in {'history', 'rules'}:
        raise StreamsError('Prefix repair requires an explicit history or rules classification')
    try:
        raw.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise StreamsError('Prefix repair source is not valid UTF-8') from exc
    if b'\0' in raw:
        raise StreamsError('Prefix repair source contains a NUL byte')
    if type(prefix_bytes) is not int or not 0 < prefix_bytes < len(raw) or raw[prefix_bytes-1:prefix_bytes] != b'\n':
        raise StreamsError('Explicit prefix must end at an exact UTF-8 line boundary')
    candidate = raw[prefix_bytes:]
    if before is not None:
        if 'pending' in before:
            raise StreamsError('A pending Log operation owns canonical repair')
        book = artifacts._book(before)
        parsed = artifacts._checked_state(candidate, book)
    else:
        book = artifacts.LogBook()
        parsed = artifacts.parse_state(candidate)
        if candidate[parsed.log.body.start:]:
            raise StreamsError('Unregistered canonical Log requires an explicit source-backed migration, not prefix repair')
    if target == 'rules':
        prefix = raw[:prefix_bytes]
        if not prefix.decode('utf-8').strip():
            raise StreamsError('Active Rules prefix must not be empty')
        fence = b'`' * (max([2, *(len(run) for run in re.findall(rb'`+', prefix))]) + 1)
        projection = b'Retained active Rules from the STATE prefix.\n\n' + fence + b'text\n' + prefix + fence + b'\n\n'
        offset = parsed.rules.body.start
        candidate = candidate[:offset] + projection + candidate[offset:]
    artifacts._checked_state(candidate, book)
    return candidate


def _disposition(document: dict) -> tuple[int, PrefixTarget]:
    if document.get('version') == 1 and type(document.get('version')) is int and 'prefixDisposition' not in document:
        return document.get('prefixHistoryBytes'), 'history'
    disposition = document.get('prefixDisposition')
    if (type(document.get('version')) is not int or document['version'] != 2 or 'prefixHistoryBytes' in document
            or not isinstance(disposition, dict) or set(disposition) != {'bytes', 'target'}
            or disposition['target'] not in ('history', 'rules')):
        raise StreamsError('Invalid explicit prefix disposition')
    return disposition['bytes'], disposition['target']


def _sections_candidate(raw: bytes, before: dict | None) -> bytes:
    book = artifacts._book(before) if before is not None else artifacts.LogBook()
    if before is not None and before.get('pending') is not None:
        raise StreamsError('A pending Log operation owns canonical repair')
    try:
        artifacts._checked_state(raw, book)
    except StreamsError as invalid:
        try:
            raw.decode('utf-8')
        except UnicodeDecodeError:
            raise invalid
        size = book.entries[-1].end if book.entries else 0
        headings = artifacts._headings(raw[:len(raw) - size])
        top = [heading for heading in headings if heading.level == 2]
        names = [heading.name for heading in top]
        if (b'\0' in raw or size > len(raw) or any(names.count(name) != 1 for name in ('Goals', 'Rules', 'Log'))
                or names[:2] != ['Goals', 'Rules'] or names[-1] != 'Log'
                or raw[:top[0].span.start].strip() or len(set(names)) == len(names) and all(names)):
            raise invalid
    else:
        return raw
    unnamed = 'Retained unnamed sections'
    while unnamed in names:
        unnamed += ' (retained)'
    groups: dict[str, list[tuple[str, bytes]]] = {}
    for index in range(2, len(top) - 1):
        heading = top[index]
        content = raw[heading.span.start:top[index + 1].span.start]
        groups.setdefault(heading.name or unnamed, []).append((heading.name, content))
    extras = []
    for name, sections in groups.items():
        if len(sections) == 1 and sections[0][0]:
            extras.append(sections[0][1])
        else:
            extras.append(f'## {name}\n'.encode() + b''.join(re.sub(rb'^( {0,3})##', rb'\1###', content, count=1) for _, content in sections))
    candidate = raw[:top[2].span.start] + b''.join(extras) + raw[top[-1].span.start:]
    artifacts._checked_state(candidate, book)
    return candidate


def plan(stream: Path, prefix_bytes: int, *, target: RepairTarget = 'history', at: str | None = None, version: int = 2) -> dict:
    if stream.is_symlink() or load_stream_config(stream / 'stream.toml').state_schema != 1:
        raise StreamsError('Prefix repair requires an existing canonical stream')
    raw = migration.regular_bytes(stream / 'STATE.md')
    before = artifacts._read_tick_data(stream).get('state_log')
    candidate = _sections_candidate(raw, before) if target == 'sections' else _candidate(raw, prefix_bytes, target, before)
    timestamp = at or clock.stamp(clock.now())
    if clock.parse(timestamp) is None:
        raise StreamsError('Invalid repair timestamp')
    if version == 1 and target == 'history':
        classification = {'prefixHistoryBytes': prefix_bytes}
    elif version == 2 and target != 'sections':
        classification = {'prefixDisposition': {'bytes': prefix_bytes, 'target': target}, 'sourceGitHead': git(stream, 'rev-parse', 'HEAD').strip()}
    elif version == 3 and target == 'sections' and prefix_bytes == 0:
        classification = {'sectionDisposition': 'merge-extras', 'sourceGitHead': git(stream, 'rev-parse', 'HEAD').strip()}
    else:
        raise StreamsError('Invalid prefix repair version')
    seed = {'version': version, 'root': str(stream.resolve()), 'at': timestamp, **classification, 'source': migration.encoded(raw), 'sourceSha256': migration.digest(raw), 'after': migration.encoded(candidate), 'afterSha256': migration.digest(candidate), 'book': before}
    identity = migration.digest(migration._json(seed).encode())
    kind = 'sections' if version == 3 else 'prefix'
    return {**seed, 'id': identity, 'history': f'history/state-{kind}-repair-{identity}.md'}


def heal_sections_locked(stream: Path) -> None:
    if load_stream_config(stream / 'stream.toml').state_schema != 1:
        return
    journal = stream / 'log/state-sections-repair.json'
    if journal.exists() or journal.is_symlink():
        operation = json.loads(migration.regular_bytes(journal))
        if (not isinstance(operation, dict) or operation.get('version') != 1
                or operation.get('root') != str(stream.resolve()) or operation.get('phase') != 'complete'):
            apply_locked(stream, None, sections=True)
    raw = migration.regular_bytes(stream / 'STATE.md')
    before = artifacts._read_tick_data(stream).get('state_log')
    if isinstance(before, dict) and before.get('pending') is not None:
        return
    if _sections_candidate(raw, before) != raw:
        apply_locked(stream, plan(stream, 0, target='sections', version=3), sections=True)


def apply_locked(stream: Path, document: dict | None, *, sections: bool = False) -> dict:
    if stream.is_symlink() or not (stream / '.git').is_dir() or (stream / '.git').is_symlink():
        raise StreamsError('Prefix repair requires its owned real stream repository')
    root = stream.resolve()
    journal = root / ('log/state-sections-repair.json' if sections else 'log/state-repair.json')
    if journal.parent.is_symlink():
        raise StreamsError('Prefix repair journal directory must be owned')
    operation = json.loads(migration.regular_bytes(journal)) if journal.exists() or journal.is_symlink() else None
    if sections and isinstance(operation, dict) and operation.get('phase') == 'complete' and document is not None and operation.get('plan') != document:
        apply_locked(root, None, sections=True)
        operation = None
    if operation is None:
        if document is None:
            raise StreamsError('No prefix repair to resume')
        prefix_bytes, target = (0, 'sections') if sections else _disposition(document)
        fresh = plan(root, prefix_bytes, target=target, at=document.get('at'), version=document['version'])
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
    if (saved.get('version') == 3) != sections:
        raise StreamsError('Canonical repair journal kind changed')
    if document is not None and saved != document:
        raise StreamsError('Different prefix repair is already recorded')
    seed = {key: value for key, value in saved.items() if key not in {'id', 'history'}}
    kind = 'sections' if sections else 'prefix'
    if saved.get('root') != str(root) or migration.digest(migration._json(seed).encode()) != saved.get('id') or saved.get('history') != f"history/state-{kind}-repair-{saved['id']}.md":
        raise StreamsError('Prefix repair journal plan identity changed')
    prefix_bytes, target = (0, 'sections') if sections else _disposition(saved)
    if saved['version'] in (2, 3) and saved.get('sourceGitHead') != operation['base_head']:
        raise StreamsError('Prefix repair source Git parent changed')
    source, after = artifacts._decode_bytes(saved['source']), artifacts._decode_bytes(saved['after'])
    candidate = _sections_candidate(source, saved['book']) if sections else _candidate(source, prefix_bytes, target, saved['book'])
    if (migration.digest(source) != saved['sourceSha256'] or migration.digest(after) != saved['afterSha256'] or candidate != after):
        raise StreamsError('Prefix repair source hashes or projection changed')
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
    if set(expected).intersection(git(root, 'diff', '--cached', '--name-only').splitlines()):
        raise StreamsError('Prefix repair overlaps newer staged edits')
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
    name = 'state-sections-repair.json' if operation['plan']['version'] == 3 else 'state-repair.json'
    _write(root / 'log' / name, json.dumps(operation, indent=2, sort_keys=True) + '\n')
