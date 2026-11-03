from __future__ import annotations

import json
import test_failure_recovery as cases
from tick_support import TickCase


class MassResumeTests(TickCase):
    seed = cases.FailureRecoveryTests.seed
    digest = cases.FailureRecoveryTests.digest
    body = cases.FailureRecoveryTests.body
    fixture = cases.FailureRecoveryTests.fixture
    append = cases.FailureRecoveryTests.append
    fork_response = cases.FailureRecoveryTests.fork_response
    advance = cases.FailureRecoveryTests.advance

    def test_refreshed_native_auth_resumes_without_reading_tokens_or_changing_models(self):
        self.fixture()
        self.original['recoveryReadinessSupport'] = 'same-provider-v1'
        ready = {'sessionId': 'coi', 'cwd': str(self.cwd), 'provider': 'openai-codex', 'model': 'gpt-6-astra', 'authenticated': False, 'resourceReady': True}
        self.routes.append(('GET', '/api/sessions/coi/failure-recovery/readiness', 200, ready))
        self.stub.set_routes(self.routes)
        first = self.run_streams('resume', 'etl', '--all-parked')
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(json.loads(first.stdout)[0]['state'], 'pending')
        self.assertFalse(any(item[1].endswith('/fork') for item in self.stub.requests))
        ready['authenticated'] = True
        second = self.run_streams('resume', 'etl', '--all-parked')
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(json.loads(second.stdout)[0]['phase'], 'bound')
        self.assertEqual(sum(item[1].endswith('/fork') for item in self.stub.requests), 1)
        self.assertFalse(any(item[1].endswith('/model') for item in self.stub.requests))

    def test_mass_resume_preserves_explicit_local_off(self):
        self.fixture()
        data = self.state(self.stream)
        data['drive'] = {'enabled': False}
        (self.stream / 'log/tick-state.json').write_text(json.dumps(data))
        self.stub.requests.clear()
        result = self.run_streams('resume', '--all-parked')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)[0]['state'], 'stopped')
        self.assertFalse(self.stub.requests)
