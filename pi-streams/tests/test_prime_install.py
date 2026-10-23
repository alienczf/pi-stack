"""New installer behavior with isolated fixtures. This does not prove a stock build."""
import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import StreamsError
from engine import install_prime as installer


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="merged-install-test-")
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.root = self.home / "owned-prefix"

    def runtime(self, root, text="matching source"):
        for name in installer.RUNTIME_FILES:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)

    def test_missing_prerequisite_and_invalid_percent_fail_before_writes(self):
        with patch.object(installer.shutil, "which", side_effect=lambda name: None if name == "cargo" else "/fixture/" + name):
            with self.assertRaisesRegex(StreamsError, "missing prerequisites: cargo"):
                installer.preflight(self.root, self.root / "project", "openai-codex/gpt-6.1-sol", "xhigh", .1)
        self.assertFalse(self.root.exists())
        for percent in (0, float("nan"), 101):
            with self.assertRaises(StreamsError):
                installer.preflight(self.root, self.root / "project", "openai-codex/gpt-6.1-sol", "xhigh", percent)
        self.assertFalse(self.root.exists())

    def test_early_dispatch_requires_explicit_options_without_pi_or_service_files(self):
        script = Path(__file__).resolve().parents[2] / "install.sh"
        result = subprocess.run([str(script), "--merged-poc"], env={"PATH": os.environ["PATH"], "HOME": str(self.home)}, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("--compaction-percent", result.stderr)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_wrapper_confines_kernel_runtime_uv_xdg_and_discards_inherited_override(self):
        binary = self.root / "libexec/prime-agent"
        binary.parent.mkdir(parents=True)
        binary.write_text('#!/usr/bin/env python3\nimport json,os,sys\nkeys=["PRIME_AGENT_KERNEL_VENV","PRIME_AGENT_KERNEL_PYTHON","UV_CACHE_DIR","UV_PYTHON_INSTALL_DIR","XDG_CACHE_HOME","XDG_CONFIG_HOME","XDG_DATA_HOME","PI_PACKAGE_DIR"]\nprint(json.dumps({"env":{k:os.environ.get(k) for k in keys},"argv":sys.argv[1:]}))\n')
        binary.chmod(0o755)
        installer.write_wrappers(self.root, Path(__file__).resolve().parents[2])
        env = {"PATH": os.environ["PATH"], "HOME": str(self.home), "PRIME_AGENT_KERNEL_PYTHON": "/foreign/python"}
        result = subprocess.run([str(self.root / "bin/prime-agent"), "--version"], env=env, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        self.assertEqual(data["env"]["PRIME_AGENT_KERNEL_PYTHON"], None)
        self.assertEqual(data["env"]["PRIME_AGENT_KERNEL_VENV"], str(self.root / "prime/kernel-venv"))
        self.assertEqual(data["env"]["UV_PYTHON_INSTALL_DIR"], str(self.root / "cache/python"))
        self.assertEqual(data["argv"], ["--version"])
        for key, value in data["env"].items():
            if key != "PRIME_AGENT_KERNEL_PYTHON":
                self.assertTrue(Path(value).is_relative_to(self.root))

    def test_existing_binary_cannot_pass_with_missing_or_mismatched_sidecar(self):
        source = self.root / "src/prime-agent"
        self.runtime(source / "prime-agent-runtime")
        binary = self.root / "libexec/prime-agent"
        binary.parent.mkdir(parents=True)
        binary.write_text("fixture binary")
        def run(argv, **kwargs):
            if "rev-parse" in argv:
                return installer.PRIME_REVISION + "\n"
            if "get-url" in argv:
                return installer.PRIME_URL + "\n"
            return ""
        with patch.object(installer, "run", side_effect=run):
            with self.assertRaisesRegex(StreamsError, "missing or mismatched runtime"):
                installer.install_prime(self.root)
            self.runtime(self.root / "libexec/prime-agent-runtime", "wrong revision")
            with self.assertRaisesRegex(StreamsError, "missing or mismatched runtime"):
                installer.install_prime(self.root)
        self.assertEqual(binary.read_text(), "fixture binary")

    def test_unselected_branch_is_refused_before_writes(self):
        with patch.object(installer.shutil, "which", return_value="/fixture/tool"), patch.object(installer, "git", return_value="feat/unselected\n"):
            with self.assertRaisesRegex(StreamsError, "explicitly selected feat/merged-poc"):
                installer.preflight(self.root, self.root / "project", "openai-codex/gpt-6.1-sol", "xhigh", .1)
        self.assertFalse(self.root.exists())

    def test_identical_install_is_idempotent_and_model_metadata_keeps_xhigh(self):
        original_git = installer.git
        def selected_checkout(repo, *args):
            return "feat/merged-poc\n" if args == ("branch", "--show-current") else original_git(repo, *args)
        def prime(root):
            return {"prime_source_revision": installer.PRIME_REVISION, "prime_binary_sha256": "a" * 64,
                    "prime_runtime_sha256": "b" * 64, "prime_version": "0.10.1"}
        def poteto(root):
            path = root / "src/plugins/pstack/skills/poteto-mode/SKILL.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("fixture process skill\n")
            return "c" * 40, path
        args = ["--prefix", str(self.root), "--project", str(self.root / "project"), "--coordinator-model", "openai-codex/gpt-6.1-sol", "--coordinator-thinking", "xhigh", "--compaction-percent", ".1"]
        with patch.object(installer, "git", side_effect=selected_checkout), patch.object(installer.shutil, "which", return_value="/fixture/tool"), patch.object(installer, "install_prime", side_effect=prime), patch.object(installer, "install_poteto", side_effect=poteto), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(installer.main(args), 0)
            before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
            self.assertEqual(installer.main(args), 0)
        after = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(after, before)
        model = json.loads((self.root / "prime/agent/models.json").read_text())["providers"]["openai-codex"]["models"][0]
        self.assertEqual(model["thinkingLevelMap"]["xhigh"], "xhigh")
        self.assertEqual(model["reasoning"], True)
        self.assertFalse((self.home / ".pi").exists())
        self.assertFalse((self.home / ".local/bin").exists())

    def test_explicit_thinking_keys_may_have_provider_api_aliases(self):
        for level, api_value in (("off", None), ("minimal", "low")):
            root = self.home / level
            root.mkdir()
            config = installer.prepare_project(root, root / "project", "openai-codex/gpt-6.1-sol", level, .1, root / "poteto/SKILL.md")
            stored = json.loads((root / "prime/agent/models.json").read_text())["providers"]["openai-codex"]["models"][0]
            self.assertEqual(config.coordinator.thinking, level)
            self.assertEqual(stored["thinkingLevelMap"][level], api_value)

    def test_traversal_cannot_write_outside_the_owned_prefix(self):
        self.root.mkdir()
        outside = self.home / "outside-owned-prefix.txt"
        with self.assertRaisesRegex(StreamsError, "traversal|escape"):
            installer.install_bytes(self.root, self.root / "../outside-owned-prefix.txt", b"must not escape")
        self.assertFalse(outside.exists())
        installer.install_bytes(self.root, self.root / "valid.txt", b"owned bytes")
        self.assertEqual((self.root / "valid.txt").read_bytes(), b"owned bytes")

    def test_foreign_symlink_and_conflicting_owned_file_are_not_overwritten(self):
        foreign = self.home / "foreign"
        foreign.mkdir()
        self.root.symlink_to(foreign, target_is_directory=True)
        with self.assertRaisesRegex(StreamsError, "symlink"):
            installer.install_bytes(self.root, self.root / "file", b"must not write")
        self.assertEqual(list(foreign.iterdir()), [])
        self.root.unlink()
        self.root.mkdir()
        path = self.root / "file"
        path.write_text("foreign content")
        with self.assertRaisesRegex(StreamsError, "conflicting"):
            installer.install_bytes(self.root, path, b"must not overwrite")
        self.assertEqual(path.read_text(), "foreign content")
