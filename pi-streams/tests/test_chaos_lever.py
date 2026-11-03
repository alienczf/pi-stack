from __future__ import annotations

import argparse
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


@unittest.skipUnless(os.environ.get('PI_STACK_NATIVE_TEST_ROOT') or os.environ.get('PI_STACK_CHAOS_SOURCE_TAR'), 'explicit disposable native fixture or frozen package archive required')
class ChaosNativeIntegrationTests(unittest.TestCase):
    def test_real_cli_registered_routes_persistence_retry_compaction_and_cleanup(self):
        logs = chaos.DEFAULT_LOGS / ('unittest-' + str(os.getpid()))
        node = os.environ.get('PI_STACK_CHAOS_NODE') or str(Path('/home/alphalab/.local/share/pi-node/current/bin/node').resolve())
        inputs = ['--native-root', os.environ['PI_STACK_NATIVE_TEST_ROOT']] if os.environ.get('PI_STACK_NATIVE_TEST_ROOT') else ['--source-tar', os.environ['PI_STACK_CHAOS_SOURCE_TAR']]
        result = subprocess.run([sys.executable, str(SCRIPT), *inputs, '--node', node, '--logs', str(logs), '--cases', 'overload,compaction'], capture_output=True, text=True, timeout=150)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        run = max(logs.glob('run-*'), key=lambda path: path.stat().st_mtime_ns)
        results = json.loads((run / 'results.json').read_text())
        self.assertEqual([item['result'] for item in results], ['PASS', 'PASS'])
        if inputs[0] == '--source-tar':
            self.assertTrue(json.loads((run / 'fixture-cleanup.json').read_text())['removed'])
        self.assertGreaterEqual(results[0]['details']['retryDelayMs'], 5000)
        self.assertGreater(results[1]['details']['before'], 150000)
        self.assertLess(results[1]['details']['after'], 150000)
        self.assertEqual(results[1]['details']['observation']['kind'], 'assistant-stop')
        for item in results:
            self.assertTrue(item['cleanup']['processStopped'])
            self.assertEqual(item['cleanup']['processReturncode'], 0)
            self.assertTrue(item['cleanup']['pathRemoved'])
            self.assertTrue(all(stream['closed'] for stream in item['cleanup']['streams']))
            self.assertTrue(all(session['state'] in ('archived', 'already-archived-or-retired') for session in item['cleanup']['sessions']))
            evidence = json.loads((Path(item['evidence']) / 'native-evidence.json').read_text())
            self.assertTrue(evidence['simulatedProviderTransport'])
            self.assertTrue(any(request['url'] == '/api/sessions' and request['method'] == 'POST' and request['status'] == 200 for request in evidence['requests']))
            self.assertTrue(any(session.get('entries') for session in evidence['evidence']))
            self.assertEqual({(call['provider'], call['model']) for call in evidence['calls']}, {('openai-codex', 'gpt-6.1-sol')})


if __name__ == '__main__':
    unittest.main()
