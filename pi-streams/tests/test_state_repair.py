from __future__ import annotations

import hashlib
import json
import os
import sys
from unittest import mock

from support import EngineCase, ROOT, git, seed_ratified_stream

sys.path.insert(0, str(ROOT / 'pi-streams'))
from engine import state_repair


class StateRepairTests(EngineCase):
    def setUp(self):
        super().setUp()
        self.assertEqual(self.run_streams('init', str(self.root), '-y').returncode, 0)
        self.stream = self.register_stream('repair')
        seed_ratified_stream(self.stream, self.root.name)
        self.prefix = b'# Historical heading\nThis prefix was explicitly classified as history.\n'
        self.canonical = (self.stream / 'STATE.md').read_bytes()
        self.original = self.prefix + self.canonical
        (self.stream / 'STATE.md').write_bytes(self.original)
        git(self.stream, self.env, 'init')
        git(self.stream, self.env, 'add', '--all')
        git(self.stream, self.env, 'commit', '-m', 'canonical prefix fixture')
        self.stub.requests.clear()

    def plan(self):
        result = self.run_streams('migrate', 'repair', '--repair-plan', '--prefix-history-bytes', str(len(self.prefix)))
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        path = self.tmp / 'repair-plan.json'
        path.write_text(json.dumps(plan))
        return plan, path

    def test_supported_plan_and_apply_preserve_exact_sources_and_authority_without_native_actions(self):
        plan, path = self.plan()
        self.assertEqual((self.stream / 'STATE.md').read_bytes(), self.original)
        self.assertEqual(plan['sourceSha256'], hashlib.sha256(self.original).hexdigest())
        applied = self.run_streams('migrate', 'repair', '--repair-apply', str(path))
        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertEqual((self.stream / 'STATE.md').read_bytes(), self.canonical)
        self.assertEqual((self.stream / plan['history']).read_bytes(), self.original)
        self.assertEqual(self.stub.requests, [])
        before = git(self.stream, self.env, 'rev-parse', 'HEAD')
        again = self.run_streams('migrate', 'repair', '--repair-resume')
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertFalse(json.loads(again.stdout)['changed'])
        self.assertEqual(git(self.stream, self.env, 'rev-parse', 'HEAD'), before)
        body = self.tmp / 'log-entry.txt'
        body.write_text('The existing standing grant remains authoritative.')
        logged = self.run_streams('state', 'append', 'repair', '--subject', 'After repair', '--body-file', str(body), '--request-id', 'after-repair')
        self.assertEqual(logged.returncode, 0, logged.stderr)

    def test_interrupted_repair_blocks_other_writers_and_resumes_exactly_once(self):
        plan, path = self.plan()
        real = state_repair._save
        def interrupt(root, operation):
            real(root, operation)
            if operation['phase'] == 'state':
                raise OSError('controlled repair interruption')
        with mock.patch.dict(os.environ, self.env, clear=True), mock.patch('engine.state_repair._save', side_effect=interrupt):
            with self.assertRaisesRegex(OSError, 'controlled repair'):
                state_repair.apply_locked(self.stream, plan)
        body = self.tmp / 'must-wait.txt'
        body.write_text('Do not cross pending artifact ownership.')
        stopped = self.run_streams('state', 'objective', 'repair', '--body-file', str(body))
        self.assertNotEqual(stopped.returncode, 0)
        resumed = self.run_streams('migrate', 'repair', '--repair-resume')
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertEqual((self.stream / 'STATE.md').read_bytes(), self.canonical)
        self.assertEqual((self.stream / plan['history']).read_bytes(), self.original)
        self.assertEqual(git(self.stream, self.env, 'rev-list', '--count', 'HEAD').strip(), '2')

    def test_changed_source_or_prefix_boundary_refuses_without_rewriting_authority(self):
        plan, path = self.plan()
        changed = self.original + b'Newer facts\n'
        (self.stream / 'STATE.md').write_bytes(changed)
        applied = self.run_streams('migrate', 'repair', '--repair-apply', str(path))
        self.assertNotEqual(applied.returncode, 0)
        self.assertEqual((self.stream / 'STATE.md').read_bytes(), changed)
        bad = self.run_streams('migrate', 'repair', '--repair-plan', '--prefix-history-bytes', str(len(self.prefix) + 4))
        self.assertNotEqual(bad.returncode, 0)
        self.assertEqual((self.stream / 'STATE.md').read_bytes(), changed)
