from __future__ import annotations

import hashlib
import re
from pathlib import Path

from engine import StreamsError, artifacts, clock, sessionlog

BLOCKED = re.compile(r'(?im)^\s*(?:\*\*|#{1,6}\s*)?(?:blocked\b|blocker\b|cannot proceed\b|unable to proceed\b)')
PROGRESS = re.compile(r'\b(?:completed?|implemented|verified|passed|validated|resolved|installed)\b', re.IGNORECASE)
NEGATIVE = re.compile(r'\b(?:not|never|no)\s+(?:\w+\s+){0,2}(?:completed?|implemented|verified|passed|validated|resolved|installed)\b|\bfailed\b', re.IGNORECASE)


def fingerprint(goal: str) -> str:
    return hashlib.sha256(' '.join(goal.removeprefix('/poteto-mode ').split()).encode()).hexdigest()


def _deliveries(stream: Path, goal: str) -> list[dict]:
    from engine.delivery import receipts
    return [item for item in receipts(stream) if fingerprint(item.get('control', {}).get('goal', item['body'])) == fingerprint(goal)]


def _record(data: dict, goal: str) -> dict:
    records = data.setdefault('blocked_goals', {})
    if not isinstance(records, dict):
        raise StreamsError('Invalid blocked-goal records')
    key = fingerprint(goal)
    old = records.get(key)
    if old is not None and (not isinstance(old, dict) or not all(isinstance(old.get(name), list) for name in ('sent', 'received'))):
        raise StreamsError('Invalid blocked-goal record')
    if old is None or old.get('version') != 2:
        records[key] = {'version': 2, 'outcomes': {}, 'sent': [], 'received': [], 'disposition': 'tracking', **({'legacy': old} if old is not None else {})}
    record = records[key]
    if not isinstance(record.get('outcomes'), dict) or any(not isinstance(item, dict) or item.get('state') not in {'blocked', 'progress'} or type(item.get('sequence')) is not int or item['sequence'] < 1 or not isinstance(item.get('evidence'), list) or any(not isinstance(value, str) for value in item['evidence']) for item in record['outcomes'].values()):
        raise StreamsError('Invalid blocked-prompt outcomes')
    return record


def observe(stream: Path, goal: str, sid: str, native_file: str, *, dispatch: str = '') -> None:
    evidence = sessionlog.last_assistant(Path(native_file), evidence=True)
    if evidence is None or evidence['message'].get('stopReason') != 'stop':
        return
    content = evidence['message'].get('content', [])
    text = content if isinstance(content, str) else '\n'.join(part.get('text', '') for part in content if isinstance(part, dict) and part.get('type') == 'text')
    blocked = bool(BLOCKED.search(text))
    if not blocked and (not PROGRESS.search(text) or NEGATIVE.search(text)):
        return
    candidates = [item for item in _deliveries(stream, goal) if item['session'] == sid and (item['state'] in {'transport_accepted', 'consumed', 'applied'} or item.get('control', {}).get('state') == 'ended')]
    if not candidates:
        return
    target = next((item for item in candidates if item['id'] == dispatch), None) if dispatch else max(candidates, key=lambda item: item.get('control', {}).get('sequence', 0))
    if target is None:
        return
    _receive(stream, goal, target['id'], f"{sid}:{evidence['entryId']}:{evidence['sha256']}", 'blocked' if blocked else 'progress', native=True)


def receive(stream: Path, goal: str, identity: str, *, sent: str = '') -> None:
    target = sent or identity.removeprefix('delivery:')
    _receive(stream, goal, target, identity, 'blocked')


def progress(stream: Path, goal: str, identity: str) -> None:
    _receive(stream, goal, identity, 'applied:' + identity, 'progress')


def _receive(stream: Path, goal: str, target: str, evidence: str, state: str, *, native: bool = False) -> None:
    candidates = {item['id']: item for item in _deliveries(stream, goal)}
    if target not in candidates:
        return
    candidate = candidates[target]
    if candidate['state'] not in {'transport_accepted', 'consumed', 'applied', 'sending', 'uncertain'} and candidate.get('control', {}).get('state') not in {'queued', 'sending', 'ended'}:
        return
    data = artifacts._read_tick_data(stream)
    if state == 'progress' and fingerprint(goal) not in data.get('blocked_goals', {}):
        return
    record = _record(data, goal)
    outcome = record['outcomes'].get(target)
    if outcome is None:
        control = candidates[target].get('control', {})
        maximum = max((item['sequence'] for item in record['outcomes'].values()), default=0)
        offsets = record.setdefault('run_offsets', {})
        run = control.get('run_id')
        if run not in offsets:
            offsets[run or 'steer'] = maximum
        sequence = offsets.get(run, maximum) + control.get('sequence', 1)
        outcome = {'sequence': sequence, 'state': state, 'evidence': []}
        record['outcomes'][target] = outcome
    if native and evidence in outcome['evidence']:
        return
    if native or state == 'progress' or outcome['state'] != 'progress':
        outcome['state'] = state
    if evidence not in outcome['evidence']:
        outcome['evidence'].append(evidence)
    artifacts._save_tick_data(stream, data)


def permit(stream: Path, goal: str) -> bool:
    data = artifacts._read_tick_data(stream)
    key = fingerprint(goal)
    if key not in data.get('blocked_goals', {}):
        return True
    record = _record(data, goal)
    streak = []
    for target, outcome in sorted(record['outcomes'].items(), key=lambda item: item[1]['sequence']):
        if outcome['state'] == 'progress':
            streak = []
        elif outcome['state'] == 'blocked':
            streak.append(target)
    record['sent'] = streak
    record['received'] = ['delivery:' + target for target in streak]
    suppressed = len(streak) >= 3
    record['disposition'] = 'suppressed' if suppressed else 'tracking'
    artifacts._save_tick_data(stream, data)
    if suppressed:
        epoch = hashlib.sha256('\n'.join(streak).encode()).hexdigest()
        artifacts.append_log_locked(stream, clock.stamp(clock.now()), 'Blocked-goal escalation', f'Goal fingerprint {key}. Three distinct prompts have consecutive blocked outcomes without reported progress. Identical prompts are suppressed. Keep drive intent on. Select a different authorized strategy or unit; this blocker is not North Star completion.', request_id=f'blocked-goal:{key}:{epoch}')
    return not suppressed
