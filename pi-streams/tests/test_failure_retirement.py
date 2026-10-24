from __future__ import annotations

import base64
import copy
import hashlib
import json
from pathlib import Path

import test_failure_dcr as cases
from tick_support import TickCase, info, reply, row, status


class FailureRetirementTests(TickCase):
    seed = cases.FailureDcrTests.seed
    digest = cases.FailureDcrTests.digest
    body = cases.FailureDcrTests.body
    fixture = cases.FailureDcrTests.fixture
    append = cases.FailureDcrTests.append
    fork_response = cases.FailureDcrTests.fork_response
    advance = cases.FailureDcrTests.advance
    start = cases.FailureDcrTests.start
    maintenance = cases.FailureDcrTests.maintenance
    message = cases.FailureDcrTests.message
    compacted = cases.FailureDcrTests.compacted
    observed = cases.FailureDcrTests.observed

    def ready_to_retire(self, role="coordinator"):
        self.start(role)
        self.compacted()
        self.observed()
        self.assertEqual(self.advance().returncode, 0)
        self.assertEqual(self.state(self.stream)["failure_recoveries"]["coi"]["phase"], "observed")
        self.original["failureRetirementSupport"] = "singular-original-v1"
        self.receipt = None
        self.deletions = 0
        self.routes.append(("POST", "/api/sessions/coi/failure-recovery/retire", 200, self.retire))
        self.stub.set_routes(self.routes)

    def retire(self, body):
        self.assertEqual(body["id"], self.op["id"])
        self.assertEqual(body["forkSessionId"], "returned-fork")
        if self.receipt is None:
            source = Path(self.log_path("coi")).read_bytes()
            self.cached_source = source
            digest = hashlib.sha256(source).hexdigest()
            archive = {"sessionId": "coi", "cwd": str(self.cwd), "originalPath": self.log_path("coi"), "archivePath": str(self.tmp / "offline-archive-original.jsonl"), "archivedAt": "2026-10-06T12:05:00Z"}
            boundary = {**self.hold, "state": "watching"}
            release = self.append("returned-fork", "released", self.fork_status["rotationSafety"]["entryId"], "pi-web.stream-failure", boundary)
            self.fork_status["failureBoundary"] = boundary
            self.fork_status["rotationSafety"]["entryId"] = "released"
            cache = self.tmp / "labelled-native-maintenance-cache.json"
            retirement = {"version": 1, "id": self.op["id"], "originalSessionId": "coi", "forkSessionId": "returned-fork", "cwd": str(self.cwd), "operation": copy.deepcopy(self.result), "observation": copy.deepcopy(self.state(self.stream)["dcr_operations"]["returned-fork"]["observation"]), "originalFile": self.log_path("coi"), "cacheFile": str(cache), "originalLeaf": self.original["rotationSafety"]["entryId"], "model": {"provider": "openai-codex", "id": self.original["model"]["id"], "thinking": "xhigh"}, "sourceSha256": digest, "sourceBase64": base64.b64encode(source).decode(), "state": "released", "archive": archive, "deleted": {"sessionId": "coi", "archivePath": archive["archivePath"], "sourceSha256": digest}, "release": release}
            cache.write_text(json.dumps({"version": 1, "sessionId": "returned-fork", "cwd": str(self.cwd), "current": self.op["id"], "operations": {self.op["id"]: {**self.native, "retirement": retirement}}}))
            self.receipt = {key: value for key, value in retirement.items() if key != "sourceBase64"}
            Path(self.log_path("coi")).unlink()
            self.deletions += 1
            self.listing[:] = [item for item in self.listing if item["id"] != "coi"]
        return 200, self.receipt

    def test_exact_durable_retirement_clears_only_original_marker_and_retains_other_worker_bytes(self):
        self.ready_to_retire()
        other = self.tmp / "unrelated-worker"
        other.mkdir()
        (other / "sentinel").write_bytes(b"unrelated worker bytes\x00\xff")
        with (self.stream / "threads.tsv").open("a") as registry:
            registry.write(row("unrelated", "research", str(other)))
        self.write_log("unrelated", str(other), reply("Independent authorized worker work."))
        self.listing.append(info("unrelated", str(other), self.log_path("unrelated")))
        self.routes.append(("GET", "/api/sessions/unrelated/status", 200, status("unrelated", streaming=True)))
        self.stub.set_routes(self.routes)
        result = self.advance()
        self.assertEqual(result.returncode, 0, result.stderr)
        saved = self.state(self.stream)["failure_recoveries"]["coi"]
        self.assertEqual(saved["phase"], "complete")
        self.assertEqual(saved["retirement"]["deleted"]["sessionId"], "coi")
        self.assertFalse((self.stream / "failures/coi.lastgood").exists())
        self.assertEqual(self.state(self.stream)["failures"]["coi"]["state"], "recovered")
        self.assertEqual((other / "sentinel").read_bytes(), b"unrelated worker bytes\x00\xff")
        self.assertIn("coi\tcoordinator", (self.stream / "threads.tsv").read_text())
        self.assertIn("\tarchived\t", (self.stream / "threads.tsv").read_text())
        self.assertEqual(self.advance().returncode, 0)
        self.assertEqual(self.deletions, 1)
        self.fork_status["controlGoalSupport"] = "preserve-ask-v1"
        self.stub.reflect_control_goals = True
        self.routes += [("POST", "/api/sessions/returned-fork/control-goal", 200, {"state": "queued"}), ("POST", "/api/sessions/returned-fork/automatic-admission", 200, dict(self.stub.automatic_admissions["returned-fork"]))]
        self.stub.set_routes(self.routes)
        enabled = self.run_streams("drive", "etl", "on")
        self.assertEqual(enabled.returncode, 0, enabled.stderr)
        ticked = self.tick("2026-10-06T12:10:00Z")
        self.assertEqual(ticked.returncode, 0, ticked.stderr)
        goals = [item for item in self.stub.requests if item[0] == "POST" and item[1].endswith("/control-goal")]
        self.assertEqual([item[1] for item in goals], ["/api/sessions/returned-fork/control-goal"])

    def test_worker_retirement_never_changes_the_owned_worktree(self):
        self.ready_to_retire("research")
        before = (self.cwd / ".stream").read_bytes()
        result = self.advance()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.state(self.stream)["failure_recoveries"]["coi"]["phase"], "complete")
        self.assertEqual((self.cwd / ".stream").read_bytes(), before)
        self.assertIn("returned-fork\tresearch", (self.stream / "threads.tsv").read_text())

    def test_reply_loss_after_native_delete_reconciles_own_receipt_before_host_cleanup(self):
        self.ready_to_retire()
        def lost(body):
            self.retire(body)
            return 503, {"error": "Labelled reply loss after durable native retirement"}
        self.routes[-1] = ("POST", "/api/sessions/coi/failure-recovery/retire", 200, lost)
        self.stub.set_routes(self.routes)
        self.assertNotEqual(self.advance().returncode, 0)
        self.assertTrue((self.stream / "failures/coi.lastgood").exists())
        self.assertEqual(self.state(self.stream)["failure_recoveries"]["coi"]["phase"], "retiring")
        self.routes[-1] = ("POST", "/api/sessions/coi/failure-recovery/retire", 200, self.retire)
        self.stub.set_routes(self.routes)
        result = self.advance()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.deletions, 1)
        self.assertFalse((self.stream / "failures/coi.lastgood").exists())

    def test_unexplained_not_found_is_not_a_deletion_receipt(self):
        self.ready_to_retire()
        self.routes[-1] = ("POST", "/api/sessions/coi/failure-recovery/retire", 404, {"error": "Labelled unexplained not-found"})
        self.stub.set_routes(self.routes)
        before = (self.stream / "threads.tsv").read_bytes()
        self.assertNotEqual(self.advance().returncode, 0)
        self.assertEqual(self.state(self.stream)["failure_recoveries"]["coi"]["phase"], "retiring")
        self.assertEqual((self.stream / "threads.tsv").read_bytes(), before)
        self.assertEqual((self.stream / "failures/coi.lastgood").read_bytes(), b"e4\n")
        self.assertEqual(self.deletions, 0)

    def test_lost_ratification_proof_after_intent_does_not_retry_a_native_effect(self):
        self.ready_to_retire()
        self.routes[-1] = ("POST", "/api/sessions/coi/failure-recovery/retire", 404, {"error": "Labelled unavailable receiving owner"})
        self.stub.set_routes(self.routes)
        self.assertNotEqual(self.advance().returncode, 0)
        data = self.state(self.stream)
        data["failures"]["coi"]["ratification"] = None
        (self.stream / "log/tick-state.json").write_text(json.dumps(data))
        self.stub.requests.clear()
        result = self.advance()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("proof is unavailable", result.stderr)
        self.assertFalse(any(item[0] == "POST" for item in self.stub.requests))
        self.assertEqual((self.stream / "failures/coi.lastgood").read_bytes(), b"e4\n")

    def test_corrupt_retained_cache_cannot_replace_independent_deletion_proof(self):
        self.ready_to_retire()
        def corrupt(body):
            response = self.retire(body)
            cache = Path(self.receipt["cacheFile"])
            data = json.loads(cache.read_text())
            data["operations"][self.op["id"]]["retirement"]["sourceBase64"] = base64.b64encode(b"Labelled corrupted source cache").decode()
            cache.write_text(json.dumps(data))
            return response
        self.routes[-1] = ("POST", "/api/sessions/coi/failure-recovery/retire", 200, corrupt)
        self.stub.set_routes(self.routes)
        self.assertNotEqual(self.advance().returncode, 0)
        self.assertEqual((self.stream / "failures/coi.lastgood").read_bytes(), b"e4\n")
        self.assertEqual(self.state(self.stream)["failure_recoveries"]["coi"]["phase"], "retiring")

    def test_foreign_marker_is_preserved_after_a_verified_native_result(self):
        self.ready_to_retire()
        marker = self.stream / "failures/coi.lastgood"
        def changed(body):
            response = self.retire(body)
            marker.write_bytes(b"foreign-marker\n")
            return response
        self.routes[-1] = ("POST", "/api/sessions/coi/failure-recovery/retire", 200, changed)
        self.stub.set_routes(self.routes)
        self.assertNotEqual(self.advance().returncode, 0)
        self.assertEqual(marker.read_bytes(), b"foreign-marker\n")
        self.assertEqual(self.state(self.stream)["failure_recoveries"]["coi"]["retirement"]["state"], "released")

    def test_newer_fork_stop_after_native_completion_preserves_the_marker_and_stop(self):
        self.ready_to_retire()
        def stopped(body):
            response = self.retire(body)
            self.stub.automatic_admissions["returned-fork"].update(allowed=False, generation="newer-explicit-stop")
            return response
        self.routes[-1] = ("POST", "/api/sessions/coi/failure-recovery/retire", 200, stopped)
        self.stub.set_routes(self.routes)
        self.assertNotEqual(self.advance().returncode, 0)
        self.assertEqual((self.stream / "failures/coi.lastgood").read_bytes(), b"e4\n")
        self.assertFalse(self.stub.automatic_admissions["returned-fork"]["allowed"])
        self.assertEqual(self.stub.automatic_admissions["returned-fork"]["generation"], "newer-explicit-stop")
        self.assertEqual(self.state(self.stream)["failure_recoveries"]["coi"]["retirement"]["state"], "released")
