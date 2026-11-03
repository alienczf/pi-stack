from __future__ import annotations

import json
import sys
from support import ROOT

sys.path.insert(0, str(ROOT / "pi-streams"))

import test_failure_recovery as cases
from tick_support import TickCase


class EnginePolicyRecoveryTests(TickCase):
    seed = cases.FailureRecoveryTests.seed
    digest = cases.FailureRecoveryTests.digest
    body = cases.FailureRecoveryTests.body
    fixture = cases.FailureRecoveryTests.fixture
    append = cases.FailureRecoveryTests.append
    fork_response = cases.FailureRecoveryTests.fork_response
    advance = cases.FailureRecoveryTests.advance

    def test_enrolled_coordinator_recovers_without_verifier_or_fresh_handover(self):
        self.fixture(policy=True)
        self.assertFalse((self.stream / 'handover/coordinator/coi.md').exists())
        result = self.advance()
        self.assertEqual(result.returncode, 0, result.stderr)
        operation = self.state(self.stream)['failure_recoveries']['coi']
        self.assertEqual(operation['phase'], 'bound')
        self.assertEqual(operation['request']['authority'], {'kind': 'engine-policy', 'policyId': 'enrolled-prefix-v1', 'enrollmentId': 'fresh-lane'})
        self.assertFalse(any(item[1].endswith('/ratify') for item in self.stub.requests))
        self.assertEqual((self.stream / 'failures/coi.lastgood').read_text(), 'e4\n')

    def test_worker_assignment_is_retained_without_promoting_it_to_coordinator(self):
        self.fixture('implementation', policy=True)
        result = self.advance()
        self.assertEqual(result.returncode, 0, result.stderr)
        episode = self.state(self.stream)['failures']['coi']
        self.assertEqual(episode['continuation']['role'], 'implementation')
        self.assertEqual(episode['continuation']['assignment'], 'Implement only the assigned fixture unit.')
        self.assertIn('returned-fork\timplementation', self.rows(self.stream))
        self.assertEqual((self.cwd / '.stream').read_text(), str(self.stream))

    def test_tick_automatically_advances_policy_without_notice_or_generic_prompt(self):
        self.fixture(policy=True)
        result = self.tick('2026-10-06T12:05:00Z')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.state(self.stream)['failure_recoveries']['coi']['phase'], 'bound')
        self.assertEqual(sum(item[1].endswith('/fork') for item in self.stub.requests), 1)
        self.assertFalse(any(item[1].endswith('/prompt') or item[1].endswith('/ratify') for item in self.stub.requests))

    def test_historical_parking_uses_registry_role_and_original_input_without_enrollment(self):
        self.fixture(policy=True)
        from engine import failure
        from pathlib import Path
        boundary = self.original['failureBoundary']
        boundary.pop('enrollment')
        path = Path(self.log_path('coi'))
        entries = [json.loads(line) for line in path.read_text().splitlines()]
        for entry in entries:
            if entry.get('customType') == 'pi-web.stream-failure':
                entry['data'].pop('enrollment', None)
        path.write_text(''.join(json.dumps(entry) + '\n' for entry in entries))
        authority, continuation = failure.enrolled_authority(self.stream, 'coi', str(self.cwd), path, 'registered-policy', boundary, self.original, 'native-parked-coi')
        self.assertEqual(authority, {'kind': 'engine-policy', 'policyId': 'enrolled-prefix-v1', 'enrollmentId': 'coi'})
        self.assertEqual(continuation['role'], 'coordinator')
        opening = next(entry['message']['content'] for entry in entries if entry.get('message', {}).get('role') == 'user')
        self.assertEqual(continuation['assignment'], json.dumps(opening, ensure_ascii=False))
        boundary['parking']['generation'] = 'old-generation'
        self.assertIsNone(failure.enrolled_authority(self.stream, 'coi', str(self.cwd), path, 'registered-policy', boundary, self.original, 'newer-stop'))

    def test_ambiguous_saved_authority_refuses_before_any_effect(self):
        self.fixture(policy=True)
        path = self.stream / 'log/tick-state.json'
        data = self.state(self.stream)
        data['failures']['coi']['authority'] = {'kind': 'arbitrary-label'}
        path.write_text(json.dumps(data))
        result = self.advance()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('authority', result.stderr)
        self.assertFalse(any(item[1].endswith('/fork') for item in self.stub.requests))

    def test_rotate_uses_owned_lastgood_without_a_live_checkpoint(self):
        self.fixture()
        self.assertNotIn('coordinator_checkpoint', self.state(self.stream))
        self.assertEqual((self.stream / 'failures/coi.lastgood').read_text(), 'e4\n')
        result = self.run_streams('rotate', 'etl')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.endswith('returned-fork\n'))
        self.assertEqual(self.state(self.stream)['failure_recoveries']['coi']['phase'], 'bound')
        self.assertFalse(any(item[1].endswith('/archive') or item[1].endswith('/abort') for item in self.stub.requests))

    def test_newer_stop_never_uses_policy_to_rearm_or_fork(self):
        self.fixture(policy=True)
        self.stub.automatic_admissions['coi']['generation'] = 'human-stop'
        result = self.advance()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(item[1].endswith('/fork') for item in self.stub.requests))
        self.assertEqual((self.stream / 'failures/coi.lastgood').read_text(), 'e4\n')
