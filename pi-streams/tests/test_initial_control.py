from __future__ import annotations

import copy
import json

import test_drive as cases
from tick_support import TickCase, reply, row


class InitialControlTests(TickCase):
    def setUp(self):
        super().setUp()
        self.stream = self.make_stream(self.home, 'etl', row('coord', 'coordinator', str(self.home / 'etl')))
        self.write_log('coord', str(self.stream), reply('Previous authorized work finished.'))
        self.stub.reflect_control_goals = True
        self.goal = '<the single human-authorized outcome>'
        (self.stream / 'log').mkdir(exist_ok=True)
        (self.stream / 'log/tick-state.json').write_text('{}')
        self.routes()

    def drive(self):
        result = self.run_streams('drive', 'etl', 'status')
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    routes = cases.DriveTests.routes
    goal_posts = cases.DriveTests.goal_posts

    def unarmed(self):
        self.stub.automatic_admissions['coord'] = {'sessionId': 'coord', 'cwd': str(self.stream), 'generation': 'unarmed', 'allowed': False, 'durable': False}
        self.routes()

    def bootstrap_route(self, *, stopped=False, invalid=None):
        def receive(body):
            self.assertEqual(body, {'allowed': True, 'initializeIfAbsent': True})
            remote = {'sessionId': 'coord', 'cwd': str(self.stream), 'generation': 'genuine-stop' if stopped else 'initial-epoch', 'allowed': not stopped, 'durable': True}
            if invalid:
                remote.update(invalid)
            self.stub.automatic_admissions['coord'] = remote
            return 200, remote
        self.stub.set_routes([('POST', '/api/sessions/coord/automatic-admission/initialize', 200, receive), *self.stub.routes])

    def test_explicit_drive_bootstraps_the_exact_unarmed_coordinator_without_a_prompt(self):
        self.unarmed()
        self.bootstrap_route()
        before = {name: (self.stream / name).read_bytes() for name in ('STATE.md', 'threads.tsv')}
        result = self.run_streams('drive', 'etl', 'on')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.drive()['enabled'], self.drive()['remote_state'], self.drive()['remote_generation']), (True, 'on-confirmed', 'initial-epoch'))
        self.assertEqual({name: (self.stream / name).read_bytes() for name in before}, before)
        self.assertEqual([(r[1], r[3]) for r in self.stub.requests if r[0] == 'POST'], [('/api/sessions/coord/automatic-admission/initialize', {'allowed': True, 'initializeIfAbsent': True})])

    def test_explicit_resume_uses_bootstrap_for_an_initial_legacy_coordinator(self):
        self.unarmed()
        self.bootstrap_route()
        result = self.run_streams('resume', 'etl', '--all-parked')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.drive()['enabled'], self.drive()['remote_state'], self.drive()['remote_generation']), (True, 'on-confirmed', 'initial-epoch'))
        self.assertEqual([(r[1], r[3]) for r in self.stub.requests if r[0] == 'POST'], [('/api/sessions/coord/automatic-admission/initialize', {'allowed': True, 'initializeIfAbsent': True})])

    def test_ordinary_tick_does_not_infer_bootstrap_from_goals(self):
        self.unarmed()
        self.bootstrap_route()
        result = self.tick('2026-10-06T12:00:00Z')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn('durable automatic admission capability is unavailable', result.stderr)
        self.assertFalse(self.drive()['enabled'])
        self.assertFalse(self.stub.automatic_admissions['coord']['durable'])
        self.assertEqual([r for r in self.stub.requests if r[0] == 'POST'], [])

    def test_concurrent_durable_stop_is_preserved_without_a_second_rearm(self):
        self.unarmed()
        self.bootstrap_route(stopped=True)
        result = self.run_streams('drive', 'etl', 'on')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.drive()['enabled'], self.drive()['remote_state']), (False, 'on-unconfirmed'))
        self.assertEqual(self.stub.automatic_admissions['coord']['generation'], 'genuine-stop')
        self.assertFalse(self.stub.automatic_admissions['coord']['allowed'])
        self.assertEqual(len([r for r in self.stub.requests if r[0] == 'POST']), 1)

    def test_later_stop_blocks_the_first_automatic_goal_without_bootstrapping_again(self):
        self.unarmed()
        self.bootstrap_route()
        result = self.run_streams('drive', 'etl', 'on')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.stub.automatic_admissions['coord'].update(generation='later-stop', allowed=False)
        self.stub.requests.clear()
        result = self.tick('2026-10-06T12:00:00Z')
        self.assertEqual(result.returncode, 0, result.stderr)
        record = self.state(self.stream)['deliveries'][self.drive()['current_delivery']]
        self.assertEqual(record['state'], 'blocked')
        self.assertEqual(self.stub.automatic_admissions['coord']['generation'], 'later-stop')
        self.assertEqual([r for r in self.stub.requests if r[0] == 'POST'], [])

    def test_undurable_noninitial_generation_is_not_bootstrapped(self):
        self.unarmed()
        self.stub.automatic_admissions['coord']['generation'] = 'failed-real-epoch'
        result = self.run_streams('drive', 'etl', 'on')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('capability', result.stderr)
        self.assertEqual([r for r in self.stub.requests if r[0] == 'POST'], [])

    def test_initial_identity_mismatch_does_not_publish_control(self):
        self.unarmed()
        self.stub.automatic_admissions['coord']['sessionId'] = 'some-other-session'
        result = self.run_streams('drive', 'etl', 'on')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual([r for r in self.stub.requests if r[0] == 'POST'], [])
        self.assertFalse(self.drive()['enabled'])

    def test_missing_capability_does_not_publish_control(self):
        self.unarmed()
        self.stub.automatic_admissions.pop('coord')
        result = self.run_streams('drive', 'etl', 'on')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual([r for r in self.stub.requests if r[0] == 'POST'], [])
        self.assertFalse(self.drive()['enabled'])

    def test_historical_negative_marker_does_not_block_bootstrap(self):
        self.unarmed()
        self.bootstrap_route()
        charter = self.stream / 'STATE.md'
        charter.write_text(charter.read_text().replace('## Goals\n', '## Goals\nratified: no\n', 1))
        result = self.run_streams('drive', 'etl', 'on')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([r[1] for r in self.stub.requests if r[0] == 'POST'], ['/api/sessions/coord/automatic-admission/initialize'])
        self.assertTrue(self.stub.automatic_admissions['coord']['durable'])
        self.assertTrue(self.drive()['enabled'])

    def test_bootstrap_rejects_an_undurable_receipt(self):
        self.unarmed()
        self.bootstrap_route(invalid={'durable': False})
        result = self.run_streams('drive', 'etl', 'on')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.drive()['enabled'], self.drive()['remote_state']), (False, 'on-unconfirmed'))

    def test_bootstrap_rejects_a_receipt_for_another_cwd(self):
        self.unarmed()
        self.bootstrap_route(invalid={'cwd': str(self.tmp / 'wrong-cwd')})
        result = self.run_streams('drive', 'etl', 'on')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.drive()['enabled'], self.drive()['remote_state']), (False, 'on-unconfirmed'))

    def test_bootstrap_does_not_resume_a_historical_parked_worker_or_clear_its_queue(self):
        self.unarmed()
        table = self.stream / 'threads.tsv'
        table.write_text(table.read_text() + row('historical-worker', 'research', str(self.fx.alpha_wt)).replace('\tactive\t', '\tparked\t'))
        self.write_log('historical-worker', str(self.fx.alpha_wt), reply('Retain the old bounded assignment.'))
        data = self.state(self.stream)
        data['sessions'] = {'historical-worker': {'replay': [['unconfirmed external submission', 'steer']]}}
        (self.stream / 'log/tick-state.json').write_text(json.dumps(data))
        before = table.read_bytes()
        queue = copy.deepcopy(data['sessions'])
        self.bootstrap_route()
        result = self.run_streams('drive', 'etl', 'on')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.drive()['enabled'])
        self.assertEqual(table.read_bytes(), before)
        self.assertEqual(self.state(self.stream)['sessions'], queue)
        self.assertEqual([r[1] for r in self.stub.requests if r[0] == 'POST'], ['/api/sessions/coord/automatic-admission/initialize'])

    def test_old_native_without_the_initialize_endpoint_cannot_fall_back_to_unconditional_rearm(self):
        self.unarmed()
        self.stub.set_routes([('POST', '/api/sessions/coord/automatic-admission/initialize', 404, {'error': 'Unsupported endpoint'}), *self.stub.routes])
        result = self.run_streams('drive', 'etl', 'on')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.drive()['enabled'], self.drive()['remote_state']), (False, 'on-unconfirmed'))
        self.assertEqual(self.stub.automatic_admissions['coord']['generation'], 'unarmed')
        self.assertFalse(self.stub.automatic_admissions['coord']['durable'])
        self.assertEqual([r[1] for r in self.stub.requests if r[0] == 'POST'], ['/api/sessions/coord/automatic-admission/initialize'])

    def test_existing_durable_epoch_still_uses_exact_generation_cas(self):
        self.stub.simulate_conditional_controls = True
        self.stub.automatic_admissions['coord'].update(generation='genuine-existing-stop', allowed=False)
        self.routes()
        result = self.run_streams('drive', 'etl', 'on')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.drive()['remote_generation'], 'genuine-existing-stop-next')
        self.assertEqual([r[3] for r in self.stub.requests if r[0] == 'POST'], [{'allowed': True, 'expectedGeneration': 'genuine-existing-stop'}])
