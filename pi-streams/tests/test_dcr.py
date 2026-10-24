from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

from tick_support import TickCase, PROMPTS, info, reply, row, status
from support import CLI, ROOT

sys.path.insert(0, str(ROOT / "pi-streams"))
from engine import StreamsError, dcr
from engine.threads import Coordinator, NativeSession, load_threads


class DcrTests(TickCase):
    def setUp(self) -> None:
        super().setUp()
        self.stream = self.make_stream(self.home, "etl", row("coord", "coordinator", str(self.home / "etl")))
        self.write_log("coord", str(self.stream), reply("Earlier completed work."))

    def operation(self) -> dict:
        data = self.state(self.stream)
        self.assertIn("dcr_operations", data, "150k must create the owned same-SID DCR operation")
        return data["dcr_operations"]["coord"]

    def routes(self, *, tokens: int = 150000, streaming: bool = True, leaf: str = "e1", operation: dict | None = None, native: dict | None = None, resume_native: dict | None = None) -> None:
        body = status("coord", tokens=tokens, streaming=streaming)
        body.update(maintenanceSupport="checkpoint-input-v1", potetoInvocationSupport="exact-goal-v1", dcrEventSupport="phase-v1", rotationSafety={"entryId": leaf})
        routes = [PROMPTS, ("GET", "/api/sessions", 200, [info("coord", str(self.stream), self.log_path("coord"))]), ("GET", "/api/sessions/coord/status", 200, body)]
        if operation is not None:
            identity = operation["id"]
            routes.extend([
                ("POST", "/api/sessions/coord/maintenance/events/watch", 200, {"id": identity, "entryId": "watch-marker"}),
                ("POST", "/api/sessions/coord/maintenance/events/close", 200, {"id": identity, "entryId": "closed-marker", "closed": True}),
            ])
            if native is not None:
                routes.extend([
                    ("GET", f"/api/sessions/coord/maintenance/{identity}", 200, native),
                    ("POST", "/api/sessions/coord/maintenance/compact", 200, native),
                    ("POST", "/api/sessions/coord/maintenance/resume", 200, native if resume_native is None else resume_native),
                ])
        self.stub.set_routes(routes)

    def start(self) -> dict:
        self.routes()
        result = self.tick("2026-10-06T12:00:00Z")
        self.assertEqual(result.returncode, 0, result.stderr)
        return self.operation()

    def ready(self, operation: dict) -> dict:
        self.routes(operation=operation)
        result = self.run_streams("dcr", "ready", "etl", "--session", "coord", "--operation", operation["id"])
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt["acknowledgement"], f"DCR SYNC ready: {operation['id']} {receipt['stateRevision']}")
        self.write_log("coord", str(self.stream), reply("Earlier completed work."), reply(receipt["acknowledgement"]))
        return self.operation()

    def backend(self, operation: dict, state: str = "compacting") -> dict:
        return {
            "version": 1, "id": operation["id"], "sessionId": "coord", "cwd": str(self.stream),
            "entryId": "e2", "generation": operation["automatic"]["generation"],
            "markerEntryId": "native-marker", "instructions": operation["compact_instructions"],
            "state": state, "inputSequence": 0, "inputs": [], "compactionEntryId": None,
            "compactionSha256": None, "resume": None,
        }

    def resumed_text(self, goal: str) -> str:
        return (
            "Read the current stream artifacts before acting:\n"
            f"- {self.stream}/AGENTS.md\n"
            f"- {self.stream}/STATE.md\n"
            "Resolve the current objective in STATE Goals, falling back to its North Star.\n"
            "Open history/, context/ and its README index, checks/, or handover/ only on demand.\n"
            "Historical entries do not override current Goals or Rules.\n"
            "Do not self-remedy environment/auth/resource failures or write new rules, skills,\n"
            "or memory because of them. Park and append a Log entry via the engine;\n"
            "the human repairs them.\n"
            f"/poteto-mode {goal}"
        )

    def test_exact_150k_trigger_coalesces_while_busy_and_never_replaces_sid(self) -> None:
        self.routes(tokens=149999)
        first = self.tick("2026-10-06T12:00:00Z")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertFalse(any(item[0] == "POST" for item in self.stub.requests))
        operation = self.start()
        posts = [item for item in self.stub.requests if item[0] == "POST"]
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0][1], "/api/sessions/coord/prompt")
        self.assertEqual(posts[0][3]["streamingBehavior"], "steer")
        self.assertIn("SYNC/DUMP", posts[0][3]["text"])
        self.assertIn(operation["id"], posts[0][3]["text"])
        self.assertEqual(operation["phase"], "sync-admitted")
        report = self.run_streams("status", "etl", "--json")
        self.assertEqual(report.returncode, 0, report.stderr)
        self.assertEqual(json.loads(report.stdout)["streams"][0]["maintenance"], [{"id": operation["id"], "session": "coord", "phase": "sync-admitted", "detail": "", "compactionEntry": ""}])
        self.routes(operation=operation)
        again = self.tick("2026-10-06T12:05:00Z")
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertFalse(any(item[0] == "POST" for item in self.stub.requests))
        self.assertEqual(self.operation()["id"], operation["id"])
        self.assertIn("coord\tcoordinator", self.rows(self.stream))
        self.assertNotIn("archived", self.rows(self.stream))

    def test_actual_native_compaction_receipt_then_fresh_exact_goal_resume(self) -> None:
        operation = self.ready(self.start())
        native = self.backend(operation)
        self.routes(streaming=False, leaf="e2", operation=operation, native=native)
        compact = self.tick("2026-10-06T12:05:00Z")
        self.assertEqual(compact.returncode, 0, compact.stderr)
        self.assertEqual(self.operation()["phase"], "compacting")
        compact_posts = [item for item in self.stub.requests if item[0] == "POST"]
        self.assertEqual([item[1] for item in compact_posts], ["/api/sessions/coord/maintenance/compact"])
        self.assertEqual(compact_posts[0][3]["expectedIdle"]["entryId"], "e2")
        goal = 'Latest "café" goal\nwith $HOME and `literal` text'
        goal_file = self.tmp / "fresh-goal.txt"
        goal_file.write_text(goal, encoding="utf-8")
        changed = self.run_streams("state", "objective", "etl", "--body-file", str(goal_file))
        self.assertEqual(changed.returncode, 0, changed.stderr)
        self.write_log("coord", str(self.stream), reply("Earlier completed work."), reply(f"DCR SYNC ready: {operation['id']} {operation['ready_revision']}"), {"type": "compaction", "summary": "Synced references and current work.", "firstKeptEntryId": "e1", "tokensBefore": 150000})
        raw = Path(self.log_path("coord")).read_bytes().splitlines(keepends=True)[-1]
        native.update(state="complete", compactionEntryId="e3", compactionSha256=hashlib.sha256(raw).hexdigest())
        resume_native = {**native, "state": "resuming", "resume": {"deliveryId": f"{operation['id']}:resume", "text": self.resumed_text(goal), "potetoGoal": goal, "generation": operation["automatic"]["generation"], "inputSequence": 0, "state": "sending"}}
        self.routes(tokens=5000, streaming=False, leaf="e3", operation=operation, native=native, resume_native=resume_native)
        resumed = self.tick("2026-10-06T12:06:00Z")
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        posts = [item for item in self.stub.requests if item[0] == "POST"]
        self.assertEqual([item[1] for item in posts], ["/api/sessions/coord/maintenance/resume"])
        self.assertEqual(posts[0][3]["text"], self.resumed_text(goal))
        self.assertEqual(posts[0][3]["potetoGoal"], goal)
        self.assertEqual(self.operation()["phase"], "resuming")
        self.assertIn("coord\tcoordinator", self.rows(self.stream))
        resume_native.update(state="resumed")
        resume_native["resume"]["state"] = "admitted"
        self.routes(tokens=5000, streaming=False, leaf="e3", operation=operation, native=resume_native)
        no_delta = self.tick("2026-10-06T12:07:00Z")
        self.assertEqual(no_delta.returncode, 0, no_delta.stderr)
        self.assertEqual(self.operation()["phase"], "resuming", "Old pre-compaction SYNC acknowledgement is not resumed progress")
        self.assertFalse(any(item[0] == "POST" for item in self.stub.requests))
        self.write_log("coord", str(self.stream), reply("Earlier completed work."), reply(f"DCR SYNC ready: {operation['id']} {operation['ready_revision']}"), {"type": "compaction", "summary": "Synced references and current work.", "firstKeptEntryId": "e1", "tokensBefore": 150000}, reply("Fresh resumed work completed."))
        self.routes(tokens=5000, streaming=False, leaf="e4", operation=operation, native=resume_native)
        completed = self.tick("2026-10-06T12:08:00Z")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(self.operation()["phase"], "complete")
        self.assertEqual([item[1] for item in self.stub.requests if item[0] == "POST"], ["/api/sessions/coord/maintenance/events/close"])

    def test_manual_compaction_is_not_aborted_or_given_an_extra_sync(self) -> None:
        self.routes()
        routes = list(self.stub.routes)
        for method, path, _, body in routes:
            if path.endswith("/status"):
                body["isCompacting"] = True
        self.stub.set_routes(routes)
        waiting = self.tick("2026-10-06T12:00:00Z")
        self.assertEqual(waiting.returncode, 0, waiting.stderr)
        self.assertFalse(any(item[0] == "POST" for item in self.stub.requests))
        operation = self.start()
        self.assertEqual(operation["phase"], "sync-admitted")
        self.assertEqual([item[1] for item in self.stub.requests if item[0] == "POST"], ["/api/sessions/coord/prompt"])

    def test_engine_log_overflow_between_ready_and_compact_keeps_synced_authority(self) -> None:
        operation = self.start()
        body = self.tmp / "log-body.txt"
        body.write_text("Completed work and its exact reference.\n", encoding="utf-8")
        for number in range(31):
            result = self.run_streams("state", "append", "etl", "--subject", f"safe-sync-{number}", "--request-id", f"safe-sync-{number}", "--body-file", str(body))
            self.assertEqual(result.returncode, 0, result.stderr)
        operation = self.ready(operation)
        before = (self.stream / "STATE.md").read_bytes().split(b"## Log", 1)[0]
        self.routes(streaming=False, leaf="e2", operation=operation, native=self.backend(operation))
        result = self.tick("2026-10-06T12:05:00Z")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.operation()["phase"], "compacting")
        self.assertEqual(len(self.state(self.stream)["state_log"]["entries"]), 30)
        self.assertEqual((self.stream / "STATE.md").read_bytes().split(b"## Log", 1)[0], before)
        self.assertEqual([item[1] for item in self.stub.requests if item[0] == "POST"], ["/api/sessions/coord/maintenance/compact"])

    def test_changed_authority_after_ready_requires_fresh_sync_without_compaction(self) -> None:
        operation = self.ready(self.start())
        goal = self.tmp / "changed-before-compact.txt"
        goal.write_text("New authorized objective before compaction", encoding="utf-8")
        changed = self.run_streams("state", "objective", "etl", "--body-file", str(goal))
        self.assertEqual(changed.returncode, 0, changed.stderr)
        self.routes(streaming=False, leaf="e2", operation=operation)
        result = self.tick("2026-10-06T12:05:00Z")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.operation()["phase"], "superseded")
        self.assertEqual([item[1] for item in self.stub.requests if item[0] == "POST"], ["/api/sessions/coord/maintenance/events/close"])

    def test_stop_after_ready_never_compacts_or_resumes(self) -> None:
        operation = self.ready(self.start())
        self.stub.automatic_admissions["coord"].update(generation="real-stop-generation", allowed=False)
        self.routes(streaming=False, leaf="e2", operation=operation)
        result = self.tick("2026-10-06T12:05:00Z")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.operation()["phase"], "superseded")
        self.assertFalse(any(item[1].endswith(("/compact", "/resume", "/prompt")) and item[0] == "POST" for item in self.stub.requests))

    def test_native_compaction_failure_is_not_misreported_as_an_explicit_stop(self) -> None:
        operation = self.ready(self.start())
        self.routes(streaming=False, leaf="e2", operation=operation, native=self.backend(operation))
        started = self.tick("2026-10-06T12:05:00Z")
        self.assertEqual(started.returncode, 0, started.stderr)
        self.assertEqual(self.operation()["phase"], "compacting")
        self.stub.automatic_admissions["coord"].update(generation="failure-induced-pause", allowed=False)
        failed = self.backend(operation, "failed")
        failed["detail"] = "Nothing to compact (session too small)"
        self.routes(streaming=False, leaf="e2", operation=operation, native=failed)
        observed = self.tick("2026-10-06T12:06:00Z")
        self.assertEqual(observed.returncode, 0, observed.stderr)
        self.assertEqual(self.operation()["phase"], "blocked")
        self.assertIn("Nothing to compact", self.operation()["detail"])
        self.assertFalse(self.stub.automatic_admissions["coord"]["allowed"])
        self.assertFalse(any(item[0] == "POST" and item[1].endswith(("/compact", "/resume", "/prompt")) for item in self.stub.requests))

    def test_real_stop_during_compaction_keeps_its_superseded_disposition(self) -> None:
        operation = self.ready(self.start())
        self.routes(streaming=False, leaf="e2", operation=operation, native=self.backend(operation))
        started = self.tick("2026-10-06T12:05:00Z")
        self.assertEqual(started.returncode, 0, started.stderr)
        self.stub.automatic_admissions["coord"].update(generation="explicit-stop", allowed=False)
        stopped = self.backend(operation, "superseded")
        stopped.update(cancelledByStop=True, detail="Explicit stop/cancel superseded maintenance")
        self.routes(streaming=False, leaf="e2", operation=operation, native=stopped)
        observed = self.tick("2026-10-06T12:06:00Z")
        self.assertEqual(observed.returncode, 0, observed.stderr)
        self.assertEqual(self.operation()["phase"], "superseded")
        self.assertFalse(self.stub.automatic_admissions["coord"]["allowed"])
        self.assertFalse(any(item[0] == "POST" and item[1].endswith(("/compact", "/resume", "/prompt")) for item in self.stub.requests))

    def test_saved_sending_sync_is_not_replayed_after_uncertain_transport(self) -> None:
        operation = self.start()
        path = self.stream / "log/tick-state.json"
        data = json.loads(path.read_text())
        data["dcr_operations"]["coord"]["phase"] = "sync-sending"
        path.write_text(json.dumps(data))  # Labelled crash injection, never a real disk fault.
        self.routes(operation=operation)
        result = self.tick("2026-10-06T12:05:00Z")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(any(item[0] == "POST" for item in self.stub.requests))
        self.assertEqual(self.operation()["phase"], "sync-sending")

    def test_native_evidence_fifo_cannot_block_the_locked_idle_advancer(self) -> None:
        operation = self.ready(self.start())
        self.routes(streaming=False, leaf="e2", operation=operation)
        path = Path(self.log_path("coord"))
        saved = path.with_suffix(".saved-regular")
        path.rename(saved)
        os.mkfifo(path)  # Labelled private native-path substitution, not a resource failure.
        try:
            try:
                result = subprocess.run([str(CLI), "dcr", "advance", "etl", "--session", "coord", "--operation", operation["id"]], env=self.env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=3)
            except subprocess.TimeoutExpired:
                self.fail("A private native FIFO blocked the locked idle advancer instead of being refused")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(self.operation()["phase"], "blocked")
            self.assertIn("regular", self.operation()["detail"])
            self.assertFalse(any(item[0] == "POST" and item[1].endswith(("/compact", "/resume")) for item in self.stub.requests))
            try:
                tick = subprocess.run([str(CLI), "tick"], env=self.env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=3)
            except subprocess.TimeoutExpired:
                self.fail("A private native FIFO blocked the locked periodic tick")
            self.assertEqual(tick.returncode, 1, tick.stderr)
            self.assertIn("regular", tick.stderr)
        finally:
            path.unlink()
            saved.rename(path)

    def test_native_evidence_symlink_is_refused_before_compaction(self) -> None:
        operation = self.ready(self.start())
        self.routes(streaming=False, leaf="e2", operation=operation, native=self.backend(operation))
        path = Path(self.log_path("coord"))
        saved = path.with_suffix(".saved-regular")
        path.rename(saved)
        path.symlink_to(saved)  # Labelled private native-path substitution.
        try:
            result = self.run_streams("dcr", "advance", "etl", "--session", "coord", "--operation", operation["id"])
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(self.operation()["phase"], "blocked")
            self.assertIn("regular", self.operation()["detail"])
            self.assertFalse(any(item[0] == "POST" and item[1].endswith(("/compact", "/resume")) for item in self.stub.requests))
        finally:
            path.unlink()
            saved.rename(path)

    def test_native_evidence_descriptor_replacement_and_append_are_detected(self) -> None:
        self.write_log("coord", str(self.stream), reply("Earlier completed work."))
        path = Path(self.log_path("coord"))
        original = path.read_bytes()
        resolved = Coordinator(load_threads(self.stream / "threads.tsv")[0], NativeSession(info("coord", str(self.stream), str(path)), {"rotationSafety": {"entryId": "e1"}}))
        loads = json.loads
        for fault in ("replace", "append"):
            with self.subTest(labelled_private_fault=fault):
                path.write_bytes(original)
                changed = False
                def mutate_after_header(value):
                    nonlocal changed
                    result = loads(value)
                    if not changed:
                        changed = True
                        if fault == "replace":
                            replaced = path.with_suffix(".replaced")
                            replaced.write_bytes(original)
                            replaced.replace(path)
                        else:
                            with path.open("ab") as handle:
                                handle.write(b"\n")
                    return result
                with mock.patch("engine.dcr.json.loads", side_effect=mutate_after_header):
                    with self.assertRaisesRegex(StreamsError, "changed"):
                        dcr.native_branch(resolved)

    def test_unconfirmed_local_drive_off_blocks_idle_event_advancement(self) -> None:
        operation = self.ready(self.start())
        self.routes(streaming=False, leaf="e2", operation=operation, native=self.backend(operation))
        self.stub.set_routes([("POST", "/api/sessions/coord/automatic-admission", 503, {"error": "Labelled unavailable stop publication"}), *self.stub.routes])
        stopped = self.run_streams("drive", "etl", "off")
        self.assertNotEqual(stopped.returncode, 0)
        self.assertFalse(self.state(self.stream)["drive"]["enabled"])
        self.assertTrue(self.stub.automatic_admissions["coord"]["allowed"])
        self.stub.requests.clear()
        advanced = self.run_streams("dcr", "advance", "etl", "--session", "coord", "--operation", operation["id"])
        self.assertEqual(advanced.returncode, 0, advanced.stderr)
        self.assertFalse(any(item[0] == "POST" and item[1].endswith(("/compact", "/resume", "/prompt")) for item in self.stub.requests))
        self.assertEqual(self.operation()["phase"], "sync-admitted")

    def test_callback_advance_refuses_wrong_root_sid_or_operation_before_effect(self) -> None:
        operation = self.ready(self.start())
        self.routes(streaming=False, leaf="e2", operation=operation)
        self.stub.requests.clear()
        result = self.run_streams("dcr", "advance", "etl", "--session", "different-sid", "--operation", operation["id"])
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(item[0] == "POST" for item in self.stub.requests))
        self.assertEqual(self.operation()["phase"], "sync-admitted")
        result = self.run_streams("dcr", "advance", "etl", "--session", "coord", "--operation", "different-operation")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(item[0] == "POST" for item in self.stub.requests))
