"""Delivery checks use disposable package trees, never the installed daemon."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class NativeOverlayTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("native_overlay", ROOT / "scripts/apply-native-overlay.py")
        self.overlay = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.overlay)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "package.json").write_text('{"name":"fixture","version":"1"}')
        self.manifest = {"id": "fixture-v1", "packages": {"package.json": {"name": "fixture", "version": "1"}}, "files": []}
        for name in ("a.js", "b.js"):
            (self.root / name).write_text("export const value = 1;\n")
            self.manifest["files"].append({"path": name, "before": self.digest("export const value = 1;\n"), "after": self.digest("export const value = 2;\n"), "edits": [{"old": "value = 1", "new": "value = 2"}]})

    @staticmethod
    def digest(text):
        return hashlib.sha256(text.encode()).hexdigest()

    def test_apply_and_exact_repeat(self):
        self.assertEqual(self.overlay.apply(self.root, self.manifest), "applied")
        self.assertEqual((self.root / "a.js").read_text(), "export const value = 2;\n")
        self.assertEqual(self.overlay.apply(self.root, self.manifest), "already-applied")

    def test_preflight_every_file_before_mutation(self):
        (self.root / "b.js").write_text("unexpected bytes")
        with self.assertRaisesRegex(ValueError, "hash"):
            self.overlay.apply(self.root, self.manifest)
        self.assertEqual((self.root / "a.js").read_text(), "export const value = 1;\n")

    def test_unknown_mixed_tree_refused_but_interrupted_owned_apply_reconciles(self):
        (self.root / "a.js").write_text("export const value = 2;\n")
        with self.assertRaisesRegex(ValueError, "mixed"):
            self.overlay.apply(self.root, self.manifest)
        journal = self.overlay.journal_bytes(self.manifest)
        (self.root / ".pi-stack-overlay.pending").write_bytes(journal)
        self.assertEqual(self.overlay.apply(self.root, self.manifest), "applied")
        self.assertEqual((self.root / "b.js").read_text(), "export const value = 2;\n")

    def test_version_and_escaping_symlinks_refuse_without_changes(self):
        (self.root / "package.json").write_text('{"name":"fixture","version":"2"}')
        with self.assertRaisesRegex(ValueError, "version"):
            self.overlay.apply(self.root, self.manifest)
        (self.root / "package.json").write_text('{"name":"fixture","version":"1"}')
        (self.root / "a.js").unlink()
        (self.root / "a.js").symlink_to(ROOT / "README.md")
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.overlay.apply(self.root, self.manifest)
        self.assertEqual((self.root / "b.js").read_text(), "export const value = 1;\n")

    def test_changed_journal_and_package_symlink_fail_closed(self):
        (self.root / ".pi-stack-overlay.pending").write_text("another operation")
        with self.assertRaisesRegex(ValueError, "journal"):
            self.overlay.apply(self.root, self.manifest)
        self.assertEqual((self.root / "a.js").read_text(), "export const value = 1;\n")
