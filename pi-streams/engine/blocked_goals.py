from __future__ import annotations

import hashlib
import re
from pathlib import Path

from engine import StreamsError, artifacts, clock, sessionlog


def fingerprint(goal: str) -> str:
    goal = goal.removeprefix('/poteto-mode ')
    return hashlib.sha256(' '.join(goal.split()).encode()).hexdigest()


def observe(stream: Path, goal: str, sid: str, native_file: str) -> None:
    evidence = sessionlog.last_assistant(Path(native_file), evidence=True)
    if evidence is None:
        return
    content = evidence['message'].get('content', [])
    text = content if isinstance(content, str) else '\n'.join(part.get('text', '') for part in content if isinstance(part, dict) and part.get('type') == 'text')
    if not re.search(r'(?im)^\s*(?:\*\*|#{1,6}\s*)?(?:blocked\b|blocker\b|cannot proceed\b|unable to proceed\b)', text):
        return
    receive(stream, goal, f"{sid}:{evidence['entryId']}:{evidence['sha256']}")


def receive(stream: Path, goal: str, identity: str, *, sent: str = '') -> None:
    data = artifacts._read_tick_data(stream)
    records = data.setdefault('blocked_goals', {})
    if not isinstance(records, dict):
        raise StreamsError('Invalid blocked-goal records')
    record = records.setdefault(fingerprint(goal), {'sent': [], 'received': [], 'disposition': 'tracking'})
    if identity not in record['received']:
        record['received'].append(identity)
    if sent and sent not in record['sent']:
        record['sent'].append(sent)
    artifacts._save_tick_data(stream, data)


def permit(stream: Path, goal: str) -> bool:
    from engine.delivery import receipts

    data = artifacts._read_tick_data(stream)
    key = fingerprint(goal)
    record = data.get('blocked_goals', {}).get(key)
    if record is None:
        return True
    if not isinstance(record, dict) or set(record) != {'sent', 'received', 'disposition'} or not all(isinstance(record[name], list) and all(isinstance(item, str) for item in record[name]) for name in ('sent', 'received')) or record['disposition'] not in {'tracking', 'suppressed'}:
        raise StreamsError('Invalid blocked-goal disposition')
    for delivery in receipts(stream):
        candidate = delivery.get('control', {}).get('goal', delivery['body'])
        admitted = delivery['state'] in {'transport_accepted', 'consumed', 'applied'} or delivery.get('control', {}).get('state') in {'queued', 'sending', 'ended'}
        if admitted and fingerprint(candidate) == key and delivery['id'] not in record['sent']:
            record['sent'].append(delivery['id'])
    suppressed = record['disposition'] == 'suppressed' or len(record['sent']) >= 3
    record['disposition'] = 'suppressed' if suppressed else 'tracking'
    artifacts._save_tick_data(stream, data)
    if suppressed:
        artifacts.append_log_locked(stream, clock.stamp(clock.now()), 'Blocked-goal escalation', f'Goal fingerprint {key}. Three distinct dispatches have a blocked report. Identical prompts are suppressed. Keep drive intent on. Select a different authorized strategy or unit; this blocker is not North Star completion.', request_id=f'blocked-goal:{key}')
    return not suppressed
