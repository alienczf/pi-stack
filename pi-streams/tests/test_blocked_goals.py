from __future__ import annotations

import json

import test_drive as cases
from tick_support import TickCase, reply, row


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
            blocked = reply('Blocked. The required toolchain is unavailable. Do not repeat this unit.')
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
