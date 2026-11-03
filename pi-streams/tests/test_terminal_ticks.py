from __future__ import annotations

from tick_support import TickCase, info, row, status


class TerminalTickTests(TickCase):
    def test_closed_unratified_coordinator_archives_once_without_dispatch_or_new_gate(self):
        stream = self.make_stream(self.home, 'etl', row('coord', 'coordinator', str(self.home / 'etl')))
        source = (stream / 'STATE.md').read_text().replace('ratified: 2026-10-06 fixture source', 'ratified: no')
        authority = source.split('ratified: ', 1)[1].splitlines()[0]
        source = source.replace('ratified: ' + authority, 'ratified: no', 1)
        (stream / 'STATE.md').write_text(source)
        closed = self.run_streams('close', 'etl')
        self.assertEqual(closed.returncode, 0, closed.stderr)
        for index in range(3):
            ticked = self.tick(f'2026-11-03T00:0{index}:00Z')
            self.assertEqual(ticked.returncode, 0, ticked.stderr)
            if index == 0:
                self.assertEqual([r[1] for r in self.stub.requests if r[0] == 'POST'], ['/api/sessions/coord/archive'])
            else:
                self.assertEqual(self.stub.requests, [])
        self.assertIn('coord\tcoordinator', self.rows(stream))
        self.assertIn('\tarchived\t', self.rows(stream))

    def test_definite_missing_worker_is_not_queried_on_later_ticks(self):
        stream = self.make_stream(self.home, 'etl', row('coord', 'coordinator', str(self.home / 'etl')) + row('dead-worker', 'review', '/owned/review'))
        self.stub.set_routes([('GET', '/api/sessions/dead-worker/status', 404, {'error': 'Session not found'})])
        for index in range(3):
            ticked = self.tick(f'2026-11-03T00:0{index}:00Z')
            self.assertEqual(ticked.returncode, 0, ticked.stderr)
            calls = [r for r in self.stub.requests if r[1] == '/api/sessions/dead-worker/status']
            self.assertEqual(len(calls), 1 if index == 0 else 0)
        terminal = self.state(stream)['terminal_sessions']['dead-worker']
        self.assertEqual(terminal['state'], 'missing')
        self.assertIn('dead-worker\treview', self.rows(stream))
        self.assertNotIn('invented handover', self.rows(stream))

    def test_known_archive_rejection_is_not_uncertainty_or_a_per_tick_retry(self):
        stream = self.make_stream(self.home, 'etl', row('coord', 'coordinator', str(self.home / 'etl'), status='done'))
        self.stub.set_routes([('POST', '/api/sessions/coord/archive', 409, {'error': 'Definite rejection before archive'})])
        first = self.tick('2026-11-03T00:00:00Z')
        self.assertNotEqual(first.returncode, 0)
        self.assertEqual(self.state(stream)['terminal_sessions']['coord']['state'], 'refused')
        again = self.tick('2026-11-03T00:01:00Z')
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(self.stub.requests, [])
        self.assertIn('\tdone\t', self.rows(stream))

    def test_known_archived_worker_is_not_reopened_and_registry_evidence_survives(self):
        stream = self.make_stream(self.home, 'etl', row('coord', 'coordinator', str(self.home / 'etl')) + row('old-worker', 'review', '/owned/review'))
        self.stub.set_routes([('GET', '/api/sessions/old-worker/status', 409, {'error': 'Session is archived'})])
        for index in range(3):
            ticked = self.tick(f'2026-11-03T00:0{index}:00Z')
            self.assertEqual(ticked.returncode, 0, ticked.stderr)
            self.assertEqual(sum(r[1] == '/api/sessions/old-worker/status' for r in self.stub.requests), 1 if index == 0 else 0)
            self.assertFalse(any(r[1] == '/api/sessions/old-worker/archive' for r in self.stub.requests))
        self.assertEqual(self.state(stream)['terminal_sessions']['old-worker']['state'], 'archived')
        self.assertIn('old-worker\treview', self.rows(stream))

    def test_archived_listing_wins_even_when_native_status_still_returns200(self):
        stream = self.make_stream(self.home, 'etl', row('coord', 'coordinator', str(self.home / 'etl')) + row('old-worker', 'review', '/owned/review'))
        self.stub.set_routes([('GET', '/api/sessions/old-worker/status', 200, {**status('old-worker'), 'conditionalAdmissionSupport': 'generation-cas-v1'}), ('GET', '/api/sessions', 200, [info('coord', str(stream), self.log_path('coord')), {**info('old-worker', '/owned/review', '/missing/original.jsonl'), 'archived': True}])])
        for index in range(3):
            ticked = self.tick(f'2026-11-03T03:0{index}:00Z')
            self.assertEqual(ticked.returncode, 0, ticked.stderr)
            self.assertEqual(sum(r[1] == '/api/sessions/old-worker/status' for r in self.stub.requests), 1 if index == 0 else 0)
        self.assertEqual(self.state(stream)['terminal_sessions']['old-worker']['state'], 'archived')
        self.assertIn('old-worker\treview', self.rows(stream))

    def test_close_retains_missing_worker_registry_and_handover_without_claiming_archive_success(self):
        stream = self.make_stream(self.home, 'etl', row('coord', 'coordinator', str(self.home / 'etl')) + row('missing-worker', 'review', '/owned/review'))
        handover = stream / 'handover/review/missing-worker.md'
        handover.parent.mkdir(parents=True)
        handover.write_text('session: missing-worker\nVerified fixture handover before supported fixture deletion.\n')
        self.stub.set_routes([('GET', '/api/sessions/missing-worker/status', 404, {'error': 'Session not found'})])
        self.assertEqual(self.tick('2026-11-03T03:00:00Z').returncode, 0)
        self.stub.requests.clear()
        closed = self.run_streams('close', 'etl')
        self.assertEqual(closed.returncode, 0, closed.stderr)
        self.assertIn('missing missing-worker review', closed.stdout)
        self.assertNotIn('archived missing-worker', closed.stdout)
        self.assertIn('missing-worker\treview', self.rows(stream))
        self.assertTrue(handover.is_file())
        self.assertFalse(any(r[1].startswith('/api/sessions/missing-worker/') for r in self.stub.requests))

    def test_unknown_archive_effect_is_retained_without_repeated_native_calls(self):
        stream = self.make_stream(self.home, 'etl', row('coord', 'coordinator', str(self.home / 'etl'), status='done'))
        self.stub.set_routes([('POST', '/api/sessions/coord/archive', 503, {'error': 'Controlled lost archive reply'})])
        first = self.tick('2026-11-03T00:00:00Z')
        self.assertNotEqual(first.returncode, 0)
        self.assertEqual(self.state(stream)['terminal_sessions']['coord']['state'], 'uncertain')
        for index in range(1, 3):
            ticked = self.tick(f'2026-11-03T00:0{index}:00Z')
            self.assertEqual(ticked.returncode, 0, ticked.stderr)
            self.assertEqual(self.stub.requests, [])
        self.assertIn('\tdone\t', self.rows(stream))
