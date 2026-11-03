from __future__ import annotations

import hashlib
import json
import os
import sys
from unittest import mock

from support import EngineCase, ROOT, git, seed_ratified_stream

sys.path.insert(0, str(ROOT / 'pi-streams'))
from engine import artifacts, migration, state_repair


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


ACTIVE_STOP = b'# COMPLETED by ZF 2026-11-02 11:39 SGT. Stream closed. Do not resume, push, or start new work.\n\n'


class ActiveStateRepairTests(EngineCase):
    def setUp(self):
        super().setUp()
        self.assertEqual(self.run_streams('init', str(self.root), '-y').returncode, 0)
        self.fixture('repair')

    def fixture(self, name, prefix=ACTIVE_STOP):
        self.stream = self.register_stream(name)
        seed_ratified_stream(self.stream, self.root.name)
        state = self.stream / 'STATE.md'
        state.write_text(state.read_text().replace('### Current objective\n\n', '### Current objective\nThe stream remains closed. Do not resume business work.\n\n').replace('## Rules\n\n', '## Rules\nExisting fixture STOP. No publication or new work.\n\n## Fixture notes\nUnchanged optional section.\n\n'))
        git(self.stream, self.env, 'init')
        git(self.stream, self.env, 'add', '--all')
        git(self.stream, self.env, 'commit', '-m', 'canonical fixture')
        body = self.tmp / 'entry.txt'
        body.write_text('Preserve ordered Log ownership.\n## A heading inside an owned Log\n')
        for number in (1, 2):
            result = self.run_streams('state', 'append', name, '--subject', f'Owned entry {number}', '--body-file', str(body), '--request-id', f'owned-{number}')
            self.assertEqual(result.returncode, 0, result.stderr)
        self.canonical = (self.stream / 'STATE.md').read_bytes()
        self.tick = artifacts._read_tick_data(self.stream)
        self.prefix = prefix
        self.original = prefix + self.canonical
        (self.stream / 'STATE.md').write_bytes(self.original)
        (self.stream / 'threads.tsv').write_text('session\trole\trepo\tworktree\tbranch\tbase\tmodel\tthinking\tstatus\tstarted\n' + f'closed-fixture\tcoordinator\t\t{self.stream}\t\t\topenai/gpt6.1-sol\txhigh\tdone\t2026-11-02T03:39:00Z\n')
        git(self.stream, self.env, 'init')
        git(self.stream, self.env, 'add', '--all')
        git(self.stream, self.env, 'commit', '-m', 'closed active prefix fixture')
        self.initial_count = int(git(self.stream, self.env, 'rev-list', '--count', 'HEAD'))
        self.stub.requests.clear()

    def plan(self):
        result = self.run_streams('migrate', self.stream.name, '--repair-plan', '--prefix-rules-bytes', str(len(self.prefix)))
        self.assertEqual(result.returncode, 0, result.stderr)
        path = self.tmp / 'active-plan.json'
        path.write_text(result.stdout)
        return json.loads(result.stdout), path

    def apply(self, path):
        return self.run_streams('migrate', self.stream.name, '--repair-apply', str(path))

    def check_repaired(self, plan):
        after = (self.stream / 'STATE.md').read_bytes()
        before = artifacts._checked_state(self.canonical, artifacts._book(self.tick['state_log']))
        parsed = artifacts._checked_state(after, artifacts._book(self.tick['state_log']))
        self.assertEqual(after[parsed.goals.heading.start:parsed.goals.body.end], self.canonical[before.goals.heading.start:before.goals.body.end])
        self.assertEqual(after[parsed.rules.body.end:], self.canonical[before.rules.body.end:])
        self.assertEqual(after[parsed.log.heading.start:], self.canonical[before.log.heading.start:])
        rules = after[parsed.rules.body.start:parsed.rules.body.end]
        self.assertIn(self.prefix, rules)
        self.assertTrue(rules.startswith(b'Retained active Rules from the STATE prefix.\n\n'))
        self.assertTrue(rules.endswith(self.canonical[before.rules.body.start:before.rules.body.end]))
        self.assertEqual((self.stream / plan['history']).read_bytes(), self.original)
        self.assertEqual(artifacts._read_tick_data(self.stream), self.tick)
        self.assertNotIn('drive', self.tick)
        self.assertEqual(self.stub.requests, [])

    def interrupt(self, plan, phase):
        real = state_repair._save
        def save(root, operation):
            real(root, operation)
            if operation['phase'] == phase:
                raise OSError('controlled active repair interruption')
        with mock.patch.dict(os.environ, self.env, clear=True), mock.patch('engine.state_repair._save', side_effect=save):
            with self.assertRaisesRegex(OSError, 'controlled active repair'):
                state_repair.apply_locked(self.stream, plan)

    def resume(self):
        return self.run_streams('migrate', self.stream.name, '--repair-resume')

    def test_cli_status_red_then_plan_apply_repeat_green_retains_active_stop_and_exact_authority(self):
        self.assertEqual(len(ACTIVE_STOP), 96)
        before = self.run_streams('status', self.stream.name, '--json')
        self.assertEqual(before.returncode, 1)
        self.assertIn('STATE has content before Goals', before.stderr)
        plan, path = self.plan()
        self.assertEqual(plan['version'], 2)
        self.assertEqual(plan['prefixDisposition'], {'bytes': 96, 'target': 'rules'})
        self.assertEqual(plan['sourceSha256'], hashlib.sha256(self.original).hexdigest())
        self.assertEqual((self.stream / 'STATE.md').read_bytes(), self.original)
        self.assertFalse((self.stream / 'log/state-repair.json').exists())
        frozen = {name: (self.stream / name).read_bytes() for name in ('threads.tsv', 'stream.toml', 'AGENTS.md')}
        applied = self.apply(path)
        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.check_repaired(plan)
        head = git(self.stream, self.env, 'rev-parse', 'HEAD')
        for result in (self.apply(path), self.resume()):
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(json.loads(result.stdout)['changed'])
        self.assertEqual(git(self.stream, self.env, 'rev-parse', 'HEAD'), head)
        self.assertEqual(git(self.stream, self.env, 'diff', '--cached', '--name-only'), '')
        status = self.run_streams('status', self.stream.name, '--json')
        self.assertEqual(status.returncode, 0, status.stderr)
        report = json.loads(status.stdout)['streams'][0]
        self.assertTrue(report['ratified'])
        self.assertIsNone(report['coordinator'])
        self.assertNotIn('drive', report)
        self.assertEqual({name: (self.stream / name).read_bytes() for name in frozen}, frozen)
        self.assertEqual(self.stub.requests, [])

    def test_markdown_injection_and_multibyte_prefix_stay_literal_inside_rules(self):
        prefix = 'STOP. 不要恢复。\r\n## Log\n### Charter\n```\n``````\n~~~\n## Goals\n'.encode()
        self.fixture('literal', prefix)
        plan, path = self.plan()
        applied = self.apply(path)
        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.check_repaired(plan)
        after = (self.stream / 'STATE.md').read_bytes()
        self.assertIn(b'```````text\n' + prefix + b'```````\n', after)
        self.assertEqual(self.run_streams('status', self.stream.name, '--json').returncode, 0)
        self.assertEqual(self.stub.requests, [])

    def test_requires_one_explicit_supported_classification(self):
        for options in ((), ('--prefix-rules-bytes', '96', '--prefix-history-bytes', '96'), ('--prefix-target', 'objective'), ('--prefix-rules-bytes', ''), ('--prefix-rules-bytes', 'unknown')):
            with self.subTest(options=options):
                result = self.run_streams('migrate', self.stream.name, '--repair-plan', *options)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual((self.stream / 'STATE.md').read_bytes(), self.original)
                self.assertFalse((self.stream / 'log/state-repair.json').exists())
        result = self.run_streams('migrate', self.stream.name, '--repair-resume', '--prefix-rules-bytes', '96')
        self.assertNotEqual(result.returncode, 0)

    def test_invalid_utf8_nul_empty_rules_and_incomplete_line_boundaries_refuse(self):
        variants = [(b'\xff\n', 2), (b'\0\n', 2), (b' \r\n\n', 4), ('停止\n'.encode(), 1), (ACTIVE_STOP, 0), (ACTIVE_STOP, -1), (ACTIVE_STOP, 5), (ACTIVE_STOP, 96 + 4), (ACTIVE_STOP, len(self.original))]
        for prefix, count in variants:
            with self.subTest(prefix=prefix, count=count):
                raw = prefix + self.canonical
                (self.stream / 'STATE.md').write_bytes(raw)
                result = self.run_streams('migrate', self.stream.name, '--repair-plan', '--prefix-rules-bytes', str(count))
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual((self.stream / 'STATE.md').read_bytes(), raw)
                self.assertFalse((self.stream / 'log/state-repair.json').exists())
        (self.stream / 'STATE.md').write_bytes(ACTIVE_STOP + b'\xff' + self.canonical)
        result = self.run_streams('migrate', self.stream.name, '--repair-plan', '--prefix-rules-bytes', '96')
        self.assertNotEqual(result.returncode, 0)

    def test_tampered_or_ambiguous_plan_disposition_refuses(self):
        plan, path = self.plan()
        for disposition in ({'bytes': 96, 'target': ''}, {'bytes': 96, 'target': 'objective'}, {'bytes': 96}, {'bytes': 96, 'target': None}, {'bytes': True, 'target': 'rules'}, {'bytes': 96, 'target': 'rules', 'history': True}):
            with self.subTest(disposition=disposition):
                path.write_text(json.dumps({**plan, 'prefixDisposition': disposition}))
                result = self.apply(path)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual((self.stream / 'STATE.md').read_bytes(), self.original)
                self.assertFalse((self.stream / 'log/state-repair.json').exists())
        path.write_text(json.dumps({**plan, 'prefixHistoryBytes': 96}))
        self.assertNotEqual(self.apply(path).returncode, 0)

    def test_changed_state_between_plan_and_apply_refuses(self):
        plan, path = self.plan()
        changed = b'Newer STOP\n' + self.original
        (self.stream / 'STATE.md').write_bytes(changed)
        self.assertNotEqual(self.apply(path).returncode, 0)
        self.assertEqual((self.stream / 'STATE.md').read_bytes(), changed)
        self.assertFalse((self.stream / 'log/state-repair.json').exists())

    def test_changed_log_book_between_plan_and_apply_refuses(self):
        plan, path = self.plan()
        changed = artifacts._read_tick_data(self.stream)
        changed['state_log']['next_occurrence'] += 1
        artifacts._save_tick_data(self.stream, changed)
        self.assertNotEqual(self.apply(path).returncode, 0)
        self.assertEqual((self.stream / 'STATE.md').read_bytes(), self.original)
        self.assertEqual(artifacts._read_tick_data(self.stream), changed)
        self.assertFalse((self.stream / 'log/state-repair.json').exists())

    def test_git_parent_drift_since_plan_refuses(self):
        plan, path = self.plan()
        git(self.stream, self.env, 'commit', '--allow-empty', '-m', 'newer parent')
        head = git(self.stream, self.env, 'rev-parse', 'HEAD')
        self.assertNotEqual(self.apply(path).returncode, 0)
        self.assertEqual((self.stream / 'STATE.md').read_bytes(), self.original)
        self.assertEqual(git(self.stream, self.env, 'rev-parse', 'HEAD'), head)
        self.assertFalse((self.stream / 'log/state-repair.json').exists())

    def test_staged_state_or_archive_refuses_without_rewriting(self):
        plan, path = self.plan()
        for name in ('STATE.md', plan['history']):
            with self.subTest(name=name):
                target = self.stream / name
                if name != 'STATE.md':
                    target.parent.mkdir(exist_ok=True)
                    target.write_bytes(b'foreign source\n')
                else:
                    target.write_bytes(self.original + b'foreign staged bytes\n')
                git(self.stream, self.env, 'add', '--', name)
                if name == 'STATE.md':
                    target.write_bytes(self.original)
                staged = git(self.stream, self.env, 'show', ':' + name)
                self.assertNotEqual(self.apply(path).returncode, 0)
                self.assertEqual((self.stream / 'STATE.md').read_bytes(), self.original)
                self.assertEqual(git(self.stream, self.env, 'show', ':' + name), staged)
                git(self.stream, self.env, 'reset', 'HEAD', '--', name)

    def test_all_saved_phases_resume_once_without_duplication(self):
        for phase in ('history', 'state', 'commit', 'complete'):
            with self.subTest(phase=phase):
                self.fixture('phase-' + phase)
                plan, path = self.plan()
                self.interrupt(plan, phase)
                result = self.resume()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.check_repaired(plan)
                self.assertEqual(int(git(self.stream, self.env, 'rev-list', '--count', 'HEAD')), self.initial_count + 1)
                self.assertFalse(json.loads(self.resume().stdout)['changed'])

    def test_state_write_or_scoped_commit_reply_loss_resumes_once(self):
        for lost in ('state-write', 'commit'):
            with self.subTest(lost=lost):
                self.fixture('reply-loss-' + lost)
                plan, path = self.plan()
                if lost == 'state-write':
                    real = state_repair._write
                    def write(target, text):
                        real(target, text)
                        if target == self.stream / 'STATE.md':
                            raise OSError('controlled reply loss')
                    patch = mock.patch('engine.state_repair._write', side_effect=write)
                else:
                    real = state_repair.commit_repo
                    def commit(*args, **kwargs):
                        real(*args, **kwargs)
                        raise OSError('controlled reply loss')
                    patch = mock.patch('engine.state_repair.commit_repo', side_effect=commit)
                with mock.patch.dict(os.environ, self.env, clear=True), patch:
                    with self.assertRaisesRegex(OSError, 'controlled reply loss'):
                        state_repair.apply_locked(self.stream, plan)
                result = self.resume()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.check_repaired(plan)
                self.assertEqual(int(git(self.stream, self.env, 'rev-list', '--count', 'HEAD')), self.initial_count + 1)
                self.assertFalse(json.loads(self.resume().stdout)['changed'])

    def test_pending_or_unregistered_log_ownership_is_not_reclassified(self):
        for pending in (False, True):
            with self.subTest(pending=pending):
                data = json.loads(json.dumps(self.tick))
                if pending:
                    data['state_log']['pending'] = {'fixture': 'owned elsewhere'}
                else:
                    del data['state_log']
                artifacts._save_tick_data(self.stream, data)
                result = self.run_streams('migrate', self.stream.name, '--repair-plan', '--prefix-rules-bytes', '96')
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual((self.stream / 'STATE.md').read_bytes(), self.original)
                self.assertEqual(artifacts._read_tick_data(self.stream), data)
                self.assertFalse((self.stream / 'log/state-repair.json').exists())

    def test_resume_refuses_changed_retained_source(self):
        plan, path = self.plan()
        self.interrupt(plan, 'state')
        history = self.stream / plan['history']
        history.write_bytes(self.original + b'newer evidence\n')
        self.assertNotEqual(self.resume().returncode, 0)
        self.assertEqual((self.stream / 'STATE.md').read_bytes(), self.original)
        self.assertEqual(history.read_bytes(), self.original + b'newer evidence\n')

    def test_resume_refuses_newer_state_book_staging_or_git_parent_before_writes(self):
        for drift in ('state', 'book', 'staging', 'parent'):
            with self.subTest(drift=drift):
                self.fixture('drift-' + drift)
                plan, path = self.plan()
                self.interrupt(plan, 'state')
                if drift == 'state':
                    (self.stream / 'STATE.md').write_bytes(b'Newer STOP\n' + self.original)
                elif drift == 'book':
                    changed = artifacts._read_tick_data(self.stream)
                    changed['state_log']['next_occurrence'] += 1
                    artifacts._save_tick_data(self.stream, changed)
                elif drift == 'staging':
                    (self.stream / 'STATE.md').write_bytes(b'Foreign staged STATE\n')
                    git(self.stream, self.env, 'add', '--', 'STATE.md')
                    (self.stream / 'STATE.md').write_bytes(self.original)
                else:
                    git(self.stream, self.env, 'commit', '--allow-empty', '-m', 'concurrent parent')
                before = (self.stream / 'STATE.md').read_bytes()
                tick = artifacts._read_tick_data(self.stream)
                self.assertNotEqual(self.resume().returncode, 0)
                self.assertEqual((self.stream / 'STATE.md').read_bytes(), before)
                self.assertEqual(artifacts._read_tick_data(self.stream), tick)
                self.assertEqual((self.stream / plan['history']).read_bytes(), self.original)

    def test_old_version_history_plan_and_interrupted_journal_remain_compatible(self):
        for recorded in (False, True):
            with self.subTest(recorded=recorded):
                self.fixture('legacy-' + str(recorded).lower(), b'# Explicit historical prefix\n')
                seed = {'version': 1, 'root': str(self.stream.resolve()), 'at': '2026-11-03T00:00:00Z', 'prefixHistoryBytes': len(self.prefix), 'source': migration.encoded(self.original), 'sourceSha256': migration.digest(self.original), 'after': migration.encoded(self.canonical), 'afterSha256': migration.digest(self.canonical), 'book': self.tick['state_log']}
                identity = migration.digest(migration._json(seed).encode())
                plan = {**seed, 'id': identity, 'history': f'history/state-prefix-repair-{identity}.md'}
                path = self.tmp / 'old-plan.json'
                path.write_text(json.dumps(plan))
                if recorded:
                    history = self.stream / plan['history']
                    history.parent.mkdir(exist_ok=True)
                    history.write_bytes(self.original)
                    operation = {'version': 1, 'root': str(self.stream.resolve()), 'plan': plan, 'base_head': git(self.stream, self.env, 'rev-parse', 'HEAD').strip(), 'message': f"pi-streams repair-state {self.stream.name} {identity}", 'phase': 'state'}
                    (self.stream / 'log/state-repair.json').write_text(json.dumps(operation))
                    result = self.resume()
                else:
                    result = self.apply(path)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual((self.stream / 'STATE.md').read_bytes(), self.canonical)
                self.assertEqual((self.stream / plan['history']).read_bytes(), self.original)
                self.assertFalse(json.loads(self.resume().stdout)['changed'])
                self.assertEqual(artifacts._read_tick_data(self.stream), self.tick)
                self.assertEqual(self.stub.requests, [])
