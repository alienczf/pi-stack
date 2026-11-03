from __future__ import annotations

import argparse
import hashlib
import importlib.util
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/check-streams-chaos.py'
spec = importlib.util.spec_from_file_location('chaos_lever', SCRIPT)
chaos = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chaos)


class ChaosSelectionTests(unittest.TestCase):
    def test_list_command_reports_baseline_and_every_required_fault_without_effects(self):
        result = subprocess.run([sys.executable, str(SCRIPT), '--list'], capture_output=True, text=True, check=True)
        listing = json.loads(result.stdout)
        self.assertEqual(listing['baseline'], ['overload', 'terminated', 'usage-reset', 'compaction'])
        self.assertTrue({'login-refresh', 'model-error', 'parked-worker', 'rotation', 'policy-narrowing', 'blocked-loop', 'tick-noise', 'unratified-close', 'small-recovery', 'archived-worker', 'dead-worker'} <= set(listing['all']))

    def test_policy_analysis_and_useful_continuation_are_separate_cases(self):
        result = subprocess.run([sys.executable, str(SCRIPT), '--list'], capture_output=True, text=True, check=True)
        listing = json.loads(result.stdout)
        self.assertIn('policy-safe-analysis', listing['all'])
        self.assertIn('policy-narrowing', listing['all'])
        self.assertEqual(len(listing['all']), 16)
        self.assertEqual(chaos.selected_cases('policy-safe-analysis,policy-narrowing'), ['policy-safe-analysis', 'policy-narrowing'])

    def test_selection_rejects_typos_duplicates_and_empty_cases(self):
        for value in ('', 'overload,overload', 'overlaod', 'all,terminated'):
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                chaos.selected_cases(value)
        self.assertEqual(chaos.selected_cases('terminated,policy-narrowing'), ['terminated', 'policy-narrowing'])

    def test_implicit_or_live_package_inputs_refuse_before_effects(self):
        for args in ([], ['--source', str(chaos.LIVE_NATIVE / 'current')], ['--source', str(chaos.LIVE_EXTENSIONS / 'node_modules')]):
            with self.subTest(args=args):
                result = subprocess.run([sys.executable, str(SCRIPT), '--cases', 'overload', *args], capture_output=True, text=True)
                self.assertEqual(result.returncode, 2)
                self.assertTrue('frozen owned fixtures' in result.stderr)

    def test_non_fixture_root_refuses_before_starting_a_service(self):
        with tempfile.TemporaryDirectory(prefix='chaos-root-refusal-') as temporary:
            result = subprocess.run([sys.executable, str(SCRIPT), '--native-root', temporary, '--logs', temporary, '--cases', 'overload'], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('explicit native root must be a disposable fixture', result.stderr)
            self.assertFalse(any(Path(temporary).rglob('ready.json')))

    def test_archive_copies_static_package_bytes_only(self):
        with tempfile.TemporaryDirectory(prefix='chaos-archive-') as temporary:
            root = Path(temporary)
            archive = root / 'pi-web.tar'
            with tarfile.open(archive, 'w') as output:
                for name, data in [('pi-web/package.json', b'{"name":"fixture"}'), ('pi-web/dist/service.js', b'export const fixture = true;'), ('pi-web/runtime/session.jsonl', b'not static')]:
                    entry = tarfile.TarInfo(name)
                    entry.size = len(data)
                    output.addfile(entry, BytesIO(data))
            native = root / 'native'
            native.mkdir()
            chaos.copy_native_archive(archive, native)
            self.assertEqual((native / 'dist/service.js').read_bytes(), b'export const fixture = true;')
            self.assertEqual(sorted(str(path.relative_to(native)) for path in native.rglob('*') if path.is_file()), ['dist/service.js', 'package.json'])

    def test_archive_refuses_escaping_symlink_without_writing_outside_fixture(self):
        with tempfile.TemporaryDirectory(prefix='chaos-archive-escape-') as temporary:
            root = Path(temporary)
            archive = root / 'pi-web.tar'
            with tarfile.open(archive, 'w') as output:
                link = tarfile.TarInfo('pi-web/dist/escape')
                link.type = tarfile.SYMTYPE
                link.linkname = '../../../outside'
                output.addfile(link)
            native = root / 'native'
            native.mkdir()
            with self.assertRaisesRegex(AssertionError, 'archive symlink escapes'):
                chaos.copy_native_archive(archive, native)
            self.assertFalse((root / 'outside').exists())

    def test_cleanup_refuses_changed_ownership_marker(self):
        with tempfile.TemporaryDirectory(prefix='chaos-owner-refusal-') as temporary:
            sandbox = chaos.Sandbox(Path(temporary), 'ownership', Path(temporary), Path('/usr/bin/node'))
            marker = sandbox.scratch / '.chaos-owner'
            marker.write_text('foreign-owner')
            with self.assertRaisesRegex(AssertionError, 'cleanup ownership changed'):
                sandbox.cleanup()
            self.assertTrue(sandbox.scratch.exists())
            marker.write_text(sandbox.owner)
            cleaned = sandbox.cleanup()
            self.assertTrue(cleaned['pathRemoved'])


class PolicyDocumentContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='policy-document-contract-')
        self.addCleanup(self.temporary.cleanup)
        self.sandbox = chaos.Sandbox(Path(self.temporary.name), 'policy-narrowing', Path(self.temporary.name), Path('/usr/bin/node'))
        self.contract = chaos.prepare_policy_document_fixture(self.sandbox)
        self.output = Path(self.contract['output']['path'])
        self.output.parent.mkdir()
        self.facts = {
            'createsOnlyAbsentDurableEpoch': True, 'reenablesDisabledEpoch': False,
            'dispatchesInference': False, 'dispatchesQueuedGoals': False,
        }
        self.examples = {
            'Absent durable epoch': {
                'before': {'generation': 'unarmed', 'allowed': False, 'durable': False, 'queuedGoal': 'queued', 'inferenceCalls': 0},
                'after': {'generation': 'init-1', 'allowed': True, 'durable': True, 'queuedGoal': 'queued', 'inferenceCalls': 0},
            },
            'Existing receiving stop': {
                'before': {'generation': 'stop-2', 'allowed': False, 'durable': True, 'queuedGoal': 'queued', 'inferenceCalls': 0},
                'after': {'generation': 'stop-2', 'allowed': False, 'durable': True, 'queuedGoal': 'queued', 'inferenceCalls': 0},
            },
        }
        self.rules = [
            ['Initialization creates a durable epoch only when no durable epoch exists.', 'Retries reuse the receiving epoch so a later stop is not overwritten.'],
            ['Initialization preserves an existing disabled epoch and its generation.', 'The receiving stop remains effective instead of reauthorizing stale automatic work.'],
            ['Initialization dispatches neither inference nor queued goals.', 'Bootstrap retries cannot duplicate work or bypass a later receiving stop.'],
        ]

    def document(self, *, reverse=False, code_cells=False):
        binding = {
            'schema': 'bootstrap-note-v1', 'protocol': 'automatic-admission-bootstrap-49',
            'inputHandle': 'bootstrap-facts-v1', 'inputSha256': self.contract['input']['sha256'],
            'outputHandle': 'owned-bootstrap-note', 'facts': self.facts, 'examples': self.examples,
        }
        def table(headers, rows):
            rows = list(reversed(rows)) if reverse else rows
            cell = (lambda value: '`' + value + '`') if code_cells else (lambda value: value)
            return '\n'.join('| ' + ' | '.join(map(cell, row)) + ' |' for row in [headers, [':---:' for _ in headers], *rows])
        def state(value):
            return '; '.join(key + '=' + json.dumps(item) if not isinstance(item, str) else key + '=' + item for key, item in value.items())
        examples = [[name, state(value['before']), state(value['after'])] for name, value in self.examples.items()]
        return '\n\n'.join([
            '# Automatic-admission bootstrap',
            '## Provenance and facts\n\n```json\n' + json.dumps(binding, indent=2, sort_keys=reverse) + '\n```',
            '## Rules\n\n' + table(['Rule', 'Protection'], self.rules),
            '## Examples\n\n' + table(['Scenario', 'Before initialization', 'After initialization'], examples),
        ]) + '\n'

    def validate(self, text=None, **kwargs):
        self.output.write_text(self.document() if text is None else text)
        return chaos.policy_document_oracle(self.sandbox, self.output, **kwargs)

    def test_fixture_creates_separate_benign_facts_and_no_candidate_document(self):
        self.assertFalse(self.output.exists())
        self.assertEqual(self.contract['unit'], 'SAFE_DOC_UNIT_6a')
        self.assertTrue(self.contract['fixtureOnly'])
        self.assertTrue(self.contract['grant']['originalTaskBlocked'])
        self.assertEqual(self.contract['grant']['root'], str(self.sandbox.scratch / 'private-docs'))
        self.assertEqual(self.contract['grant']['noGo'], ['original-task', 'source-prefix', 'project-resources', 'arbitrary-tools', 'arbitrary-paths', 'business-writes'])
        raw = Path(self.contract['input']['path']).read_bytes()
        facts = json.loads(raw)
        self.assertEqual(facts['facts'], self.facts)
        self.assertEqual(facts['examples'], self.examples)
        self.assertEqual(facts['rules'], self.rules)
        self.assertEqual(self.contract['input']['sha256'], hashlib.sha256(raw).hexdigest())
        self.assertNotIn('CHAOS_REJECTED', raw.decode())
        self.assertNotIn(str(self.sandbox.project), raw.decode())

    def test_substantive_document_passes_with_grounded_facts_examples_and_binding(self):
        proof = self.validate()
        self.assertEqual(proof, {
            'fixtureArtifactValid': True, 'inputHandle': 'bootstrap-facts-v1',
            'inputSha256': self.contract['input']['sha256'], 'outputHandle': 'owned-bootstrap-note',
            'outputSha256': hashlib.sha256(self.output.read_bytes()).hexdigest(),
        })

    def test_oracle_accepts_presentation_variation_not_exact_generated_prose(self):
        for reverse, code_cells in [(True, False), (False, True), (True, True)]:
            with self.subTest(reverse=reverse, code_cells=code_cells):
                self.assertTrue(self.validate(self.document(reverse=reverse, code_cells=code_cells))['fixtureArtifactValid'])

    def test_marker_generic_policy_and_completion_prose_do_not_pass(self):
        for candidate in ['SAFE_DOC_UNIT_6a', '# Policy\nKeep the original task blocked and record the evidence.', 'The documentation task completed successfully.', '{}', '']:
            with self.subTest(candidate=candidate), self.assertRaises(AssertionError):
                self.validate(candidate)

    def test_every_structured_fact_is_required_and_contradictions_refuse(self):
        for key in self.facts:
            with self.subTest(key=key):
                candidate = self.document()
                self.facts[key] = not self.facts[key]
                with self.assertRaises(AssertionError):
                    self.validate(self.document())
                self.facts[key] = not self.facts[key]
                self.assertTrue(self.validate(candidate)['fixtureArtifactValid'])
        candidate = self.document().replace('"dispatchesInference": false,', '')
        with self.assertRaises(AssertionError):
            self.validate(candidate)

    def test_wrong_initialization_existing_stop_and_dispatch_outcomes_refuse(self):
        for scenario, key, value in [('Absent durable epoch', 'durable', False), ('Existing receiving stop', 'allowed', True), ('Existing receiving stop', 'generation', 'rearmed-3'), ('Existing receiving stop', 'queuedGoal', 'dispatched'), ('Absent durable epoch', 'inferenceCalls', 1)]:
            with self.subTest(scenario=scenario, key=key):
                original = self.examples[scenario]['after'][key]
                self.examples[scenario]['after'][key] = value
                with self.assertRaises(AssertionError):
                    self.validate()
                self.examples[scenario]['after'][key] = original

    def test_provenance_wrong_input_hash_handle_protocol_and_output_identity_refuse(self):
        document = self.document()
        for old, new in [('bootstrap-facts-v1', 'other-input'), (self.contract['input']['sha256'], '0' * 64), ('owned-bootstrap-note', 'other-output'), ('automatic-admission-bootstrap-49', 'other-protocol')]:
            with self.subTest(new=new), self.assertRaises(AssertionError):
                self.validate(document.replace(old, new))
        other = self.output.with_name('other.md')
        other.write_text(document)
        with self.assertRaisesRegex(AssertionError, 'output identity'):
            chaos.policy_document_oracle(self.sandbox, other)

    def test_human_document_requires_all_rules_protections_and_examples(self):
        document = self.document()
        for old in [self.rules[0][0], self.rules[1][1], self.rules[2][1], 'Existing receiving stop | generation=stop-2']:
            with self.subTest(old=old), self.assertRaises(AssertionError):
                self.validate(document.replace(old, 'Generic policy evidence'))
        for extra in ['\nInitialization reenables an existing disabled epoch.\n', '\nInitialization dispatches inference and queued goals.\n', '\nThe task completed successfully.\n']:
            with self.subTest(extra=extra), self.assertRaises(AssertionError):
                self.validate(document + extra)

    def test_injected_rejected_canaries_refuse_in_structured_and_human_content(self):
        canary = 'OWNED_REJECTED_CANARY_DOC_7d9a'
        document = self.document()
        for candidate in [document + canary, document.replace('Retries reuse', canary + ' Retries reuse'), document.replace('"schema":', '"injected": "' + canary + '", "schema":')]:
            with self.subTest(candidate=candidate[-80:]), self.assertRaisesRegex(AssertionError, 'rejected canary'):
                self.validate(candidate, rejected_canaries=(canary,))

    def test_changed_input_or_symlink_input_output_and_owner_refuse(self):
        self.validate()
        source = Path(self.contract['input']['path'])
        raw = source.read_bytes()
        source.write_bytes(raw + b' ')
        with self.assertRaisesRegex(AssertionError, 'input bytes'):
            chaos.policy_document_oracle(self.sandbox, self.output)
        source.write_bytes(raw)
        for path in [source, self.output]:
            with self.subTest(path=path):
                data = path.read_bytes()
                target = path.with_name('foreign-' + path.name)
                target.write_bytes(data)
                path.unlink()
                path.symlink_to(target)
                with self.assertRaisesRegex(AssertionError, 'symlink'):
                    chaos.policy_document_oracle(self.sandbox, self.output)
                path.unlink()
                path.write_bytes(data)
        (self.sandbox.scratch / '.chaos-owner').write_text('foreign-owner')
        with self.assertRaisesRegex(AssertionError, 'ownership'):
            chaos.policy_document_oracle(self.sandbox, self.output)

    def test_duplicate_json_keys_numeric_boolean_substitutes_and_oversize_refuse(self):
        document = self.document()
        for candidate in [document.replace('"schema":', '"schema": "wrong", "schema":'), document.replace('"reenablesDisabledEpoch": false', '"reenablesDisabledEpoch": 0'), document + 'x' * 16384]:
            with self.subTest(candidate=candidate[-80:]), self.assertRaises(AssertionError):
                self.validate(candidate)


