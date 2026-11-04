from __future__ import annotations

import json
from pathlib import Path
import sys

import test_failure_recovery as cases
from support import ROOT
from tick_support import TickCase

sys.path.insert(0, str(ROOT / 'pi-streams'))
from engine import StreamsError, artifacts, dcr, failure


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

    def test_rejected_permitted_analysis_records_one_blocker_without_repeating_it(self):
        self.fixture()
        self.listing[:] = [item for item in self.listing if item['id'] != 'returned-fork']
        path = Path(self.log_path('coi'))
        entries = [json.loads(line) for line in path.read_bytes().splitlines()]
        for entry in entries:
            if entry.get('id') == 'e5':
                entry['message']['content'] = failure.POLICY_ANALYSIS
            if entry.get('id') == 'e6':
                entry['message']['errorMessage'] = POLICY_ERRORS[0]
        path.write_bytes(b''.join((json.dumps(entry) + '\n').encode() for entry in entries))
        self.original['failureBoundary']['checkpoint']['sha256'] = self.digest('coi', 'e4')
        self.original['failureBoundary']['failure']['sha256'] = self.digest('coi', 'e6')
        self.append('coi', 'analysis-refused', 'registered-policy', 'pi-web.stream-failure', self.original['failureBoundary'])
        self.original['rotationSafety']['entryId'] = 'analysis-refused'
        data = self.state(self.stream)
        data.pop('failures')
        (self.stream / 'log/tick-state.json').write_text(json.dumps(data))
        self.stub.set_routes(self.routes)
        for _ in range(3):
            ticked = self.tick('2026-11-03T00:00:00Z')
            self.assertEqual(ticked.returncode, 0, ticked.stderr)
            self.assertEqual([item for item in self.stub.requests if item[0] == 'POST'], [])
        episode = self.state(self.stream)['failures']['coi']
        self.assertEqual((episode['kind'], episode['authority']), ('content-policy', None))
        self.assertIn('not proven clean', episode['detail'])
        self.assertEqual((self.stream / 'STATE.md').read_text().count('Content-policy safe blocker'), 1)

    def check_clean_analysis(self, disposition):
        self.fixture(model='gpt-6.1-sol')
        self.listing[:] = [item for item in self.listing if item['id'] != 'returned-fork']
        source = Path(self.log_path('coi'))
        entries = [json.loads(raw) for raw in source.read_bytes().splitlines()]
        for entry in entries:
            if entry.get('id') == 'e6':
                entry['message']['errorMessage'] = POLICY_ERRORS[0]
        source.write_bytes(b''.join((json.dumps(entry) + '\n').encode() for entry in entries))
        boundary = self.original['failureBoundary']
        boundary['checkpoint']['sha256'] = self.digest('coi', 'e4')
        boundary['failure'].update(kind='content-policy', sha256=self.digest('coi', 'e6'))
        self.append('coi', 'clean-policy-boundary', 'registered-policy', 'pi-web.stream-failure', boundary)
        self.original['rotationSafety']['entryId'] = 'clean-policy-boundary'
        self.original['cleanPolicyAnalysisSupport'] = 'clean-policy-analysis-v1'
        data = self.state(self.stream)
        data.pop('failures')
        data['drive'] = {'enabled': True, 'run_id': 'retained-drive'}
        (self.stream / 'log/tick-state.json').write_text(json.dumps(data))
        calls = []
        def analyze(body):
            calls.append(body)
            self.assertEqual(set(body), {'cwd', 'id', 'basis', 'expected', 'blockedGoalSha256'})
            self.assertEqual(body['basis'], 'clean-policy-analysis-v1')
            self.assertNotIn('assignment', {key: value for key, value in body.items() if key != 'expected'})
            if disposition == 'lost':
                return 503, {'error': 'Controlled unknown analysis outcome'}
            return 200, {'version': 1, 'id': body['id'], 'basis': body['basis'], 'originalSessionId': 'coi', 'cwd': str(self.cwd),
                         'failure': body['expected']['failure'], 'blockedGoalSha256': body['blockedGoalSha256'], 'provider': 'openai-codex', 'model': 'gpt-6.1-sol', 'thinking': 'xhigh',
                         'state': disposition, 'originalTaskBlocked': True, 'audit': {'sourceSha256': 'a' * 64, 'retainedSource': 'outside-model-input'}}
        self.routes.append(('POST', '/api/sessions/coi/failure-recovery/analysis', 200, analyze))
        self.stub.set_routes(self.routes)
        original, table = source.read_bytes(), (self.stream / 'threads.tsv').read_bytes()
        authority = (self.stream / 'STATE.md').read_bytes().partition(b'## Log')[0]
        posts = []
        for _ in range(3):
            ticked = self.tick('2026-11-03T00:00:00Z')
            self.assertEqual(ticked.returncode, 0, ticked.stderr)
            posts.extend(request[1] for request in self.stub.requests if request[0] == 'POST')
        episode = self.state(self.stream)['failures']['coi']
        self.assertEqual(len(calls), 1)
        self.assertEqual((episode['state'], episode['authority']), ('parked', None))
        self.assertEqual(episode['analysis']['state'], 'uncertain' if disposition == 'lost' else disposition)
        self.assertEqual(episode['analysis']['basis'], 'clean-policy-analysis-v1')
        self.assertEqual(source.read_bytes(), original)
        self.assertEqual((self.stream / 'threads.tsv').read_bytes(), table)
        self.assertEqual((self.stream / 'STATE.md').read_bytes().partition(b'## Log')[0], authority)
        self.assertEqual(self.state(self.stream)['drive']['run_id'], 'retained-drive')
        self.assertEqual((self.stream / 'STATE.md').read_text().count('Separate policy metadata analysis'), 1)
        self.assertTrue(failure.policy_blocks_goal(self.stream, artifacts.resolve_current_goal(artifacts.parse_state((self.stream / 'STATE.md').read_bytes()))))
        self.assertEqual(posts, ['/api/sessions/coi/failure-recovery/analysis'])

    def test_clean_metadata_analysis_is_not_original_task_recovery(self):
        self.check_clean_analysis('analyzed')

    def test_rejected_clean_analysis_is_not_retried_on_later_ticks(self):
        self.check_clean_analysis('rejected')

    def test_unknown_clean_analysis_is_durably_retained_without_retry(self):
        self.check_clean_analysis('lost')

    def test_historical_model_error_retains_safe_blocker_without_rejected_assignment_replay(self):
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
        self.assertEqual((episode['kind'], episode['state'], episode['authority']), ('content-policy', 'parked', None))
        context = episode['continuation']
        self.assertEqual(context['mode'], 'permitted-analysis-v1')
        self.assertEqual(context['policyFailure'], {'entryId': 'e6', 'sha256': self.digest('coi', 'e6')})
        self.assertEqual(context['assignment'], 'Explain the content-policy restriction and record a blocker. Do not perform the rejected task or any external effects.')
        self.assertNotIn('savedInput', context)
        self.assertNotIn('nativeFile', context)
        self.assertNotIn('handovers', context)
        op = dcr.Operation('safe-policy', 'safe-fork', str(self.cwd), {}, '', continuation=context)
        with self.assertRaisesRegex(StreamsError, 'clean model context'):
            dcr.continuation_text(op, self.stream)
        self.assertTrue(failure.policy_blocks_goal(self.stream, artifacts.resolve_current_goal(artifacts.parse_state((self.stream / 'STATE.md').read_bytes()))))
        self.assertEqual(self.state(self.stream)['drive']['run_id'], 'retained-drive-intent')
        self.assertTrue(self.state(self.stream)['drive']['enabled'])
        self.assertEqual((self.stream / 'threads.tsv').read_bytes(), before)
        self.assertEqual((self.stream / 'failures/coi.lastgood').read_bytes(), b'e4\n')
        self.assertEqual([item for item in self.stub.requests if item[0] == 'POST'], [])
        self.assertEqual((self.stream / 'STATE.md').read_text().count('Content-policy safe blocker'), 1)
