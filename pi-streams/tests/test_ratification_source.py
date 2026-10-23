from __future__ import annotations

import base64
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from support import ROOT, make_env, git
from test_artifact_migration import STREAM, DECISIONS, authority_map, AT

sys.path.insert(0, str(ROOT / "pi-streams"))
from engine import StreamsError, artifacts, migration, threads


class RatificationSourceTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="ratification-source-"))
        self.addCleanup(lambda: shutil.rmtree(self.root))
        (self.root / "home").mkdir()
        (self.root / "config").mkdir()
        self.env = make_env(self.root / "home", self.root / "config", "http://127.0.0.1:9")
        self.stream = self.root / "legacy"
        self.stream.mkdir()
        git(self.stream, self.env, "init")
        (self.stream / "stream.toml").write_text('project = "fixture"\npi_stack_revision = "legacy"\n')
        (self.stream / "STATE.md").write_text("old state\n")
        (self.stream / "DECISIONS.md").write_bytes(DECISIONS)

    def canonical(self, marker):
        raw = (ROOT / "pi-streams/templates/stream/STATE.md").read_bytes()
        return artifacts.parse_state(raw.replace(b"ratified: no", b"ratified: " + marker.encode(), 1))

    def test_canonical_authority_rejects_ambiguous_words_and_preserves_source_references(self):
        for marker in ("0", "unknown", "yes", "true", "1", "ZF", "ZF notice", "2026-10-23", "2026-99-99 human notice 4"):
            with self.subTest(marker=marker):
                self.assertFalse(threads._has_ratified_authority(self.canonical(marker)))
        for marker in ("2026-10-23 fixture human confirmation", "2026-10-24T01:40:00Z ZF notice genuine-42", "ZF notice 42, charter v3"):
            with self.subTest(marker=marker):
                self.assertTrue(threads._has_ratified_authority(self.canonical(marker)))
        self.assertFalse(threads._has_ratified_authority(self.canonical("no")))

    def test_ambiguous_legacy_marker_cannot_produce_a_dispatch_authorizing_migration(self):
        for marker in ("0", "unknown", "yes", "true", "1"):
            with self.subTest(marker=marker):
                raw = STREAM.replace(b"ratified: 2026-10-20 human notice fixture-1", b"ratified: " + marker.encode())
                (self.stream / "STREAM.md").write_bytes(raw)
                with mock.patch.dict(os.environ, self.env, clear=True):
                    plan = migration.plan_migration(self.stream, authority_map(raw), started_at=AT)
                self.assertFalse(plan.ready)
                self.assertTrue(plan.public()["unresolved"])
        for marker, expected in (("no", False), ("2026-10-20 human notice fixture-1", True)):
            raw = STREAM.replace(b"ratified: 2026-10-20 human notice fixture-1", b"ratified: " + marker.encode())
            (self.stream / "STREAM.md").write_bytes(raw)
            with mock.patch.dict(os.environ, self.env, clear=True):
                plan = migration.plan_migration(self.stream, authority_map(raw), started_at=AT)
            self.assertTrue(plan.ready)
            candidate = artifacts.parse_state(base64.b64decode(plan.public()["state"]))
            self.assertEqual(threads._has_ratified_authority(candidate), expected)

    def test_canonical_dispatch_guard_refuses_unknown_authority_without_native_effects(self):
        (self.stream / "stream.toml").write_text('project = "fixture"\npi_stack_revision = "fixture"\nstate_schema = 1\n')
        for marker in ("0", "unknown"):
            (self.stream / "STATE.md").write_bytes(self.canonical(marker).source)
            with mock.patch.dict(os.environ, self.env, clear=True), mock.patch("engine.piweb.call", side_effect=AssertionError("no native operation is authorized")):
                with self.assertRaisesRegex(StreamsError, "source-backed|unratified"):
                    threads.require_ratified(self.stream)
        (self.stream / "STATE.md").write_bytes(self.canonical("2026-10-23 ZF confirmed").source)
        with mock.patch.dict(os.environ, self.env, clear=True):
            threads.require_ratified(self.stream)
