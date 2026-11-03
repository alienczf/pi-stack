from __future__ import annotations

import json
from pathlib import Path
import sys

import test_failure_recovery as cases
from support import ROOT
from tick_support import TickCase

sys.path.insert(0, str(ROOT / 'pi-streams'))
from engine import failure


POLICY_ERRORS = (
    'This content was flagged for possible cybersecurity risk',
    '503 content_policy_violation, please retry your request',
    '429 usage limit hint with content-policy refusal',
    'Request rejected by the content filter',
    'Safety policy refusal',
    'ResponsibleAIPolicyViolation',
)


class ContentPolicyGuardTests(TickCase):
    seed = cases.FailureRecoveryTests.seed
    digest = cases.FailureRecoveryTests.digest
    body = cases.FailureRecoveryTests.body
    fixture = cases.FailureRecoveryTests.fixture
    append = cases.FailureRecoveryTests.append
    fork_response = cases.FailureRecoveryTests.fork_response

    def test_policy_classification_precedes_transient_and_usage_hints(self):
        for message in POLICY_ERRORS:
            with self.subTest(message=message):
                classified = failure.classify('openai-codex', message, '2026-11-03T00:00:00Z')
                self.assertEqual((classified.kind, classified.code, classified.automatic_retry), ('content-policy', 'content_policy_blocked', False))

    def test_historical_model_error_becomes_durable_policy_blocker_without_same_content_recovery(self):
        self.fixture()
        self.listing[:] = [item for item in self.listing if item['id'] != 'returned-fork']
        source = Path(self.log_path('coi'))
        lines = source.read_bytes().splitlines(keepends=True)
        for index, raw in enumerate(lines):
            entry = json.loads(raw)
            if entry.get('id') == 'e6':
                entry['message']['errorMessage'] = POLICY_ERRORS[0]
                lines[index] = (json.dumps(entry) + '\n').encode()
        source.write_bytes(b''.join(lines))
        self.original['failureBoundary']['failure']['sha256'] = self.digest('coi', 'e6')
        self.original['failureBoundary']['failure']['kind'] = 'model-error'
        self.append('coi', 'policy-boundary', 'registered-policy', 'pi-web.stream-failure', self.original['failureBoundary'])
        self.original['rotationSafety']['entryId'] = 'policy-boundary'
        data = self.state(self.stream)
        data['failures']['coi']['failure_sha256'] = self.digest('coi', 'e6')
        data['failures']['coi']['kind'] = 'model-error'
        data['drive'] = {'enabled': True, 'run_id': 'retained-drive-intent'}
        (self.stream / 'log/tick-state.json').write_text(json.dumps(data))
        self.stub.set_routes(self.routes)
        self.stub.requests.clear()
        before = (self.stream / 'threads.tsv').read_bytes()
        for _ in range(3):
            resumed = self.run_streams('resume', 'etl', '--all-parked')
            self.assertEqual(resumed.returncode, 0, resumed.stderr)
            self.assertEqual(json.loads(resumed.stdout), [{'session': 'coi', 'state': 'policy-blocked', 'detail': 'Content-policy blocker. Do not retry or recover the same rejected content. Safe narrowed continuation is not implemented yet.'}])
            ticked = self.tick('2026-11-03T00:00:00Z')
            self.assertEqual(ticked.returncode, 0, ticked.stderr)
        advanced = self.run_streams('failure', 'advance', 'etl', '--session', 'coi', '--episode', self.episode['id'])
        self.assertNotEqual(advanced.returncode, 0)
        self.assertIn('same rejected content', advanced.stderr)
        episode = self.state(self.stream)['failures']['coi']
        self.assertEqual((episode['kind'], episode['state'], episode['authority']), ('content-policy', 'parked', None))
        self.assertEqual(self.state(self.stream)['drive']['run_id'], 'retained-drive-intent')
        self.assertTrue(self.state(self.stream)['drive']['enabled'])
        self.assertEqual((self.stream / 'threads.tsv').read_bytes(), before)
        self.assertEqual((self.stream / 'failures/coi.lastgood').read_bytes(), b'e4\n')
        self.assertEqual([item for item in self.stub.requests if item[0] == 'POST'], [])
        self.assertEqual((self.stream / 'STATE.md').read_text().count('Content-policy recovery blocked'), 1)
