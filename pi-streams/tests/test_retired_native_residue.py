"""Retired coordinator residue must be safely archived before successor dispatch."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from support import ROOT, snapshot
from tick_support import PROMPTS, TickCase, info, reply, row, status, user


class RetiredNativeResidueTests(TickCase):
    def setUp(self):
        super().setUp()
        self.stream = self.make_stream(self.home, 'etl', row('retired', 'coordinator', str(self.home / 'etl'), status='archived'))
        self.write_log('retired', str(self.stream), user('Original bounded task'), reply('Original task checkpoint'))
        self.write_log('successor', str(self.stream), user('Explicit successor'), reply('Ready'))
        self.stub.automatic_admissions.update({sid: {'sessionId': sid, 'cwd': str(self.stream), 'generation': f'fixture-{sid}', 'allowed': True, 'durable': True} for sid in ('retired', 'successor')})
        self.retired_status = {**status('retired'), 'rotationSafety': {'entryId': 'e2', 'callbacksKnown': True, 'callbackInventory': 'native-and-extension-v1', 'nativeChildCallbacks': [], 'unprovenCallbacks': []}}
        self.infos = [info(sid, str(self.stream), self.log_path(sid)) for sid in ('retired', 'successor')]
        self.archive_reply = {'archived': True, 'automaticAdmission': {**self.stub.automatic_admissions['retired'], 'allowed': False, 'generation': 'frozen-retired'}}
        self.routes()

    def routes(self, *, archive_code=200, archive_reply=None):
        self.stub.set_routes([
            ('GET', '/api/sessions', 200, self.infos),
            ('GET', '/api/sessions/retired/status', 200, self.retired_status),
            ('GET', '/api/sessions/successor/status', 200, status('successor')),
            ('POST', '/api/sessions/retired/archive', archive_code, self.archive_reply if archive_reply is None else archive_reply),
            PROMPTS,
        ])

    def adopt(self):
        adopted = self.run_streams('new', 'etl', '--coordinator-session', 'successor')
        self.assertEqual(adopted.returncode, 0, adopted.stderr)
        self.assertTrue(adopted.stdout.endswith('successor\n'), adopted.stdout)
        self.assertEqual([r for r in self.stub.requests if r[0] != 'GET'], [])
        self.stub.requests.clear()
        return (self.stream / 'threads.tsv').read_bytes()

    def pending(self):
        path = self.stream / 'log/tick-state.json'
        data = json.loads(path.read_text()) if path.exists() else {}
        data['pending'] = [{'at': '2026-11-03T00:00:00Z', 'kind': 'subscription', 'session': '', 'role': '', 'detail': 'Retained event for the exact successor'}]
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(data))

    def posts(self):
        return [(path, body) for method, path, _, body in self.stub.requests if method == 'POST']

    def assert_blocked(self, result):
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual(self.posts(), [], result.stderr)
        self.assertEqual(self.state(self.stream)['pending'][0]['detail'], 'Retained event for the exact successor')

    def test_explicit_adoption_then_tick_safely_retires_and_dispatches_to_exact_successor(self):
        registry = self.adopt()
        native_bytes = Path(self.log_path('retired')).read_bytes()
        self.pending()
        before = snapshot(self.stream)
        observed = self.run_streams('status', 'etl', '--json')
        self.assertEqual(observed.returncode, 0, observed.stderr)
        entry, = json.loads(observed.stdout)['streams']
        self.assertEqual(entry['coordinator']['session'], 'successor')
        self.assertEqual(entry['dispatchBlockers'][0]['kind'], 'retired-native-residue')
        self.assertEqual(entry['dispatchBlockers'][0]['session'], 'retired')
        self.assertEqual(snapshot(self.stream), before)
        self.assertEqual(self.posts(), [])
        self.assertFalse(any(path == '/api/sessions/retired/status' for _, path, _, _ in self.stub.requests))

        ticked = self.tick('2026-11-03T00:01:00Z')
        self.assertEqual(ticked.returncode, 0, ticked.stderr)
        posts = self.posts()
        self.assertEqual([path for path, _ in posts], ['/api/sessions/retired/archive', '/api/sessions/successor/prompt'])
        self.assertEqual(posts[0][1], {'expectedIdle': {'sessionId': 'retired', 'cwd': str(self.stream), 'entryId': 'e2', 'generation': 'fixture-retired'}})
        self.assertIn('Retained event for the exact successor', posts[1][1]['text'])
        self.assertEqual(posts[1][1]['automaticAdmission']['sessionId'], 'successor')
        self.assertEqual(self.state(self.stream)['terminal_sessions']['retired']['state'], 'archived')
        self.assertEqual((self.stream / 'threads.tsv').read_bytes(), registry)
        self.assertEqual(Path(self.log_path('retired')).read_bytes(), native_bytes)

        self.apply_tick_delivery(self.stream)
        again = self.tick('2026-11-03T00:02:00Z')
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(self.posts(), [])
        self.assertFalse(any(path == '/api/sessions/retired/status' for _, path, _, _ in self.stub.requests))
        report = self.run_streams('status', 'etl', '--json')
        self.assertNotIn('dispatchBlockers', json.loads(report.stdout)['streams'][0])

    def test_tick_heals_an_already_adopted_stream_without_another_new_command(self):
        with (self.stream / 'threads.tsv').open('a') as handle:
            handle.write(row('successor', 'coordinator', str(self.stream)))
        self.pending()
        ticked = self.tick('2026-11-03T00:01:00Z')
        self.assertEqual(ticked.returncode, 0, ticked.stderr)
        self.assertEqual([path for path, _ in self.posts()], ['/api/sessions/retired/archive', '/api/sessions/successor/prompt'])
        record = self.state(self.stream)['deliveries'][self.state(self.stream)['tick_delivery']]
        self.assertEqual((record['session'], record['state']), ('successor', 'transport_accepted'))

    def test_supported_archive_then_adoption_dispatches_without_reopening_the_predecessor(self):
        archived = subprocess.run([str(ROOT / 'bin/pi-web-cli'), 'archive', 'retired'], env=self.env, capture_output=True, text=True)
        self.assertEqual(archived.returncode, 0, archived.stderr)
        self.assertIn('retired', self.stub.archived_sessions)
        self.stub.requests.clear()
        self.adopt()
        self.pending()
        ticked = self.tick('2026-11-03T00:01:00Z')
        self.assertEqual(ticked.returncode, 0, ticked.stderr)
        self.assertEqual([path for path, _ in self.posts()], ['/api/sessions/successor/prompt'])
        self.assertFalse(any(path == '/api/sessions/retired/status' for _, path, _, _ in self.stub.requests))

    def test_retirement_retains_busy_queues_questions_and_unknown_callback_ownership(self):
        self.adopt()
        cases = [
            {'isStreaming': True}, {'isCompacting': True}, {'isBashRunning': True},
            {'pendingMessageCount': 1}, {'queuedMessages': [{'kind': 'followUp', 'text': 'Retain this input'}]},
            {'pendingAsk': {'id': 'human-question'}}, {'pendingDialogs': [{'id': 'extension-question'}]},
            {'rotationSafety': None},
            {'rotationSafety': {**self.retired_status['rotationSafety'], 'callbacksKnown': False}},
            {'rotationSafety': {**self.retired_status['rotationSafety'], 'nativeChildCallbacks': ['child']}},
            {'rotationSafety': {**self.retired_status['rotationSafety'], 'entryId': None}},
            {'sessionId': 'retired-prefix-match'},
            {'automaticAdmission': None},
        ]
        for changed in cases:
            with self.subTest(changed=changed):
                original = self.retired_status
                self.retired_status = {**original, **changed}
                control = self.stub.automatic_admissions.pop('retired') if 'automaticAdmission' in changed else None
                self.routes()
                self.pending()
                self.assert_blocked(self.tick('2026-11-03T00:01:00Z'))
                self.retired_status = original
                if control is not None:
                    self.stub.automatic_admissions['retired'] = control

    def test_wrong_registry_cwd_and_duplicate_native_ids_prevent_retirement(self):
        self.adopt()
        table = self.stream / 'threads.tsv'
        registry = table.read_text()
        cases = [
            (registry.replace(str(self.stream), str(self.fx.alpha), 1), self.infos),
            (registry, self.infos + [self.infos[0]]),
            (registry, self.infos + [self.infos[1]]),
        ]
        for rows, infos in cases:
            with self.subTest(rows=rows, infos=infos):
                table.write_text(rows)
                original = self.infos
                self.infos = infos
                self.routes()
                self.pending()
                self.assert_blocked(self.tick('2026-11-03T00:01:00Z'))
                self.assertEqual(table.read_text(), rows)
                self.infos = original

    def test_unregistered_candidates_stay_diagnostic_and_block_retirement_and_dispatch(self):
        self.adopt()
        self.infos.append(info('unregistered', str(self.stream), self.log_path('unregistered')))
        self.routes()
        self.pending()
        observed = self.run_streams('status', 'etl', '--json')
        entry, = json.loads(observed.stdout)['streams']
        self.assertEqual(entry['dispatchBlockers'][0]['kind'], 'unregistered-coordinator-candidate')
        self.assertEqual(entry['coordinator']['session'], 'successor')
        self.assertEqual(self.posts(), [])
        self.assert_blocked(self.tick('2026-11-03T00:01:00Z'))

    def test_lost_archive_reply_is_durable_and_never_replayed_after_restart(self):
        self.adopt()
        self.routes(archive_code=503, archive_reply={'error': 'Controlled lost archive reply'})
        self.pending()
        failed = self.tick('2026-11-03T00:01:00Z')
        self.assertEqual(failed.returncode, 1, failed.stdout)
        self.assertEqual(self.state(self.stream).get('terminal_sessions', {}).get('retired', {}).get('state'), 'uncertain', failed.stderr)
        self.assertEqual([path for path, _ in self.posts()], ['/api/sessions/retired/archive'])
        self.routes()
        self.assert_blocked(self.tick('2026-11-03T00:02:00Z'))
        before = snapshot(self.stream)
        report = self.run_streams('status', 'etl', '--json')
        entry, = json.loads(report.stdout)['streams']
        self.assertEqual(entry['dispatchBlockers'][0]['kind'], 'retired-native-residue')
        self.assertEqual(snapshot(self.stream), before)
        self.assertEqual(self.posts(), [])

    def test_confirmed_reply_without_native_archive_listing_does_not_enable_dispatch(self):
        self.adopt()
        self.stub.simulate_session_lifecycle = False
        self.pending()
        failed = self.tick('2026-11-03T00:01:00Z')
        self.assertEqual(failed.returncode, 1, failed.stdout)
        self.assertEqual([path for path, _ in self.posts()], ['/api/sessions/retired/archive'])
        self.assertEqual(self.state(self.stream)['terminal_sessions']['retired']['state'], 'archived')
        self.assert_blocked(self.tick('2026-11-03T00:02:00Z'))

    def test_native_refusal_is_retained_without_archive_or_dispatch_replay(self):
        self.adopt()
        self.routes(archive_code=409, archive_reply={'error': 'Native checkpoint ownership changed'})
        self.pending()
        failed = self.tick('2026-11-03T00:01:00Z')
        self.assertEqual(failed.returncode, 1, failed.stdout)
        self.assertEqual(self.state(self.stream).get('terminal_sessions', {}).get('retired', {}).get('state'), 'refused', failed.stderr)
        self.routes()
        self.assert_blocked(self.tick('2026-11-03T00:02:00Z'))

    def test_explicit_drive_off_prevents_reconciliation_and_all_native_queries(self):
        self.adopt()
        stopped = self.run_streams('drive', 'etl', 'off')
        self.assertEqual(stopped.returncode, 1, stopped.stderr)
        self.assertEqual(self.state(self.stream)['drive']['stop_intent'], 'operator-off')
        self.stub.requests.clear()
        self.pending()
        ticked = self.tick('2026-11-03T00:01:00Z')
        self.assertEqual(ticked.returncode, 0, ticked.stderr)
        self.assertEqual(self.stub.requests, [])
        observed = self.run_streams('status', 'etl', '--json')
        entry, = json.loads(observed.stdout)['streams']
        self.assertEqual(entry['nativeObservation'], 'not-queried-explicit-drive-off')
        self.assertEqual(self.stub.requests, [])
