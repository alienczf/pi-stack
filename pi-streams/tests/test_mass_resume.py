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

    def test_ordinary_tick_preserves_explicit_local_off(self):
        self.fixture()
        self.listing[:] = [item for item in self.listing if item['id'] != 'returned-fork']
        data = self.state(self.stream)
        data['drive'] = {'enabled': False}
        (self.stream / 'log/tick-state.json').write_text(json.dumps(data))
        self.stub.requests.clear()
        result = self.tick('2026-10-06T12:05:00Z')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.state(self.stream)['drive']['enabled'])
        self.assertFalse(any(item[0] == 'POST' for item in self.stub.requests))

    def test_explicit_resume_rebinds_unowned_historical_parking_without_enabling_original(self):
        import hashlib
        self.fixture()
        data = self.state(self.stream)
        data['drive'] = {'enabled': False}
        (self.stream / 'log/tick-state.json').write_text(json.dumps(data))
        self.original['failureBoundary']['parking'] = {'generation': 'legacy-off', 'owned': False}
        self.append('coi', 'historical-off', 'registered-policy', 'pi-web.stream-failure', self.original['failureBoundary'])
        self.original['rotationSafety']['entryId'] = 'historical-off'
        self.stub.automatic_admissions['coi']['generation'] = 'legacy-off'
        def resume(body):
            self.assertEqual(body['expected'], {**self.original['failureBoundary'], 'generation': 'legacy-off'})
            self.original['failureBoundary']['parking'] = {'generation': 'explicit-resume-generation', 'owned': True}
            self.append('coi', 'explicit-resume', 'historical-off', 'pi-web.stream-failure', self.original['failureBoundary'])
            self.original['rotationSafety']['entryId'] = 'explicit-resume'
            self.stub.automatic_admissions['coi']['generation'] = 'explicit-resume-generation'
            self.request['expected'] = {**self.original['failureBoundary'], 'generation': 'explicit-resume-generation'}
            self.request['continuation']['stateSha256'] = hashlib.sha256((self.stream / 'STATE.md').read_bytes()).hexdigest()
            self.result['intentSha256'] = hashlib.sha256(json.dumps(self.request, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
            return 200, self.original['failureBoundary']
        self.routes.append(('POST', '/api/sessions/coi/failure-recovery/resume', 200, resume))
        self.stub.set_routes(self.routes)
        result = self.run_streams('resume', 'etl', '--all-parked')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.state(self.stream)['failure_recoveries']['coi']['phase'], 'bound')
        self.assertTrue(self.state(self.stream)['drive']['enabled'])
        self.assertFalse(any(item[1] == '/api/sessions/coi/automatic-admission' for item in self.stub.requests))

    def test_explicit_resume_records_drive_intent_without_rearming_the_failed_original(self):
        self.fixture()
        data = self.state(self.stream)
        data['drive'] = {'enabled': False}
        (self.stream / 'log/tick-state.json').write_text(json.dumps(data))
        self.stub.requests.clear()
        result = self.run_streams('resume', 'etl', '--all-parked')
        self.assertEqual(result.returncode, 0, result.stderr)
        drive = self.state(self.stream)['drive']
        self.assertTrue(drive['enabled'])
        self.assertEqual(drive['remote_state'], 'on-unconfirmed')
        self.assertEqual(drive['resume_original'], 'coi')
        self.assertEqual(self.state(self.stream)['failure_recoveries']['coi']['fork'], 'returned-fork')
        self.assertFalse(any(item[1].endswith('/automatic-admission') and item[3].get('allowed') is True for item in self.stub.requests))
