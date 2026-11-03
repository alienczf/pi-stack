from __future__ import annotations

import json
from pathlib import Path
import sys
from unittest.mock import patch

import test_drive as cases
from support import ROOT
from tick_support import TickCase, reply, row

sys.path.insert(0, str(ROOT / 'pi-streams'))
from engine import artifacts, blocked_goals, delivery, sessionlog


class BlockedGoalTests(TickCase):
    def setUp(self):
        super().setUp()
        self.stream = self.make_stream(self.home, 'etl', row('coord', 'coordinator', str(self.home / 'etl')))
        self.write_log('coord', str(self.stream), reply('Previous authorized work finished.'))
        self.stub.reflect_control_goals = True
        self.goal = '<the single human-authorized outcome>'
        self.routes()

    def routes(self, **kwargs):
        cases.DriveTests.routes(self, **kwargs)
        self.leaf = json.loads(Path(self.log_path('coord')).read_text().splitlines()[-1])['id']
        self.stub.set_routes([(method, path, code, {**body, 'rotationSafety': {'entryId': self.leaf}} if path == '/api/sessions/coord/status' else body) for method, path, code, body in self.stub.routes])

    def append_turn(self, answer, *, goal=None):
        source = Path(self.log_path('coord'))
        for message in [
            {'role': 'user', 'content': '<skill name="poteto-mode" location="fixture">\nBounded fixture.\n</skill>\n\n' + (goal or self.goal)},
            reply(answer),
        ]:
            entry = {'type': 'message', 'id': f'e{len(source.read_text().splitlines())}', 'parentId': self.leaf, 'message': message}
            with source.open('a') as handle:
                handle.write(json.dumps(entry) + '\n')
            self.leaf = entry['id']
        self.routes()

    def complete(self, answer):
        for goal in self.stub.control_goals.values():
            goal['state'] = 'ended'
        delivery.observe_control_locked(self.stream, self.drive()['current_delivery'], state='ended')
        self.append_turn(answer)

    def observe(self, *, dispatch=''):
        blocked_goals.observe(self.stream, self.goal, 'coord', self.log_path('coord'), dispatch=dispatch, leaf=self.leaf)

    enable = cases.DriveTests.enable
    drive = cases.DriveTests.drive
    goal_posts = cases.DriveTests.goal_posts

    def test_fourth_blocked_goal_is_suppressed_across_ticks_but_drive_intent_and_new_unit_survive(self):
        self.enable()
        for number in range(3):
            ticked = self.tick(f'2026-11-03T00:0{number}:00Z')
            self.assertEqual(ticked.returncode, 0, ticked.stderr)
            self.assertEqual(len(self.goal_posts()), 1)
            self.complete('BLOCKED_UNIT_91c is blocked. The required toolchain is unavailable. Do not repeat this unit.')
        for number in range(3, 6):
            ticked = self.tick(f'2026-11-03T00:0{number}:00Z')
            self.assertEqual(ticked.returncode, 0, ticked.stderr)
            self.assertEqual(self.goal_posts(), [])
        records = self.state(self.stream)['blocked_goals']
        self.assertEqual(len(records), 1)
        record = next(iter(records.values()))
        self.assertEqual((len(record['sent']), len(record['received']), record['disposition']), (3, 3, 'suppressed'))
        self.assertTrue(self.drive()['enabled'])
        self.assertEqual((self.stream / 'STATE.md').read_text().count('Blocked-goal escalation'), 1)
        objective = self.tmp / 'different-unit.txt'
        objective.write_text('Review the already authorized offline test unit.')
        changed = self.run_streams('state', 'objective', 'etl', '--body-file', str(objective))
        self.assertEqual(changed.returncode, 0, changed.stderr)
        ticked = self.tick('2026-11-03T00:10:00Z')
        self.assertEqual(ticked.returncode, 0, ticked.stderr)
        self.assertEqual(self.goal_posts()[0][3]['potetoGoal'], 'Review the already authorized offline test unit.')

    def test_progress_resets_repetition_and_one_block_after_progress_does_not_count_old_successes(self):
        self.enable()
        for number, answer in enumerate(['Finite unit complete. Verified the artifact.', 'Passed the permitted integration check.', 'Blocked. A new dependency is unavailable.']):
            ticked = self.tick(f'2026-11-03T01:0{number}:00Z')
            self.assertEqual(ticked.returncode, 0, ticked.stderr)
            self.assertEqual(len(self.goal_posts()), 1)
            self.complete(answer)
        ticked = self.tick('2026-11-03T01:04:00Z')
        self.assertEqual(ticked.returncode, 0, ticked.stderr)
        self.assertEqual(len(self.goal_posts()), 1)
        record = self.state(self.stream)['blocked_goals'][blocked_goals.fingerprint(self.goal)]
        self.assertEqual(len(record['received']), 1)

    def test_transcript_and_ack_views_share_one_prompt_outcome_and_progress_clears_suppression(self):
        self.enable()
        for number in range(3):
            ticked = self.tick(f'2026-11-03T02:0{number}:00Z')
            self.assertEqual(ticked.returncode, 0, ticked.stderr)
            self.complete('Blocked. The authorized dependency remains unavailable.')
            self.observe()
            blocked_goals.receive(self.stream, self.goal, 'delivery:' + self.drive()['current_delivery'], sent=self.drive()['current_delivery'])
        self.assertFalse(blocked_goals.permit(self.stream, self.goal))
        record = self.state(self.stream)['blocked_goals'][blocked_goals.fingerprint(self.goal)]
        self.assertEqual((len(record['sent']), len(record['received'])), (3, 3))
        identity = self.drive()['current_delivery']
        proof = self.stream / 'context/resolved.md'
        proof.parent.mkdir(exist_ok=True)
        proof.write_text('Installed the authorized dependency. Verified its checksum and passed the integration check.')
        with patch.object(delivery, '_require_destination', return_value={}):
            delivery.acknowledge_locked(self.stream, identity, 'coord', 'consumed', 'Read the exact instruction.')
            delivery.acknowledge_locked(self.stream, identity, 'coord', 'applied', 'Verified the dependency.', evidence='context/resolved.md')
        self.assertTrue(blocked_goals.permit(self.stream, self.goal))
        self.assertEqual(self.state(self.stream)['blocked_goals'][blocked_goals.fingerprint(self.goal)]['received'], [])
        self.assertTrue(self.drive()['enabled'])

    def test_checkpoint_is_saved_before_transport_and_retained_on_queued_reconciliation(self):
        self.enable()
        ticked = self.tick('2026-11-03T03:00:00Z')
        self.assertEqual(ticked.returncode, 0, ticked.stderr)
        identity = self.drive()['current_delivery']
        checkpoint = delivery._get(self.stream, identity).control.checkpoint
        self.assertEqual((checkpoint['entryId'], checkpoint['lines']), ('e1', 2))
        sessionlog.read_record(Path(self.log_path('coord')), 'coord', checkpoint['entryId'], checkpoint['sha256'])
        self.append_turn('Completed unrelated work.', goal='A different prompt')
        self.assertEqual(self.tick('2026-11-03T03:01:00Z').returncode, 0)
        self.assertEqual(delivery._get(self.stream, identity).control.checkpoint, checkpoint)

    def test_handled_controls_cannot_reuse_stale_success_or_reset_blocked_acknowledgements(self):
        self.enable()
        for number in range(3):
            ticked = self.tick(f'2026-11-03T04:0{number}:00Z')
            self.assertEqual(ticked.returncode, 0, ticked.stderr)
            for goal in self.stub.control_goals.values():
                goal['state'] = 'ended'
            identity = self.drive()['current_delivery']
            delivery.observe_control_locked(self.stream, identity, state='ended')
            blocked_goals.receive(self.stream, self.goal, 'delivery:' + identity, sent=identity)
            self.observe()
        self.assertFalse(blocked_goals.permit(self.stream, self.goal))
        outcomes = self.state(self.stream)['blocked_goals'][blocked_goals.fingerprint(self.goal)]['outcomes']
        self.assertEqual([value['state'] for value in outcomes.values()], ['blocked'] * 3)
        self.assertTrue(all('native' not in value for value in outcomes.values()))

    def test_unrelated_or_later_user_turns_and_missing_provenance_produce_no_outcome(self):
        self.enable()
        self.assertEqual(self.tick('2026-11-03T05:00:00Z').returncode, 0)
        identity = self.drive()['current_delivery']
        delivery.observe_control_locked(self.stream, identity, state='ended')
        self.append_turn('Blocked. Unrelated work is unavailable.', goal='Another goal')
        self.observe()
        self.assertNotIn('blocked_goals', self.state(self.stream))
        self.append_turn('Blocked. The exact goal is unavailable.')
        self.observe()
        self.assertNotIn('blocked_goals', self.state(self.stream))
        record = delivery._get(self.stream, identity)
        record.control.checkpoint = None
        delivery._save(self.stream, record)
        self.observe()
        self.assertNotIn('blocked_goals', self.state(self.stream))

    def test_sibling_results_are_ignored_and_a_result_maps_to_only_one_dispatch(self):
        self.enable()
        self.assertEqual(self.tick('2026-11-03T06:00:00Z').returncode, 0)
        first = delivery._get(self.stream, self.drive()['current_delivery'])
        self.complete('Blocked. Missing the authorized dependency.')
        active_leaf = self.leaf
        source = Path(self.log_path('coord'))
        with source.open('a') as handle:
            handle.write(json.dumps({'type': 'message', 'id': 'sibling-success', 'parentId': 'e1', 'message': reply('Completed and verified unrelated work.')}) + '\n')
        self.observe()
        record = self.state(self.stream)['blocked_goals'][blocked_goals.fingerprint(self.goal)]
        self.assertEqual(record['outcomes'][first.id]['state'], 'blocked')
        first.id = 'duplicate-dispatch'
        first.control.sequence += 1
        delivery._save(self.stream, first)
        self.observe(dispatch=first.id)
        self.assertEqual(len(self.state(self.stream)['blocked_goals'][blocked_goals.fingerprint(self.goal)]['outcomes']), 1)
        self.leaf = 'sibling-success'
        self.observe(dispatch=first.id)
        self.leaf = active_leaf
        self.assertEqual(len(self.state(self.stream)['blocked_goals'][blocked_goals.fingerprint(self.goal)]['outcomes']), 1)

    def test_rewritten_checkpoint_and_preexisting_sibling_user_cannot_prove_a_new_turn(self):
        self.append_turn('Blocked. Historical sibling.')
        historical_leaf = self.leaf
        self.leaf = 'e1'
        self.stub.set_routes([(method, path, code, {**body, 'rotationSafety': {'entryId': self.leaf}} if path == '/api/sessions/coord/status' else body) for method, path, code, body in self.stub.routes])
        self.enable()
        self.assertEqual(self.tick('2026-11-03T07:00:00Z').returncode, 0)
        delivery.observe_control_locked(self.stream, self.drive()['current_delivery'], state='ended')
        self.leaf = historical_leaf
        self.observe()
        self.assertNotIn('blocked_goals', self.state(self.stream))
        source = Path(self.log_path('coord'))
        source.write_text(source.read_text().replace('Previous authorized work finished.', 'Changed historical bytes.'))
        self.append_turn('Blocked. A new result after rewritten history.')
        self.observe()
        self.assertNotIn('blocked_goals', self.state(self.stream))

    def test_legacy_native_outcomes_are_retained_but_cannot_suppress_or_erase_acknowledgements(self):
        key = blocked_goals.fingerprint(self.goal)
        for acknowledged in [False, True]:
            with self.subTest(acknowledged=acknowledged):
                data = artifacts._read_tick_data(self.stream)
                legacy = {'version': 2, 'sent': [], 'received': [], 'outcomes': {f'old-{number}': {'sequence': number, 'state': 'progress' if acknowledged and number == 3 else 'blocked', 'evidence': ([f'delivery:old-{number}'] if acknowledged else []) + ['coord:stale:hash']} for number in range(1, 4)}}
                data['blocked_goals'] = {key: legacy}
                artifacts._save_tick_data(self.stream, data)
                self.assertEqual(blocked_goals.permit(self.stream, self.goal), not acknowledged)
                retained = self.state(self.stream)['blocked_goals'][key]
                self.assertEqual(retained['legacy'], legacy)
                self.assertEqual(len(retained['outcomes']), 3 if acknowledged else 0)

    def test_correlated_progress_resets_prior_blocked_outcomes(self):
        self.enable()
        for number, answer in enumerate(['Blocked. Missing dependency.', 'Installed and verified the authorized dependency.', 'Blocked. A different dependency is unavailable.']):
            self.assertEqual(self.tick(f'2026-11-03T08:0{number}:00Z').returncode, 0)
            self.complete(answer)
            self.observe()
        self.assertTrue(blocked_goals.permit(self.stream, self.goal))
        record = self.state(self.stream)['blocked_goals'][blocked_goals.fingerprint(self.goal)]
        self.assertEqual([item['state'] for item in sorted(record['outcomes'].values(), key=lambda item: item['sequence'])], ['blocked', 'progress', 'blocked'])
        self.assertEqual(len(record['received']), 1)

    def test_successful_finite_units_are_not_blocked_repeats(self):
        self.enable()
        for number in range(5):
            ticked = self.tick(f'2026-11-03T00:0{number}:00Z')
            self.assertEqual(ticked.returncode, 0, ticked.stderr)
            self.assertEqual(len(self.goal_posts()), 1)
            self.complete('Finite unit complete. No blockers. The standing goal is unfinished.')
        self.assertTrue(self.drive()['enabled'])
        self.assertNotIn('Blocked-goal escalation', (self.stream / 'STATE.md').read_text())
