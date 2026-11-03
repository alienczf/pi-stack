"""Historical extension trees are rebuilt from hash-verified real package files."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(os.environ.get('PI_STACK_NATIVE_TEST_ROOT'), 'set PI_STACK_NATIVE_TEST_ROOT to the patched disposable package')
class NativeExtensionUpgradeTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('extension_overlay', ROOT / 'scripts/apply-native-overlay.py')
        self.overlay = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.overlay)
        self.fixture = Path(os.environ['PI_STACK_NATIVE_TEST_ROOT']).resolve().parent / 'extensions'
        self.assertIn('.harness-heal', self.fixture.parts)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    @staticmethod
    def digest(raw):
        return hashlib.sha256(raw).hexdigest()

    def historical(self, revision, extension):
        return json.loads(subprocess.check_output(['git', '-C', str(ROOT), 'show', f'{revision}:native/extensions/{extension}.json']))

    def pristine(self, extension):
        seed = self.historical('442a170', extension)
        target = self.root / extension
        target.mkdir(exist_ok=True)
        package = (self.fixture / extension / 'package.json').read_bytes()
        self.assertEqual(self.digest(package), seed['packages']['package.json']['sha256'])
        (target / 'package.json').write_bytes(package)
        for item in seed['files']:
            raw = (self.fixture / extension / item['path']).read_bytes()
            self.assertEqual(self.digest(raw), item['after'])
            text = raw.decode()
            for edit in reversed(item['edits']):
                self.assertEqual(text.count(edit['new']), 1)
                text = text.replace(edit['new'], edit['old'], 1)
            self.assertEqual(self.digest(text.encode()), item['before'])
            path = target / item['path']
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(text.encode())
        return target

    def historical_tree(self, revision, extension):
        target = self.pristine(extension)
        historical = self.historical(revision, extension)
        for item in historical['files']:
            path = target / item['path']
            text = path.read_bytes().decode()
            self.assertEqual(self.digest(text.encode()), item['before'])
            for edit in item['edits']:
                self.assertEqual(text.count(edit['old']), 1)
                text = text.replace(edit['old'], edit['new'], 1)
            self.assertEqual(self.digest(text.encode()), item['after'])
            path.write_bytes(text.encode())
        return target

    def snapshot(self, target):
        return {path.relative_to(target).as_posix(): path.read_bytes() for path in target.rglob('*') if path.is_file()}

    def assert_upgrade(self, target, manifest):
        before = self.snapshot(target)
        current = all(self.digest(before[item['path']]) == item['after'] for item in manifest['files'])
        self.assertEqual(self.overlay.apply(target, manifest, check=True), 'already-applied' if current else 'ready')
        self.assertEqual(self.snapshot(target), before)
        self.assertEqual(self.overlay.apply(target, manifest), 'already-applied' if current else 'applied')
        for item in manifest['files']:
            self.assertEqual((target / item['path']).read_bytes(), (self.fixture / target.name / item['path']).read_bytes())
            self.assertEqual(self.digest((target / item['path']).read_bytes()), item['after'])
        after = self.snapshot(target)
        self.assertEqual(self.overlay.apply(target, manifest, check=True), 'already-applied')
        self.assertEqual(self.overlay.apply(target, manifest), 'already-applied')
        self.assertEqual(self.snapshot(target), after)

    def test_all_extensions_from_real_pristine_and_known_historical_postimages(self):
        for path in sorted((ROOT / 'native/extensions').glob('*.json')):
            manifest = json.loads(path.read_text())
            extension = path.stem
            with self.subTest(extension=extension, revision='pristine'):
                self.assert_upgrade(self.pristine(extension), manifest)
            for revision in ('17e1bb8', 'c436142', '432f1e6'):
                with self.subTest(extension=extension, revision=revision):
                    self.assert_upgrade(self.historical_tree(revision, extension), manifest)

    def test_foreign_extension_bytes_refuse_before_any_mutation(self):
        for path in sorted((ROOT / 'native/extensions').glob('*.json')):
            with self.subTest(extension=path.stem):
                manifest = json.loads(path.read_text())
                target = self.historical_tree('17e1bb8', path.stem)
                changed = target / manifest['files'][-1]['path']
                changed.write_bytes(changed.read_bytes() + b'\nforeign changes\n')
                before = self.snapshot(target)
                for check in (True, False):
                    with self.assertRaisesRegex(ValueError, 'hash'):
                        self.overlay.apply(target, manifest, check=check)
                    self.assertEqual(self.snapshot(target), before)

    def test_foreign_mixture_of_known_subagent_postimages_is_not_an_upgrade(self):
        target = self.historical_tree('17e1bb8', 'pi-subagents')
        manifest = json.loads((ROOT / 'native/extensions/pi-subagents.json').read_text())
        watcher = 'src/runs/background/result-watcher.ts'
        (target / watcher).write_bytes((self.fixture / 'pi-subagents' / watcher).read_bytes())
        before = self.snapshot(target)
        for check in (True, False):
            with self.assertRaisesRegex(ValueError, 'mixed'):
                self.overlay.apply(target, manifest, check=check)
            self.assertEqual(self.snapshot(target), before)
