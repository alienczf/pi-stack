from __future__ import annotations

import json
from pathlib import Path

import test_failure_recovery as recovery_cases
from tick_support import TickCase, info, reply, row, status


class RecoveryLaneIsolationTests(TickCase):
    digest = recovery_cases.FailureRecoveryTests.digest
    body = recovery_cases.FailureRecoveryTests.body
    fixture = recovery_cases.FailureRecoveryTests.fixture
    append = recovery_cases.FailureRecoveryTests.append
    fork_response = recovery_cases.FailureRecoveryTests.fork_response

    def seed(self, sid, cwd):
        recovery_cases.FailureRecoveryTests.seed(self, sid, cwd)
        if self.reason == "job":
            path = Path(self.log_path(sid))
            entries = [json.loads(raw) for raw in path.read_text().splitlines()]
            next(entry for entry in entries if entry.get("id") == "e4")["message"]["details"] = {"jobId": "existing-job-42", "status": "submitted"}
            path.write_text("".join(json.dumps(entry)+"\n" for entry in entries))

    def blocked_worker(self, reason):
        self.reason = reason
        self.fixture("research")
        if reason == "stop":
            self.stub.automatic_admissions["coi"]["generation"] = "newer-explicit-worker-stop"
        marker = (self.stream / "failures/coi.lastgood").read_bytes()
        control = dict(self.stub.automatic_admissions["coi"])
        with (self.stream / "threads.tsv").open("a") as registry:
            registry.write(row("healthy", "coordinator", str(self.stream)))
            registry.write(row("other", "independent", str(self.fx.alpha_wt)))
        for sid, cwd in (("healthy", self.stream), ("other", self.fx.alpha_wt)):
            self.write_log(sid, str(cwd), reply("Prior authorized work completed in this independent lane."))
            self.listing.append(info(sid, str(cwd), self.log_path(sid)))
        self.stub.automatic_admissions["healthy"] = {"sessionId": "healthy", "cwd": str(self.stream), "generation": "healthy-generation", "allowed": True, "durable": True}
        healthy = status("healthy")
        healthy["controlGoalSupport"] = "preserve-ask-v1"
        self.stub.reflect_control_goals = True
        self.routes += [("GET", "/api/sessions/healthy/status", 200, healthy), ("GET", "/api/sessions/other/status", 200, status("other")), ("POST", "/api/sessions/healthy/control-goal", 200, {"state": "queued"}), ("POST", "/api/sessions/healthy/automatic-admission", 200, dict(self.stub.automatic_admissions["healthy"]))]
        self.stub.set_routes(self.routes)
        enabled = self.run_streams("drive", "etl", "on")
        self.assertEqual(enabled.returncode, 0, enabled.stderr)
        ticked = self.tick("2026-10-06T12:05:00Z")
        self.assertEqual(ticked.returncode, 1, "The blocked recovery must remain visible in whole-pass health")
        goals = [item for item in self.stub.requests if item[0] == "POST" and item[1].endswith("/control-goal")]
        self.assertEqual([item[1] for item in goals], ["/api/sessions/healthy/control-goal"])
        self.assertEqual(goals[0][3]["text"], "/poteto-mode <the single human-authorized outcome>")
        self.assertFalse(self.state(self.stream)["sessions"]["other"]["busy"])
        self.assertEqual((self.stream / "failures/coi.lastgood").read_bytes(), marker)
        self.assertEqual(self.stub.automatic_admissions["coi"], control)
        self.assertEqual(self.state(self.stream)["failures"]["coi"]["state"], "parked")
        self.assertFalse(any(item[0] == "POST" and item[1].startswith("/api/sessions/coi/") for item in self.stub.requests))
        health = json.loads((self.index / "tick-health.json").read_text())
        self.assertFalse(health["ok"])
        self.assertFalse(health["streams"][str(self.stream)]["ok"])
        self.assertIn("recovery coi:", ticked.stderr)
        if reason == "job":
            self.assertEqual(self.state(self.stream)["failures"]["coi"]["uncertain_jobs"], [{"id": "existing-job-42", "state": "submitted"}])

    def test_stopped_ratified_worker_does_not_block_healthy_coordinator_or_independent_observation(self):
        self.blocked_worker("stop")

    def test_unresolved_job_in_ratified_worker_does_not_block_other_authorized_lanes(self):
        self.blocked_worker("job")
