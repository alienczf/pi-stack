"""A coordinator designation must resolve to its exact owned native identity."""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path
from unittest import mock
from support import EngineCase, ROOT, git, seed_ratified_stream
sys.path.insert(0, str(ROOT / 'pi-streams'))
from engine import StreamsError, doctor, threads
from engine.project import StreamRow, load_project
HEADER = 'session\trole\trepo\tworktree\tbranch\tbase\tmodel\tthinking\tstatus\tstarted\n'

def live(sid: str) -> dict:
    return {'sessionId': sid, 'isStreaming': False, 'isCompacting': False, 'isBashRunning': False, 'pendingMessageCount': 0, 'contextUsage': {'tokens': 100}, 'model': {'provider': 'openai-codex', 'id': 'gpt-6.1-sol'}, 'thinkingLevel': 'xhigh', 'cost': 0}

class CoordinatorIdentityTests(EngineCase):

    def setUp(self):
        super().setUp()
        self.assertEqual(self.run_streams('init', str(self.root), '-y').returncode, 0)
        self.stream = self.register_stream('etl')
        seed_ratified_stream(self.stream, self.root.name)
        self.table = self.stream / 'threads.tsv'
        self.table.write_text(HEADER + self.row('current'))
        git(self.stream, self.env, 'init')
        git(self.stream, self.env, 'add', '-A')
        git(self.stream, self.env, 'commit', '-m', 'private identity fixture')
        self.stub.requests.clear()

    def row(self, sid, role='coordinator', state='active', cwd=None):
        model = 'openai-codex/gpt-6.1-sol' if role == 'coordinator' else 'openai-codex/gpt-6-luna'
        return f'{sid}\t{role}\t\t{cwd or self.stream}\t\t\t{model}\txhigh\t{state}\t2026-10-23T00:00:00Z\n'

    def info(self, sid='current', *, archived=False, cwd=None, count=12):
        return {'id': sid, 'cwd': str(cwd or self.stream), 'messageCount': count, 'archived': archived, 'modified': '2026-10-23T00:00:00Z'}

    def routes(self, infos, body=None):
        self.stub.set_routes([('GET', '/api/sessions', 200, infos), ('GET', '/api/sessions/current/status', 200, live('current') if body is None else body)])

    def no_mutations(self):
        self.assertEqual([item for item in self.stub.requests if item[0] not in ('GET', 'HEAD')], [])

    def test_status_reports_a_missing_designation_instead_of_a_healthy_empty_coordinator(self):
        self.table.write_text(HEADER)
        self.routes([self.info('unregistered')])
        result = self.run_streams('status', 'etl', '--json')
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn('no designated active coordinator', result.stderr)
        self.no_mutations()

    def test_status_refuses_a_missing_designated_native_session(self):
        self.routes([])
        result = self.run_streams('status', 'etl', '--json')
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn('current', result.stderr)
        self.assertNotIn('/api/sessions/current/status', [item[1] for item in self.stub.requests])
        self.no_mutations()

    def test_new_does_not_trust_a_stale_active_row(self):
        self.routes([])
        before = self.table.read_bytes()
        result = self.run_streams('new', 'etl')
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn('current', result.stderr)
        self.assertEqual(self.table.read_bytes(), before)
        self.no_mutations()

    def test_duplicate_active_designations_refuse_before_native_calls(self):
        self.table.write_text(HEADER + self.row('current') + self.row('other'))
        self.routes([self.info(), self.info('other')])
        result = self.run_streams('status', 'etl', '--json')
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn('coordinator', result.stderr)
        self.assertEqual(self.stub.requests, [])

    def test_duplicate_session_ids_are_not_a_valid_registry(self):
        self.table.write_text(HEADER + self.row('current') + self.row('current', role='worker'))
        self.routes([self.info()])
        result = self.run_streams('status', 'etl', '--json')
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn('duplicate', result.stderr.lower())
        self.no_mutations()

    def test_archived_designation_is_checked_before_status_can_reopen_it(self):
        self.routes([self.info(archived=True)])
        result = self.run_streams('status', 'etl', '--json')
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn('archived', result.stderr.lower())
        self.assertNotIn('/api/sessions/current/status', [item[1] for item in self.stub.requests])
        self.no_mutations()

    def test_prefix_or_wrong_cwd_is_not_the_designated_identity(self):
        for infos in ([self.info('current-longer')], [self.info(cwd=self.fx.alpha)]):
            with self.subTest(infos=infos):
                self.stub.requests.clear()
                self.routes(infos)
                result = self.run_streams('status', 'etl', '--json')
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertNotIn('/api/sessions/current/status', [item[1] for item in self.stub.requests])
                self.no_mutations()

    def test_runtime_status_must_repeat_the_exact_designated_id(self):
        self.routes([self.info()], live('some-other-session'))
        result = self.run_streams('status', 'etl', '--json')
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn('identity', result.stderr.lower())
        self.no_mutations()

    def test_unregistered_same_directory_candidate_is_a_mismatch(self):
        self.routes([self.info(), self.info('unregistered')])
        result = self.run_streams('status', 'etl', '--json')
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn('unregistered', result.stderr.lower())
        self.no_mutations()

    def test_new_never_implicitly_adopts_an_empty_or_nonempty_conversation(self):
        self.table.write_text(HEADER)
        for count in (0, 12):
            with self.subTest(count=count):
                self.stub.requests.clear()
                self.stub.set_routes([('GET', '/api/sessions', 200, [self.info('unrelated', count=count)]), ('GET', '/api/sessions/unrelated/status', 200, live('unrelated'))])
                result = self.run_streams('new', 'etl')
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertEqual(self.table.read_text(), HEADER)
                self.no_mutations()

    def test_explicit_adoption_records_exact_identity_without_reprompting(self):
        self.table.write_text(HEADER)
        self.stub.set_routes([('GET', '/api/sessions', 200, [self.info('selected')]), ('GET', '/api/sessions/selected/status', 200, live('selected'))])
        result = self.run_streams('new', 'etl', '--coordinator-session', 'selected')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.endswith('selected\n'))
        self.assertEqual(self.table.read_text().splitlines()[1].split('\t')[:2], ['selected', 'coordinator'])
        self.no_mutations()

    def test_failed_opening_keeps_exact_spawn_identity_for_retry(self):
        self.table.write_text(HEADER)
        self.stub.set_routes([('GET', '/api/sessions', 200, []), ('POST', '/api/sessions', 200, {'id': 'created', 'cwd': str(self.stream)}), ('GET', '/api/sessions/created/status', 200, live('created')), ('POST', '/api/sessions/created/prompt', 409, {'error': 'rejected fixture opening'})])
        failed = self.run_streams('new', 'etl')
        self.assertEqual(failed.returncode, 1)
        data = json.loads((self.stream / 'log/tick-state.json').read_text())
        self.assertEqual(data['session_start']['session'], 'created')
        self.assertEqual(data['session_start']['cwd'], str(self.stream))
        self.assertEqual(self.table.read_text(), HEADER)
        self.stub.requests.clear()
        self.stub.set_routes([('GET', '/api/sessions', 200, [self.info('retired', archived=True), self.info('created', count=0)]), ('GET', '/api/sessions/created/status', 200, live('created')), ('POST', '/api/sessions/created/prompt', 200, {'accepted': True})])
        retried = self.run_streams('new', 'etl')
        self.assertEqual(retried.returncode, 0, retried.stderr)
        self.assertTrue(retried.stdout.endswith('created\n'))
        self.assertNotIn(('POST', '/api/sessions'), [(method, path) for method, path, _, _ in self.stub.requests])
        self.assertNotIn('session_start', json.loads((self.stream / 'log/tick-state.json').read_text()))

    def test_coordinator_role_is_reserved_before_worker_effects(self):
        for args in (('thread', 'spawn', 'etl', '--repo', 'alpha', '--role', 'coordinator'), ('thread', 'adopt', 'etl', 'selected', '--worktree', str(self.fx.alpha_wt), '--role', 'coordinator')):
            with self.subTest(args=args):
                self.stub.requests.clear()
                before = self.table.read_bytes()
                result = self.run_streams(*args)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn('reserved', result.stderr.lower())
                self.assertEqual(self.stub.requests, [])
                self.assertEqual(self.table.read_bytes(), before)
                self.assertFalse((self.root / '.worktrees').exists())
                self.assertFalse((self.fx.alpha_wt / '.stream').exists())

    def test_first_line_unratified_authority_blocks_worker_spawn_and_adopt(self):
        state = self.stream / 'STATE.md'
        state.write_bytes(state.read_bytes().replace(b'ratified: 2026-10-23 fixture human confirmation', b'ratified: no', 1) + b'Historical quotation only: ratified: yes\n')
        for args in (('thread', 'spawn', 'etl', '--repo', 'alpha', '--role', 'worker'), ('thread', 'adopt', 'etl', 'selected', '--worktree', str(self.fx.alpha_wt), '--role', 'worker')):
            with self.subTest(args=args):
                self.stub.requests.clear()
                self.stub.set_routes([('GET', '/api/sessions', 200, [{'id': 'selected', 'cwd': str(self.fx.alpha_wt)}]), ('POST', '/api/sessions', 200, {'id': 'created'}), ('GET', '/api/sessions/created/status', 200, live('created')), ('GET', '/api/sessions/selected/status', 200, live('selected')), ('POST', '/api/sessions/created/prompt', 200, {'accepted': True})])
                before = self.table.read_bytes()
                result = self.run_streams(*args)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertEqual(self.stub.requests, [])
                self.assertEqual(self.table.read_bytes(), before)
                self.assertFalse((self.root / '.worktrees').exists())
                self.assertFalse((self.fx.alpha_wt / '.stream').exists())

    def test_tick_does_not_dispatch_or_rotate_a_missing_designation(self):
        self.routes([])
        meta = self.stream / 'log/tick-state.json'
        meta.parent.mkdir(exist_ok=True)
        meta.write_text(json.dumps({'pending': [{'at': '2026-10-23T00:00:00Z', 'kind': 'subscription', 'session': '', 'role': '', 'detail': 'labelled private event'}]}))
        before = self.table.read_bytes()
        result = self.run_streams('tick')
        self.assertEqual(result.returncode, 1, result.stdout)
        self.no_mutations()
        self.assertEqual(self.table.read_bytes(), before)

    def test_doctor_uses_the_same_native_identity_resolver(self):
        self.routes([])
        with mock.patch.dict(os.environ, self.env, clear=True):
            findings = doctor._check_stream(StreamRow('etl', str(self.stream), self.root.name), 'fixture-revision')
        failures = [finding for finding in findings if finding.name == 'coordinator' and finding.level == 'FAIL']
        self.assertEqual(len(failures), 1)
        self.assertIn('current', failures[0].detail)
        self.no_mutations()

    def test_bare_affirmative_is_not_source_backed_ratification(self):
        state = self.stream / 'STATE.md'
        state.write_bytes(state.read_bytes().replace(b'ratified: 2026-10-23 fixture human confirmation', b'ratified: yes', 1))
        result = self.run_streams('thread', 'spawn', 'etl', '--repo', 'alpha', '--role', 'worker')
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn('authority', result.stderr)
        self.assertEqual(self.stub.requests, [])
        self.assertFalse((self.root / '.worktrees').exists())

    def test_unrelated_directory_is_not_an_unregistered_coordinator_candidate(self):
        self.routes([self.info(), self.info('worker', cwd=self.fx.alpha_wt)])
        result = self.run_streams('status', 'etl', '--json')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['streams'][0]['coordinator']['session'], 'current')

    def test_opening_with_uncertain_acceptance_is_not_replayed_even_if_still_empty(self):
        self.table.write_text(HEADER)
        self.stub.set_routes([('GET', '/api/sessions', 200, []), ('POST', '/api/sessions', 200, {'id': 'created', 'cwd': str(self.stream)}), ('GET', '/api/sessions/created/status', 200, live('created')), ('POST', '/api/sessions/created/prompt', 200, {'accepted': True})])
        with mock.patch.dict(os.environ, self.env, clear=True):
            project = load_project(self.project_file)
            with mock.patch.object(threads, '_accept_start', side_effect=OSError('fixture crash after acceptance')):
                with self.assertRaisesRegex(OSError, 'fixture crash'):
                    threads.ensure_coordinator(project, self.stream)
        self.stub.requests.clear()
        self.stub.set_routes([('GET', '/api/sessions', 200, [self.info('created', count=0)]), ('GET', '/api/sessions/created/status', 200, live('created'))])
        result = self.run_streams('new', 'etl')
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn('uncertain', result.stderr)
        self.assertEqual(self.table.read_text(), HEADER)
        self.no_mutations()

    def test_accepted_opening_recovers_after_registry_publication_failure_without_prompt(self):
        self.table.write_text(HEADER)
        self.stub.set_routes([('GET', '/api/sessions', 200, []), ('POST', '/api/sessions', 200, {'id': 'created', 'cwd': str(self.stream)}), ('GET', '/api/sessions/created/status', 200, live('created')), ('POST', '/api/sessions/created/prompt', 200, {'accepted': True})])
        with mock.patch.dict(os.environ, self.env, clear=True):
            project = load_project(self.project_file)
            with mock.patch.object(threads, 'save_threads', side_effect=OSError('fixture registry crash')):
                with self.assertRaisesRegex(OSError, 'fixture registry crash'):
                    threads.ensure_coordinator(project, self.stream)
        self.stub.requests.clear()
        self.stub.set_routes([('GET', '/api/sessions', 200, [self.info('created')]), ('GET', '/api/sessions/created/status', 200, live('created'))])
        result = self.run_streams('new', 'etl')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.table.read_text().splitlines()[1].split('\t')[:2], ['created', 'coordinator'])
        self.no_mutations()

    def test_adoption_refuses_wrong_native_cwd_before_pointer_or_registry_writes(self):
        self.stub.set_routes([('GET', '/api/sessions', 200, [self.info('selected', cwd=self.fx.beta_wt)]), ('GET', '/api/sessions/selected/status', 200, live('selected'))])
        before = self.table.read_bytes()
        result = self.run_streams('thread', 'adopt', 'etl', 'selected', '--worktree', str(self.fx.alpha_wt), '--role', 'worker')
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn('cwd', result.stderr)
        self.assertFalse((self.fx.alpha_wt / '.stream').exists())
        self.assertEqual(self.table.read_bytes(), before)
        self.no_mutations()

    def test_archived_registry_row_cannot_hide_a_still_live_predecessor(self):
        self.table.write_text(HEADER + self.row('old', state='archived') + self.row('current'))
        self.routes([self.info('old'), self.info()])
        result = self.run_streams('status', 'etl', '--json')
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn('old', result.stderr)
        self.no_mutations()

    def test_archived_predecessor_and_designated_live_successor_resolve_one_id(self):
        self.table.write_text(HEADER + self.row('old', state='archived') + self.row('current'))
        self.routes([self.info('old', archived=True), self.info()])
        result = self.run_streams('status', 'etl', '--json')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['streams'][0]['coordinator']['session'], 'current')
        self.assertNotIn('/api/sessions/old/status', [item[1] for item in self.stub.requests])
        self.no_mutations()
