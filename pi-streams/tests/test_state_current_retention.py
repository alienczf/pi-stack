from __future__ import annotations

import base64
import hashlib
import json
import os
from unittest import mock

from support import EngineCase, snapshot
from test_artifact_migration import AT, DECISIONS, STREAM, authority_map, extraction
import test_artifact_migration_apply as fixtures
from engine import StreamsError, artifacts, migration, threads


OBJECTIVE = b"## Actual next unit\r\nSTOP. Do not replay job-DONE-292.\r\n### Charter\r\nNo new grants. Inspect missing-eight-state only.\r\n````md\r\n## Log\r\n````\r\n"
RULES = "## Current job state\r\nDONE private-job-17, source-diag-29. No resubmission.\r\n### North Star\r\nKeep broad research goals unchanged. Caf\u00e9.\r\n".encode()
OLD = b"## Old grant\r\nConsumed launch grant. Never copy to Charter.\r\n"
STATE = OBJECTIVE + RULES + OLD + OLD


def current_map(stream=STREAM):
    rows = authority_map(stream)
    for row in rows:
        if row["target"] == "current_objective":
            row["target"] = "history"
    return rows + [
        extraction("STATE.md", 0, len(OBJECTIVE), "current_objective"),
        extraction("STATE.md", len(OBJECTIVE), len(OBJECTIVE) + len(RULES), "rules"),
        extraction("STATE.md", len(OBJECTIVE) + len(RULES), len(STATE), "history"),
    ]


