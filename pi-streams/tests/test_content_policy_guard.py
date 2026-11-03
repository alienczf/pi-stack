from __future__ import annotations

import json
from pathlib import Path
import sys

import test_failure_recovery as cases
from support import ROOT
from tick_support import TickCase

sys.path.insert(0, str(ROOT / 'pi-streams'))
from engine import artifacts, dcr, failure


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

    def test_historical_model_error_gets_only_permitted_analysis_without_rejected_assignment(self):
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
        data['failures']['coi']['authority'] = None
        data['failures']['coi']['continuation'] = None
        data['drive'] = {'enabled': True, 'run_id': 'retained-drive-intent'}
        (self.stream / 'log/tick-state.json').write_text(json.dumps(data))
        self.stub.set_routes(self.routes)
        self.stub.requests.clear()
        before = (self.stream / 'threads.tsv').read_bytes()
        ticked = self.tick('2026-11-03T00:00:00Z')
        self.assertEqual(ticked.returncode, 0, ticked.stderr)
        episode = self.state(self.stream)['failures']['coi']
        self.assertEqual((episode['kind'], episode['state'], episode['authority']['kind']), ('content-policy', 'parked', 'engine-policy'))
        context = episode['continuation']
        self.assertEqual(context['mode'], 'permitted-analysis-v1')
        self.assertEqual(context['policyFailure'], {'entryId': 'e6', 'sha256': self.digest('coi', 'e6')})
        self.assertEqual(context['assignment'], 'Explain the content-policy restriction and record a blocker. Do not perform the rejected task or any external effects.')
        self.assertNotIn('savedInput', context)
        self.assertNotIn('nativeFile', context)
        self.assertNotIn('handovers', context)
        op = dcr.Operation('safe-policy', 'safe-fork', str(self.cwd), {}, '', continuation=context)
        text = dcr.continuation_text(op, self.stream)
        self.assertNotIn('Implement only the assigned fixture unit.', text)
        self.assertNotIn('<original-assignment>', text)
        self.assertIn('Do not reread or reconstruct rejected input', text)
        self.assertTrue(failure.policy_blocks_goal(self.stream, artifacts.resolve_current_goal(artifacts.parse_state((self.stream / 'STATE.md').read_bytes()))))
        self.assertEqual(self.state(self.stream)['drive']['run_id'], 'retained-drive-intent')
        self.assertTrue(self.state(self.stream)['drive']['enabled'])
        self.assertEqual((self.stream / 'threads.tsv').read_bytes(), before)
        self.assertEqual((self.stream / 'failures/coi.lastgood').read_bytes(), b'e4\n')
        self.assertEqual([item for item in self.stub.requests if item[0] == 'POST'], [])
        self.assertEqual((self.stream / 'STATE.md').read_text().count('Content-policy narrowed continuation'), 1)
