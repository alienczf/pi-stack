from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
from unittest import mock

from support import EngineCase, ROOT, git, snapshot

sys.path.insert(0, str(ROOT / "pi-streams"))
from engine import StreamsError, artifacts, migration

AT = "2026-10-24T01:40:00Z"
STREAM = b"ratified: 2026-10-20 human notice fixture-1\n\nGOAL\nShip exact evidence.\n\nCURRENT\nVerify the retained artifact.\n\nTARGET\nOnly the private fixture.\nNO-GO\nNever unfreeze production.\n"
DECISIONS = b"# DECISIONS\n\nFreeze remains in force.\nRetired experiment.\n"


def extraction(source, start, end, target):
    return {"source": source, "start": start, "end": end, "target": target}


def authority_map(stream=STREAM, decisions=DECISIONS):
    marker_end = stream.index(b"\n") + 1
    goal_start = stream.index(b"Ship exact evidence.")
    goal_end = stream.index(b"CURRENT\n")
    objective_start = goal_end + len(b"CURRENT\n")
    objective_end = stream.index(b"TARGET\n")
    freeze = decisions.index(b"Freeze remains")
    retired = decisions.index(b"Retired experiment")
    return [
        extraction("STREAM.md", 0, marker_end, "ratified"),
        extraction("STREAM.md", marker_end, goal_start, "history"),
        extraction("STREAM.md", goal_start, goal_end, "north_star"),
        extraction("STREAM.md", goal_end, objective_start, "history"),
        extraction("STREAM.md", objective_start, objective_end, "current_objective"),
        extraction("STREAM.md", objective_end, len(stream), "charter"),
        extraction("DECISIONS.md", 0, freeze, "history"),
        extraction("DECISIONS.md", freeze, retired, "rules"),
        extraction("DECISIONS.md", retired, len(decisions), "history"),
    ]


