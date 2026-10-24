from __future__ import annotations

import hashlib
import json
from pathlib import Path

import test_failure_markers as markers
from tick_support import TickCase, info, row


class FailureRecoveryTests(TickCase):
    seed = markers.FailureMarkerTests.seed
    digest = markers.FailureMarkerTests.digest
    body = markers.FailureMarkerTests.body

    def fixture(self, role="coordinator", model="gpt-6-astra"):
        self.cwd = self.home / "etl" if role == "coordinator" else self.tmp / "worker-owned"
        self.cwd.mkdir(exist_ok=True, parents=True)
        self.stream = self.make_stream(self.home, "etl", row("coi", role, str(self.cwd)).replace("gpt-6-astra", model))
        if role != "coordinator":
            (self.cwd / ".stream").write_text(str(self.stream))
        self.seed("coi", self.cwd)
        self.original = self.body(cwd=self.cwd)
        self.original["model"]["id"] = model
        self.original.update(failureRatificationConfigured=True, failureForkSupport="ratified-prefix-v1", failureMaintenanceSupport="operation-scoped-v1")
        self.original["rotationSafety"].update(callbackInventory="native-and-extension-v1", callbacksKnown=True, nativeChildCallbacks=[])
        self.listing = [info("coi", str(self.cwd), self.log_path("coi"))]
        self.routes = [("GET", "/api/sessions", 200, self.listing), ("GET", "/api/sessions/coi/status", 200, self.original)]
        self.stub.set_routes(self.routes)
        self.assertEqual(self.tick("2026-10-06T12:00:00Z").returncode, 0)
        episode = self.state(self.stream)["failures"]["coi"]
        target = {"sessionId": "coi", "cwd": str(self.cwd), "root": str(self.stream), "stream": "etl", "episode": episode["id"], "checkpoint": {"entryId": "e4", "sha256": self.digest("coi", "e4")}, "failure": {"entryId": "e6", "sha256": self.digest("coi", "e6"), "kind": "codex-login"}}
        data = {"version": 1, "id": "offline-notice", "noticeId": "offline-notice", "provenance": "labelled-offline-contract-not-authenticated-intake", "instructions": "", "target": target, "generation": "native-parked-coi"}
        receipt = self.append("coi", "ratification", "e6", "pi-web.failure-ratification", data)
        self.original["rotationSafety"]["entryId"] = "ratification"
        self.routes.append(("POST", "/api/sessions/coi/failure-recovery/ratify", 200, {**data, **receipt}))
        self.stub.set_routes(self.routes)
        notice = self.tmp / "notice.json"
        notice.write_text(json.dumps({"label": "offline verifier fixture, never real provenance"}))
        result = self.run_streams("failure", "ratify", "etl", "--session", "coi", "--episode", episode["id"], "--notice-id", "offline-notice", "--notice-file", str(notice))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.episode = self.state(self.stream)["failures"]["coi"]
        self.request = {"cwd": str(self.cwd), "id": self.episode["recovery_id"], "episode": self.episode["id"], "expected": {**self.original["failureBoundary"], "generation": "native-parked-coi"}, "ratification": {"entryId": receipt["entryId"], "sha256": receipt["sha256"]}}
        self.result = {"version": 1, "id": self.request["id"], "episode": self.episode["id"], "originalSessionId": "coi", "cwd": str(self.cwd), "root": str(self.stream), "stream": "etl", "checkpoint": target["checkpoint"], "failure": target["failure"], "intentSha256": hashlib.sha256(json.dumps(self.request, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest(), "noticeId": "offline-notice", "provenance": data["provenance"], "instructions": "", "generation": "frozen-original", "state": "forked", "forkSessionId": "returned-fork", "forkFile": self.log_path("returned-fork"), "forkGeneration": "held-generation"}
        originals = Path(self.log_path("coi")).read_bytes().splitlines(keepends=True)
        header = {"type": "session", "version": 3, "id": "returned-fork", "cwd": str(self.cwd), "parentSession": self.log_path("coi")}
        Path(self.log_path("returned-fork")).write_bytes((json.dumps(header) + "\n").encode() + b"".join(originals[1:5]))
        self.hold = {"version": 1, "sessionId": "returned-fork", "cwd": str(self.cwd), "root": str(self.stream), "stream": "etl", "state": "recovering", "recovery": {"id": self.request["id"], "originalSessionId": "coi"}}
        self.append("returned-fork", "held", "e4", "pi-web.stream-failure", self.hold)
        self.fork_status = {**self.original, "sessionId": "returned-fork", "failureBoundary": self.hold, "rotationSafety": {"entryId": "held", "callbackInventory": "native-and-extension-v1", "callbacksKnown": True, "nativeChildCallbacks": []}}
        self.stub.automatic_admissions["returned-fork"] = {"sessionId": "returned-fork", "cwd": str(self.cwd), "allowed": False, "durable": True, "generation": "held-generation"}
        self.listing.append(info("returned-fork", str(self.cwd), self.log_path("returned-fork")))
        self.routes.append(("GET", "/api/sessions/returned-fork/status", 200, self.fork_status))
        self.routes.append(("POST", "/api/sessions/coi/failure-recovery/fork", 200, self.fork_response))
        self.stub.set_routes(self.routes)

    def append(self, sid, identity, parent, kind, data):
        raw = (json.dumps({"type": "custom", "id": identity, "parentId": parent, "customType": kind, "data": data}) + "\n").encode()
        with open(self.log_path(sid), "ab") as source:
            source.write(raw)
        return {"entryId": identity, "sha256": hashlib.sha256(raw).hexdigest()}

    def fork_response(self, body):
        self.assertEqual(body, self.request)
        self.append("coi", "fork-result", "ratification", "pi-web.failure-recovery", self.result)
        self.original["rotationSafety"]["entryId"] = "fork-result"
        self.stub.automatic_admissions["coi"]["generation"] = "frozen-original"
        return 200, self.result

    def advance(self):
        return self.run_streams("failure", "advance", "etl", "--session", "coi", "--episode", self.episode["id"])

    def test_exact_native_result_rebinds_coordinator_and_preserves_original_lineage(self):
        self.fixture()
        result = self.advance()
        self.assertEqual(result.returncode, 0, result.stderr)
        operation = self.state(self.stream)["failure_recoveries"]["coi"]
        self.assertEqual(operation["phase"], "bound")
        self.assertEqual(operation["fork"], "returned-fork")
        table = (self.stream / "threads.tsv").read_text()
        self.assertIn("coi\tcoordinator", table)
        self.assertIn("\tparked\t", table)
        self.assertIn("returned-fork\tcoordinator", table)
        self.assertEqual((self.stream / "failures/coi.lastgood").read_bytes(), b"e4\n")
        again = self.advance()
        self.assertNotEqual(again.returncode, 0, "The fork-only HTTP fixture cannot confirm maintenance preparation")
        self.assertIn("maintenance owner is unconfirmed", again.stderr)
        self.assertEqual(sum(item[1].endswith("/fork") for item in self.stub.requests), 1)

    def test_worker_rebinding_preserves_worktree_files_and_exact_model(self):
        self.fixture("research")
        before = (self.cwd / ".stream").read_bytes()
        result = self.advance()
        self.assertEqual(result.returncode, 0, result.stderr)
        table = (self.stream / "threads.tsv").read_text()
        self.assertIn(f"returned-fork\tresearch\talpha\t{self.cwd}\t", table)
        self.assertIn("openai-codex/gpt-6-astra\txhigh\tactive", table)
        self.assertEqual((self.cwd / ".stream").read_bytes(), before)

    def test_lost_reply_reconciles_native_result_without_a_second_fork(self):
        self.fixture()
        def lost(body):
            self.fork_response(body)
            return 503, {"error": "Labelled reply loss after persisted native fork"}
        self.routes[-1] = ("POST", "/api/sessions/coi/failure-recovery/fork", 200, lost)
        self.stub.set_routes(self.routes)
        self.assertNotEqual(self.advance().returncode, 0)
        self.assertEqual(self.state(self.stream)["failure_recoveries"]["coi"]["phase"], "fork-sending")
        self.assertEqual(self.advance().returncode, 0)
        self.assertEqual(self.state(self.stream)["failure_recoveries"]["coi"]["phase"], "bound")
        self.assertEqual(sum(item[1].endswith("/fork") for item in self.stub.requests), 1)

    def test_unknown_fork_result_never_replays_the_effect(self):
        self.fixture()
        self.routes[-1] = ("POST", "/api/sessions/coi/failure-recovery/fork", 503, {"error": "Labelled unknown acceptance"})
        self.stub.set_routes(self.routes)
        before = (self.stream / "threads.tsv").read_bytes()
        self.assertNotEqual(self.advance().returncode, 0)
        self.assertNotEqual(self.advance().returncode, 0)
        self.assertEqual(sum(item[1].endswith("/fork") for item in self.stub.requests), 1)
        self.assertEqual(self.state(self.stream)["failure_recoveries"]["coi"]["phase"], "fork-sending")
        self.assertEqual((self.stream / "threads.tsv").read_bytes(), before)
        self.assertEqual((self.stream / "failures/coi.lastgood").read_bytes(), b"e4\n")

    def test_newer_input_during_fork_prevents_registry_rebinding(self):
        self.fixture()
        def input_arrived(body):
            self.fork_response(body)
            self.stub.automatic_admissions["coi"]["generation"] = "newer-human-input"
            return 200, self.result
        self.routes[-1] = ("POST", "/api/sessions/coi/failure-recovery/fork", 200, input_arrived)
        self.stub.set_routes(self.routes)
        before = (self.stream / "threads.tsv").read_bytes()
        self.assertNotEqual(self.advance().returncode, 0)
        self.assertEqual((self.stream / "threads.tsv").read_bytes(), before)
        self.assertEqual(self.stub.automatic_admissions["coi"]["generation"], "newer-human-input")
        self.assertEqual((self.stream / "failures/coi.lastgood").read_bytes(), b"e4\n")

    def test_changed_prefix_preserves_original_marker_and_registry(self):
        self.fixture()
        source = Path(self.log_path("returned-fork"))
        source.write_text(source.read_text().replace("Authorized good multi-tool turn", "Changed inherited turn"))
        before = (self.stream / "threads.tsv").read_bytes()
        result = self.advance()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.stream / "threads.tsv").read_bytes(), before)
        self.assertEqual((self.stream / "failures/coi.lastgood").read_bytes(), b"e4\n")
        self.assertEqual(self.state(self.stream)["failure_recoveries"]["coi"]["phase"], "forked")
