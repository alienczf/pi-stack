from __future__ import annotations

import hashlib
from pathlib import Path

from engine import StreamsError, artifacts, clock, piweb


def load(stream: Path, sid: str, cwd: str) -> dict | None:
    records = artifacts._read_tick_data(stream).get('terminal_sessions', {})
    if not isinstance(records, dict):
        raise StreamsError('Invalid terminal session records')
    value = records.get(sid)
    if value is not None and (not isinstance(value, dict) or value.get('cwd') != cwd or value.get('state') not in {'archived', 'missing', 'sending', 'refused', 'uncertain'}):
        raise StreamsError('Terminal session owner or disposition changed')
    return value


def save(stream: Path, sid: str, cwd: str, state: str, detail: str) -> None:
    data = artifacts._read_tick_data(stream)
    data.setdefault('terminal_sessions', {})[sid] = {'cwd': cwd, 'state': state, 'detail': detail}
    artifacts._save_tick_data(stream, data)
    if state != 'sending':
        artifacts.append_log_locked(stream, clock.stamp(clock.now()), 'Terminal session reconciliation', f'Session {sid}. Disposition {state}. {detail} Registry and handover evidence are retained.', request_id=f'terminal:{sid}:{state}:{hashlib.sha256(detail.encode()).hexdigest()}')


def archive(stream: Path, sid: str, cwd: str, *, explicit: bool = False, expected_idle: dict[str, str] | None = None) -> str:
    prior = load(stream, sid, cwd)
    if prior is not None:
        if prior['state'] == 'archived':
            return 'archived'
        if not (explicit and prior['state'] == 'refused'):
            raise StreamsError(f'Archive {sid} remains {prior["state"]}; preserve its exact disposition without replay')
    save(stream, sid, cwd, 'sending', 'Archive intent is durable; an interrupted outcome is not success.')
    try:
        piweb.archive(sid, expected_idle=expected_idle)
    except piweb.TerminalSession as exc:
        save(stream, sid, cwd, exc.state, str(exc))
        return exc.state
    except StreamsError as exc:
        save(stream, sid, cwd, 'refused' if isinstance(exc, piweb.ArchiveRejected) else 'uncertain', str(exc))
        raise
    save(stream, sid, cwd, 'archived', 'Native archive confirmed.')
    return 'archived'