class MigrationPlanningTests(EngineCase):
    def setUp(self):
        super().setUp()
        result = self.run_streams("init", str(self.root), "-y")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.stream = self.register_stream("legacy")
        (self.stream / "threads.tsv").write_text("session\trole\trepo\tworktree\tbranch\tbase\tmodel\tthinking\tstatus\tstarted\n")
        (self.stream / "stream.toml").write_text('project = "proj"\npi_stack_revision = "legacy"\n')
        (self.stream / "STREAM.md").write_bytes(STREAM)
        (self.stream / "DECISIONS.md").write_bytes(DECISIONS)
        self.old = b"preamble\r\n## Repeated\r\nold caf\xc3\xa9\r\n```md\r\n## fenced\r\n```\r\n## Repeated\r\nsecond\r\n##\r\nempty heading\r\n"
        (self.stream / "STATE.md").write_bytes(self.old)
        git(self.stream, self.env, "init")
        git(self.stream, self.env, "add", "STREAM.md", "DECISIONS.md", "STATE.md", "stream.toml", "threads.tsv")
        dated = {**self.env, "GIT_AUTHOR_DATE": "2026-10-01T00:00:00Z", "GIT_COMMITTER_DATE": "2026-10-01T00:00:00Z"}
        git(self.stream, dated, "commit", "-m", "legacy fixture")
        self.stub.requests.clear()

    def plan(self, mapping=None):
        with mock.patch.dict(os.environ, self.env, clear=True):
            return migration.plan_migration(self.stream, mapping, started_at=AT)

    def test_exact_raw_snapshots_and_ordered_state_reconstruction_without_writes(self):
        before = snapshot(self.stream)
        plan = self.plan(authority_map())
        self.assertTrue(plan.ready)
        public = plan.public()
        parts = [part for part in public["history"] if part["source"] == "STATE.md"]
        self.assertEqual(b"".join(base64.b64decode(part["bytes"]) for part in parts), self.old)
        self.assertEqual([part["start"] for part in parts], sorted(part["start"] for part in parts))
        self.assertEqual(len(parts), 4)
        for name, raw in (("STREAM.md", STREAM), ("DECISIONS.md", DECISIONS)):
            source = public["sources"][name]
            self.assertEqual(base64.b64decode(source["bytes"]), raw)
            self.assertEqual(source["sha256"], hashlib.sha256(raw).hexdigest())
            self.assertTrue(source["git_head"])
        self.assertEqual(snapshot(self.stream), before)
        self.assertEqual(self.stub.requests, [])

    def test_explicit_uppercase_charter_map_preserves_authority_and_active_freeze(self):
        plan = self.plan(authority_map())
        state = artifacts.parse_state(base64.b64decode(plan.public()["state"]))
        self.assertEqual(artifacts.resolve_current_goal(state), "Verify the retained artifact.")
        self.assertIn(b"ratified: 2026-10-20 human notice fixture-1\n", state.source)
        self.assertEqual(state.source[state.rules.body.start:state.rules.body.end].strip(), b"Freeze remains in force.")
        charter = state.source[state.charter.body.start:state.charter.body.end]
        self.assertIn(b"NO-GO\nNever unfreeze production.", charter)
        self.assertNotIn(b"Retired experiment", state.source)
        self.assertEqual(state.source[state.log.body.start:].count(b"### "), 1)

    def test_missing_and_incomplete_maps_report_exact_unresolved_source_spans(self):
        absent = self.plan()
        self.assertFalse(absent.ready)
        self.assertEqual({item["source"] for item in absent.public()["unresolved"]}, {"STREAM.md", "DECISIONS.md"})
        partial = authority_map()[:-1]
        plan = self.plan(partial)
        self.assertFalse(plan.ready)
        self.assertIn(extraction("DECISIONS.md", DECISIONS.index(b"Retired experiment"), len(DECISIONS), "unresolved"), [{key: value for key, value in item.items() if key in ("source", "start", "end", "target")} for item in plan.public()["unresolved"]])

    def test_overlapping_or_outside_or_wrong_source_mappings_refuse(self):
        for changed in (
            authority_map() + [extraction("STREAM.md", 0, 4, "history")],
            [extraction("../worker/STATE.md", 0, 1, "rules")],
            [extraction("STREAM.md", 0, len(STREAM) + 1, "charter")],
        ):
            with self.subTest(changed=changed):
                with self.assertRaises(StreamsError):
                    self.plan(changed)

    def test_known_section_introduction_time_is_not_latest_whole_file_time(self):
        (self.stream / "STATE.md").write_bytes(self.old + b"## Later\nnew\n")
        git(self.stream, self.env, "add", "STATE.md")
        git(self.stream, {**self.env, "GIT_AUTHOR_DATE": "2026-10-22T00:00:00Z", "GIT_COMMITTER_DATE": "2026-10-22T00:00:00Z"}, "commit", "-m", "later section")
        parts = [p for p in self.plan(authority_map()).public()["history"] if p["source"] == "STATE.md"]
        self.assertEqual(parts[1]["at"], "2026-10-01T00:00:00Z")
        self.assertEqual(parts[-1]["at"], "2026-10-22T00:00:00Z")
        self.assertEqual(parts[1]["time_source"], "git-exact-entry-introduction")

    def test_untracked_bytes_use_stable_explicit_fallback_not_mtime(self):
        (self.stream / "STATE.md").write_bytes(b"no heading, not committed\n")
        os.utime(self.stream / "STATE.md", (1, 1))
        first = self.plan(authority_map()).public()
        os.utime(self.stream / "STATE.md", (100000, 100000))
        second = self.plan(authority_map()).public()
        self.assertEqual(first, second)
        part = next(p for p in first["history"] if p["source"] == "STATE.md")
        self.assertEqual(part["at"], AT)
        self.assertEqual(part["time_source"], "migration-start-fallback")

    def test_unratified_marker_remains_unratified(self):
        raw = STREAM.replace(b"ratified: 2026-10-20 human notice fixture-1", b"ratified: no")
        (self.stream / "STREAM.md").write_bytes(raw)
        plan = self.plan(authority_map(raw))
        self.assertTrue(plan.ready)
        self.assertTrue(base64.b64decode(plan.public()["state"]).startswith(b"## Goals\nratified: no\n"))

    def test_unknown_intermediate_schema_and_source_symlinks_refuse_without_writes(self):
        target = self.stream / "GOAL.md"
        target.write_text("Unknown intermediate authority\n")
        with self.assertRaisesRegex(StreamsError, "GOAL.md"):
            self.plan(authority_map())
        target.unlink()
        original = self.stream / "STREAM.md"
        original.unlink()
        original.symlink_to(self.fx.alpha / "README")
        with self.assertRaisesRegex(StreamsError, "regular|symlink"):
            self.plan(authority_map())

    def test_excluded_files_markers_and_worker_pointers_are_not_migration_inputs(self):
        for name in ("TODO.md", "PLAN.md", "ALERTS.md", "decisions.tsv", "GOAL-not-authority.md"):
            (self.stream / name).write_text("Opaque unrelated data, not migration authority\n")
        failures = self.stream / "failures"
        failures.mkdir()
        (failures / "12345678-1234-1234-1234-123456789abc.lastgood").write_text("actual-entry-id\n")
        (self.stream / ".stream").write_text(str(self.fx.alpha_wt))
        before = snapshot(self.stream)
        plan = self.plan(authority_map()).public()
        self.assertEqual(set(plan["sources"]), {"STREAM.md", "STATE.md", "DECISIONS.md"})
        self.assertEqual(snapshot(self.stream), before)
        self.assertEqual(self.stub.requests, [])

    def test_empty_and_unclosed_fenced_old_state_are_retained_without_normalization(self):
        for raw in (b"", b"no headings\r\n", b"## Entry\n```md\n## still inside fence\n"):
            with self.subTest(raw=raw):
                (self.stream / "STATE.md").write_bytes(raw)
                parts = [part for part in self.plan(authority_map()).public()["history"] if part["source"] == "STATE.md"]
                self.assertEqual(b"".join(base64.b64decode(part["bytes"]) for part in parts), raw)
                self.assertEqual(len(parts), 1)

    def test_history_escape_and_fifo_source_refuse_before_reading(self):
        history = self.stream / "history"
        history.symlink_to(self.outside, target_is_directory=True)
        with self.assertRaisesRegex(StreamsError, "history"):
            self.plan(authority_map())
        history.unlink()
        state = self.stream / "STATE.md"
        state.unlink()
        os.mkfifo(state)
        with self.assertRaisesRegex(StreamsError, "regular"):
            self.plan(authority_map())

    def test_cli_plan_selects_registered_root_only_and_never_calls_native(self):
        mapping = self.tmp / "mapping.json"
        mapping.write_text(json.dumps(authority_map()))
        before = snapshot(self.stream)
        result = self.run_streams("migrate", "legacy", "--plan", "--mapping", str(mapping))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["ready"])
        self.assertEqual(snapshot(self.stream), before)
        self.assertEqual(self.stub.requests, [])