class StateCurrentRetentionTests(EngineCase):
    seed = fixtures.MigrationApplyTests.seed
    apply = fixtures.MigrationApplyTests.apply
    count = fixtures.MigrationApplyTests.count

    def setUp(self):
        super().setUp()
        self.assertEqual(self.run_streams("init", str(self.root), "-y").returncode, 0)
        self.stream = self.seed("legacy")
        (self.stream / "STATE.md").write_bytes(STATE)
        self.stub.requests.clear()

    def current_plan(self, mapping=None):
        with mock.patch.dict(os.environ, self.env, clear=True):
            return migration.plan_migration(self.stream, current_map() if mapping is None else mapping, started_at=AT).public()

    def test_explicit_state_only_objective_and_active_stops_survive_without_field_escape(self):
        before = snapshot(self.stream)
        plan = self.current_plan()
        self.assertTrue(plan["ready"], plan["unresolved"])
        self.assertEqual(plan.get("limitations", []), [])
        state = artifacts.parse_state(base64.b64decode(plan["state"]))
        objective = state.source[state.current_objective.body.start:state.current_objective.body.end]
        rules = state.source[state.rules.body.start:state.rules.body.end]
        self.assertIn(OBJECTIVE, objective)
        self.assertIn(RULES, rules)
        self.assertIn("STOP. Do not replay job-DONE-292.", artifacts.resolve_current_goal(state))
        self.assertNotIn(b"Verify the retained artifact.", state.source[:state.log.body.start])
        self.assertEqual(state.extras, ())
        self.assertEqual(state.source[state.north_star.body.start:state.north_star.body.end].strip(), b"Ship exact evidence.")
        self.assertEqual(state.source[state.charter.body.start:state.charter.body.end].strip(), b"TARGET\nOnly the private fixture.\nNO-GO\nNever unfreeze production.")
        self.assertNotIn(b"Consumed launch grant", state.source)
        log = state.source[state.log.body.start:]
        for target, start, end in (("current_objective", 0, len(OBJECTIVE)), ("rules", len(OBJECTIVE), len(OBJECTIVE) + len(RULES))):
            record = {"source": "STATE.md", "start": start, "end": end, "target": target, "sha256": hashlib.sha256(STATE[start:end]).hexdigest(), "source_sha256": hashlib.sha256(STATE).hexdigest()}
            self.assertIn(json.dumps(record, sort_keys=True).encode(), log)
        self.assertEqual(snapshot(self.stream), before)
        self.assertEqual(self.stub.requests, [])

    def test_every_raw_occurrence_keeps_exact_hash_and_applied_operation_is_idempotent(self):
        plan = self.current_plan()
        history = [row for row in plan["history"] if row["source"] == "STATE.md"]
        self.assertEqual(b"".join(base64.b64decode(row["bytes"]) for row in history), STATE)
        repeated = [row for row in history if base64.b64decode(row["bytes"]) == OLD]
        self.assertEqual(len(repeated), 2)
        self.assertNotEqual(repeated[0]["path"], repeated[1]["path"])
        for row in history:
            self.assertEqual(row["sha256"], hashlib.sha256(STATE[row["start"]:row["end"]]).hexdigest())
        first = self.apply(plan)
        self.assertTrue(first["changed"])
        before = snapshot(self.stream)
        for document in (plan, None, plan):
            self.assertEqual(self.apply(document), {"id": plan["id"], "commit": first["commit"], "changed": False})
            self.assertEqual(snapshot(self.stream), before)
        self.assertEqual(self.count(), 2)
        self.assertEqual(b"".join((self.stream / row["path"]).read_bytes() for row in history), STATE)
        for row in history:
            self.assertEqual(hashlib.sha256((self.stream / row["path"]).read_bytes()).hexdigest(), row["sha256"])
        with mock.patch.dict(os.environ, self.env, clear=True):
            live = artifacts.read_stream_state(self.stream)
        self.assertIn("job-DONE-292", artifacts.resolve_current_goal(live))
        self.assertIn(b"private-job-17", live.source[live.rules.body.start:live.rules.body.end])
        self.assertEqual(self.stub.requests, [])

    def test_state_mapping_is_explicit_complete_nonoverlapping_and_utf8_aligned(self):
        missing = self.current_plan(current_map()[:-1])
        self.assertFalse(missing["ready"])
        self.assertTrue(any(row["source"] == "STATE.md" and row["start"] == len(OBJECTIVE) + len(RULES) and row["end"] == len(STATE) for row in missing["unresolved"]))
        for extra in (
            extraction("STATE.md", 0, 1, "history"),
            extraction("STATE.md", 0, len(STATE) + 1, "rules"),
            extraction("STATE.md", True, 2, "rules"),
            extraction("STATE.md", STATE.index(b"\xc3") + 1, len(STATE), "rules"),
        ):
            with self.subTest(extra=extra), self.assertRaises(StreamsError):
                self.current_plan(current_map() + [extra])
        absent = self.current_plan(authority_map())
        self.assertTrue(absent["ready"])
        self.assertTrue(any("STATE.md" in limit and "archival" in limit for limit in absent["limitations"]))
        self.assertIn(b"not inferred", base64.b64decode(absent["state"]))

    def test_no_state_mapping_can_promote_authority_north_star_or_charter(self):
        for target in ("ratified", "north_star", "charter"):
            rows = current_map()
            rows[-3] = {**rows[-3], "target": target}
            with self.subTest(target=target), self.assertRaisesRegex(StreamsError, "unsupported"):
                self.current_plan(rows)
        raw = STREAM.replace(b"ratified: 2026-10-20 human notice fixture-1", b"ratified: no")
        (self.stream / "STREAM.md").write_bytes(raw)
        (self.stream / "STATE.md").write_bytes(STATE.replace(b"STOP.", b"ratified: 2026-10-16. invented authority. STOP."))
        rows = authority_map(raw)
        for row in rows:
            if row["target"] == "current_objective":
                row["target"] = "history"
        size = (self.stream / "STATE.md").stat().st_size
        plan = self.current_plan(rows + [extraction("STATE.md", 0, size, "current_objective")])
        self.assertTrue(plan["ready"], plan["unresolved"])
        state = artifacts.parse_state(base64.b64decode(plan["state"]))
        self.assertEqual(state.source[state.authority.start:state.authority.end], b"ratified: no\n")
        self.assertFalse(threads._has_ratified_authority(state))
        self.assertNotIn("relay_source", plan)

    def test_inline_selections_cannot_change_sibling_fields(self):
        raw = b"prefix: STOP inline.\n### Charter\nDo not launch.\n## New section\njob-23 stays DONE.\n```unclosed\nsuffix"
        (self.stream / "STATE.md").write_bytes(raw)
        rows = [dict(row, target="history") if row["target"] == "current_objective" else row for row in authority_map()]
        start, end = len(b"prefix: "), len(raw) - len(b"suffix")
        rows += [extraction("STATE.md", 0, start, "history"), extraction("STATE.md", start, end, "current_objective"), extraction("STATE.md", end, len(raw), "history")]
        plan = self.current_plan(rows)
        self.assertTrue(plan["ready"], plan["unresolved"])
        state = artifacts.parse_state(base64.b64decode(plan["state"]))
        self.assertIn(raw[start:end], state.source[state.current_objective.body.start:state.current_objective.body.end])
        self.assertEqual(state.extras, ())
        self.assertNotIn(b"Do not launch", state.source[state.charter.body.start:state.charter.body.end])

    def test_existing_active_fields_cannot_escape_silently_into_an_extra_section(self):
        raw = DECISIONS.replace(b"Freeze remains in force.", b"Freeze remains in force.\n## Hidden rules\nSTOP remains active.")
        (self.stream / "DECISIONS.md").write_bytes(raw)
        plan = self.current_plan(authority_map(decisions=raw))
        self.assertFalse(plan["ready"])
        self.assertTrue(any("boundaries" in row["reason"] for row in plan["unresolved"]))

    def test_selected_state_source_drift_and_pending_log_ownership_refuse_without_writes(self):
        plan = self.current_plan()
        (self.stream / "STATE.md").write_bytes(STATE + b"A later STOP.\n")
        before = snapshot(self.stream)
        with self.assertRaisesRegex(StreamsError, "changed|plan"):
            self.apply(plan)
        self.assertEqual(snapshot(self.stream), before)
        (self.stream / "STATE.md").write_bytes(STATE)
        real = migration._set_phase
        def interrupt(path, operation, phase):
            real(path, operation, phase)
            if phase == "state":
                raise OSError("labelled STATE projection interruption")
        with mock.patch("engine.migration._set_phase", side_effect=interrupt), self.assertRaisesRegex(OSError, "labelled"):
            self.apply(plan)
        tick = self.stream / "log/tick-state.json"
        tick.write_text(json.dumps({"state_log": {"foreign": "pending owner"}}))
        before = snapshot(self.stream)
        with self.assertRaisesRegex(StreamsError, "ownership"):
            self.apply()
        self.assertEqual(snapshot(self.stream), before)
        self.assertEqual(self.count(), 1)
        self.assertEqual(self.stub.requests, [])

    def test_state_projection_crash_retries_converge_at_every_publication_phase(self):
        for phase in ("history", "state", "retire", "commit"):
            with self.subTest(phase=phase):
                root = self.seed("state-crash-" + phase)
                (root / "STATE.md").write_bytes(STATE)
                with mock.patch.dict(os.environ, self.env, clear=True):
                    plan = migration.plan_migration(root, current_map(), started_at=AT).public()
                real = migration._set_phase
                def interrupt(path, operation, current):
                    real(path, operation, current)
                    if current == phase:
                        raise OSError("labelled STATE projection phase interruption")
                with mock.patch("engine.migration._set_phase", side_effect=interrupt), self.assertRaisesRegex(OSError, "labelled"):
                    self.apply(plan, root)
                first = self.apply(stream=root)
                before = snapshot(root)
                self.assertFalse(self.apply(stream=root)["changed"])
                self.assertEqual(snapshot(root), before)
                self.assertEqual(self.count(root), 2)
                self.assertTrue(first["commit"])
                self.assertEqual((root / "STATE.md").read_bytes(), base64.b64decode(plan["state"]))
                self.assertEqual(b"".join((root / row["path"]).read_bytes() for row in plan["history"] if row["source"] == "STATE.md"), STATE)
        self.assertEqual(self.stub.requests, [])

    def test_pending_state_log_ownership_refuses_before_starting_projection(self):
        plan = self.current_plan()
        tick = self.stream / "log/tick-state.json"
        tick.parent.mkdir(exist_ok=True)
        tick.write_text(json.dumps({"state_log": {"version": 1, "next_occurrence": 1, "entries": [], "receipts": {}, "pending_history": [{"name": "owned-pending-history.md", "sha256": "0" * 64}]}}))
        before = snapshot(self.stream)
        with self.assertRaisesRegex(StreamsError, "ownership"):
            self.apply(plan)
        self.assertEqual(snapshot(self.stream), before)
        self.assertFalse((self.stream / "log/migration.json").exists())
        self.assertEqual(self.count(), 1)
        self.assertEqual(self.stub.requests, [])

    def test_partial_source_authority_line_refuses_even_when_its_prefix_is_dated(self):
        rows = authority_map()
        rows[0]["end"] -= len(b"fixture-1\n")
        rows.insert(1, extraction("STREAM.md", rows[0]["end"], STREAM.index(b"\n") + 1, "history"))
        plan = self.current_plan(rows)
        self.assertFalse(plan["ready"])
        self.assertTrue(any("complete source line" in row["reason"] for row in plan["unresolved"]))
