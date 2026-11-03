from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import StreamsError, sessionlog
from tick_support import TickCase, failure
from tick_support import reply, user


class RetrySettlementTests(TickCase):
    def branch(self, *, pending=False, corrupt=False):
        sid = 'settlement-fixture'
        cwd = str(self.fx.alpha_wt)
        self.write_log(sid, cwd, user('bounded task'), failure('503 overloaded'), reply('completed'))
        path = Path(self.log_path(sid))
        lines = path.read_bytes().splitlines(keepends=True)
        data = {'version': 1, 'sessionId': sid, 'cwd': cwd, 'failure': {'entryId': 'e2', 'sha256': hashlib.sha256(lines[2]).hexdigest()}, 'identity': {'provider': 'openai-codex', 'model': 'gpt-6-astra', 'thinking': 'xhigh', 'generation': 'g'}, 'attempt': 1, 'delayMs': 5000, 'state': 'pending' if pending else 'resolved', 'phase': 'scheduled' if pending else 'attempting'}
        if not pending:
            data['completion'] = {'entryId': 'e3', 'sha256': '0' * 64 if corrupt else hashlib.sha256(lines[3]).hexdigest()}
        with path.open('a') as target:
            target.write(json.dumps({'type': 'custom', 'id': 'r', 'parentId': 'e3', 'customType': 'pi-web.stream-retry', 'data': data}) + '\n')
        return path, sid, cwd, data

    def test_resolved_raw_error_is_not_rediscovered(self):
        path, sid, cwd, _ = self.branch()
        self.assertIsNone(sessionlog.failure_observation(path, sid, cwd, 'r'))
        path, sid, cwd, _ = self.branch(corrupt=True)
        with self.assertRaisesRegex(StreamsError, 'retry'):
            sessionlog.failure_observation(path, sid, cwd, 'r')

    def test_recovery_fork_honors_only_linked_parent_settlements(self):
        path, parent, cwd, _ = self.branch()
        fork = self.tmp / 'recovery-fork.jsonl'
        lines = path.read_bytes().splitlines(keepends=True)
        header = {'type': 'session', 'version': 3, 'id': 'returned-fork', 'cwd': cwd, 'parentSession': str(path)}
        boundary = {'version': 1, 'sessionId': 'returned-fork', 'cwd': cwd, 'root': cwd, 'stream': 'fixture', 'state': 'recovering', 'recovery': {'id': 'owned-recovery', 'originalSessionId': parent}}
        held = {'type': 'custom', 'id': 'held', 'parentId': 'r', 'customType': 'pi-web.stream-failure', 'data': boundary}
        def publish():
            fork.write_bytes((json.dumps(header) + '\n').encode() + b''.join(lines[1:]) + (json.dumps(held) + '\n').encode())
        publish()
        self.assertIsNone(sessionlog.failure_observation(fork, 'returned-fork', cwd, 'held'))
        boundary['recovery']['originalSessionId'] = 'unrelated-session'
        publish()
        observed = sessionlog.failure_observation(fork, 'returned-fork', cwd, 'held')
        self.assertEqual(observed['entryId'], 'e2')

    def test_pending_native_retry_holds_only_with_exact_live_owner(self):
        path, sid, cwd, data = self.branch(pending=True)
        self.assertIsNone(sessionlog.failure_observation(path, sid, cwd, 'r', native_retry=data))
        with self.assertRaisesRegex(StreamsError, 'retry'):
            sessionlog.failure_observation(path, sid, cwd, 'r')
