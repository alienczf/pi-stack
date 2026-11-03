from __future__ import annotations

import json
import sys

import test_drive as cases
from support import ROOT
from tick_support import TickCase, reply, row

sys.path.insert(0, str(ROOT / 'pi-streams'))
from engine import blocked_goals


class BlockedGoalTests(TickCase):
    def setUp(self):
        super().setUp()
        self.stream = self.make_stream(self.home, 'etl', row('coord', 'coordinator', str(self.home / 'etl')))
        self.write_log('coord', str(self.stream), reply('Previous authorized work finished.'))
        self.stub.reflect_control_goals = True
        self.goal = '<the single human-authorized outcome>'
        self.routes()

    routes = cases.DriveTests.routes
    enable = cases.DriveTests.enable
    drive = cases.DriveTests.drive
    goal_posts = cases.DriveTests.goal_posts

    def test_fourth_blocked_goal_is_suppressed_across_ticks_but_drive_intent_and_new_unit_survive(self):
        self.enable()
        for number in range(3):
            ticked = self.tick(f'2026-11-03T00:0{number}:00Z')
            self.assertEqual(ticked.returncode, 0, ticked.stderr)
            self.assertEqual(len(self.goal_posts()), 1)
            for goal in self.stub.control_goals.values():
                goal['state'] = 'ended'
            blocked = reply('BLOCKED_UNIT_91c is blocked. The required toolchain is unavailable. Do not repeat this unit.')
            blocked['timestamp'] += number
            self.write_log('coord', str(self.stream), blocked)
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
            for goal in self.stub.control_goals.values():
                goal['state'] = 'ended'
            self.write_log('coord', str(self.stream), reply(answer))
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
            for goal in self.stub.control_goals.values():
                goal['state'] = 'ended'
            blocked = reply('Blocked. The authorized dependency remains unavailable.')
            blocked['timestamp'] += number
            self.write_log('coord', str(self.stream), blocked)
            blocked_goals.observe(self.stream, self.goal, 'coord', self.log_path('coord'))
            blocked_goals.receive(self.stream, self.goal, 'delivery:' + self.drive()['current_delivery'], sent=self.drive()['current_delivery'])
        self.assertFalse(blocked_goals.permit(self.stream, self.goal))
        record = self.state(self.stream)['blocked_goals'][blocked_goals.fingerprint(self.goal)]
        self.assertEqual((len(record['sent']), len(record['received'])), (3, 3))
        self.write_log('coord', str(self.stream), reply('Installed the authorized dependency. Verified its checksum and passed the integration check.'))
        blocked_goals.observe(self.stream, self.goal, 'coord', self.log_path('coord'))
        self.assertTrue(blocked_goals.permit(self.stream, self.goal))
        self.assertEqual(self.state(self.stream)['blocked_goals'][blocked_goals.fingerprint(self.goal)]['received'], [])
        self.assertTrue(self.drive()['enabled'])

    def test_successful_finite_units_are_not_blocked_repeats(self):
        self.enable()
        for number in range(5):
            for goal in self.stub.control_goals.values():
                goal['state'] = 'ended'
            self.write_log('coord', str(self.stream), reply('Finite unit complete. No blockers. The standing goal is unfinished.'))
            ticked = self.tick(f'2026-11-03T00:0{number}:00Z')
            self.assertEqual(ticked.returncode, 0, ticked.stderr)
            self.assertEqual(len(self.goal_posts()), 1)
        self.assertTrue(self.drive()['enabled'])
        self.assertNotIn('Blocked-goal escalation', (self.stream / 'STATE.md').read_text())