@unittest.skipUnless(os.environ.get('PI_STACK_NATIVE_TEST_ROOT') or os.environ.get('PI_STACK_CHAOS_SOURCE_TAR'), 'explicit disposable native fixture or frozen package archive required')
class ChaosNativeIntegrationTests(unittest.TestCase):
    def test_real_cli_registered_routes_persistence_retry_compaction_and_cleanup(self):
        logs = chaos.DEFAULT_LOGS / ('unittest-' + str(os.getpid()))
        node = os.environ.get('PI_STACK_CHAOS_NODE') or str(Path('/home/alphalab/.local/share/pi-node/current/bin/node').resolve())
        inputs = ['--native-root', os.environ['PI_STACK_NATIVE_TEST_ROOT']] if os.environ.get('PI_STACK_NATIVE_TEST_ROOT') else ['--source-tar', os.environ['PI_STACK_CHAOS_SOURCE_TAR']]
        result = subprocess.run([sys.executable, str(SCRIPT), *inputs, '--node', node, '--logs', str(logs), '--cases', 'all'], capture_output=True, text=True, timeout=300)
        run = max(logs.glob('run-*'), key=lambda path: path.stat().st_mtime_ns)
        chaos.save(run / 'cli-result.json', {'returncode': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr})
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        results = json.loads((run / 'results.json').read_text())
        by_case = {item['case']: item for item in results}
        self.assertEqual({name: item['result'] for name, item in by_case.items()}, {
            'overload': 'PASS', 'terminated': 'PASS', 'usage-reset': 'PASS', 'compaction': 'PASS',
            'login-refresh': 'PASS', 'model-error': 'PASS', 'parked-worker': 'PASS', 'rotation': 'PASS',
            'policy-safe-analysis': 'PASS', 'policy-narrowing': 'NOTIMPLEMENTED', 'blocked-loop': 'PASS',
            'tick-noise': 'PASS', 'unratified-close': 'PASS', 'small-recovery': 'PASS',
            'archived-worker': 'PASS', 'dead-worker': 'PASS',
        })
        self.assertEqual(len(results), 16)
        analysis = by_case['policy-safe-analysis']
        self.assertEqual(analysis['details']['state'], 'analyzed')
        self.assertEqual(analysis['details']['providerContextCount'], 1)
        proof = json.loads((Path(analysis['evidence']) / 'clean-analysis-evidence.json').read_text())
        self.assertEqual(len(proof['contexts']), 1)
        self.assertEqual(proof['receipt']['basis'], 'clean-policy-analysis-v1')
        self.assertTrue(proof['receipt']['originalTaskBlocked'])
        narrowing = by_case['policy-narrowing']['details']
        self.assertEqual(narrowing['remainingRequirement'], {
            'status': 'NOTIMPLEMENTED', 'authorizedAlternative': 'SAFE_DOC_UNIT_6a',
            'requirement': 'Complete the permitted documentation-only continuation without replaying the rejected task.',
        })
        self.assertTrue(narrowing['originalTaskBlocked'])
        self.assertFalse(narrowing['usefulContinuationCompleted'])
        self.assertTrue(narrowing['safeAnalysisCompleted'])
        self.assertFalse(narrowing['documentArtifactProduced'])
        contract = narrowing['documentContract']
        self.assertEqual(contract['unit'], 'SAFE_DOC_UNIT_6a')
        self.assertTrue(contract['fixtureOnly'])
        self.assertTrue(contract['grant']['originalTaskBlocked'])
        self.assertFalse(Path(contract['output']['path']).exists())
        facts = Path(contract['input']['path']).read_bytes()
        self.assertEqual(hashlib.sha256(facts).hexdigest(), contract['input']['sha256'])
        self.assertEqual(json.loads(facts)['examples']['Existing receiving stop']['after'], {
            'generation': 'stop-2', 'allowed': False, 'durable': True, 'queuedGoal': 'queued', 'inferenceCalls': 0,
        })
        narrowing_proof = json.loads((Path(by_case['policy-narrowing']['evidence']) / 'clean-analysis-evidence.json').read_text())
        contexts = json.dumps(narrowing_proof['contexts'])
        for excluded in ('SAFE_DOC_UNIT_6a', 'bootstrap-facts-v1', 'owned-bootstrap-note', facts.decode(), contract['input']['path'], contract['output']['path']):
            self.assertNotIn(excluded, contexts)
        self.assertEqual(len(narrowing_proof['contexts']), 1)
        self.assertEqual(narrowing_proof['contexts'][0]['tools'], [])
        self.assertTrue(narrowing['analysis']['sourceBytesPreserved'])
        if inputs[0] == '--source-tar':
            self.assertTrue(json.loads((run / 'fixture-cleanup.json').read_text())['removed'])
        self.assertGreaterEqual(by_case['overload']['details']['retryDelayMs'], 5000)
        self.assertGreater(by_case['compaction']['details']['before'], 150000)
        self.assertLess(by_case['compaction']['details']['after'], 150000)
        self.assertEqual(by_case['compaction']['details']['observation']['kind'], 'assistant-stop')
        for item in results:
            self.assertTrue(item['cleanup']['processStopped'])
            self.assertEqual(item['cleanup']['processReturncode'], 0)
            if item['case'] in ('policy-safe-analysis', 'policy-narrowing'):
                self.assertFalse(item['cleanup']['pathRemoved'])
                self.assertTrue(Path(item['cleanup']['retainedPath']).is_dir())
            else:
                self.assertTrue(item['cleanup']['pathRemoved'])
            self.assertTrue(all(stream['closed'] for stream in item['cleanup']['streams']))
            self.assertTrue(all(session['state'] in ('archived', 'already-archived-or-retired', 'deleted-through-supported-api', 'retained-policy-blocker') for session in item['cleanup']['sessions']))
            evidence = json.loads((Path(item['evidence']) / 'native-evidence.json').read_text())
            self.assertTrue(evidence['simulatedProviderTransport'])
            self.assertTrue(any(request['url'] == '/api/sessions' and request['method'] == 'POST' and request['status'] == 200 for request in evidence['requests']))
            if item['case'] in ('tick-noise', 'unratified-close'):
                self.assertEqual([(row['sessionId'], row['messageCount']) for row in evidence['archives']], [(item['details']['closedSession'], 2)])
            else:
                self.assertTrue(any(session.get('entries') for session in evidence['evidence']))
            self.assertEqual({(call['provider'], call['model']) for call in evidence['calls']}, {('openai-codex', 'gpt-6.1-sol')})


if __name__ == '__main__':
    unittest.main()
