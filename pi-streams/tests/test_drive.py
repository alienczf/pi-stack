from __future__ import annotations

import json
from pathlib import Path

from tick_support import TickCase, PROMPTS, failure, info, reply, row, status


class DriveTests(TickCase):
    def setUp(self) -> None:
        super().setUp()
        self.stream = self.make_stream(self.home, "etl", row("coord", "coordinator", str(self.home / "etl")))
        self.write_log("coord", str(self.stream), reply("Previous authorized work finished."))
        self.stub.reflect_control_goals = True
        self.goal = "<the single human-authorized outcome>"
        self.routes()

    def routes(self, *, streaming=False, worker=False, ask=None, tokens=1000):
        body = status("coord", streaming=streaming, ask=ask, tokens=tokens)
        body["controlGoalSupport"] = "preserve-ask-v1"
        native = [info("coord", str(self.stream), self.log_path("coord"))]
        routes = [PROMPTS, ("GET", "/api/sessions/coord/status", 200, body), ("POST", "/api/sessions/coord/control-goal", 200, {"state": "queued"}), ("POST", "/api/sessions/coord/automatic-admission", 200, {"sessionId": "coord", "cwd": str(self.stream), "generation": self.stub.automatic_admissions["coord"]["generation"], "allowed": True, "durable": True})]
        if worker:
            native.append(info("worker", str(self.fx.alpha_wt), self.log_path("worker")))
            routes.append(("GET", "/api/sessions/worker/status", 200, status("worker")))
        routes.append(("GET", "/api/sessions", 200, native))
        self.stub.set_routes(routes)

    def enable(self):
        result = self.run_streams("drive", "etl", "on")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["enabled"])

    def drive(self):
        return self.state(self.stream)["drive"]

    def goal_posts(self):
        return [request for request in self.stub.requests if request[0] == "POST" and request[1].endswith("/control-goal")]

    def test_drive_is_explicitly_off_by_default_then_injects_current_goal_when_idle_without_events(self):
        before = (self.stream / "STATE.md").read_bytes()
        initial = self.tick("2026-10-06T12:00:00Z")
        self.assertEqual(initial.returncode, 0, initial.stderr)
        self.assertEqual(self.goal_posts(), [])
        self.enable()
        result = self.tick("2026-10-06T12:05:00Z")
        self.assertEqual(result.returncode, 0, result.stderr)
        posts = self.goal_posts()
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0][1], "/api/sessions/coord/control-goal")
        self.assertEqual(posts[0][3]["text"], f"/poteto-mode {self.goal}")
        self.assertEqual(posts[0][3]["potetoGoal"], self.goal)
        self.assertEqual(self.drive()["desired"]["goal"], self.goal)
        self.assertEqual((self.stream / "STATE.md").read_bytes(), before)

    def test_drive_off_disables_receiving_generation_without_completing_north_star(self):
        self.enable()
        before = (self.stream / "STATE.md").read_bytes()
        routes = []
        for method, path, code, body in self.stub.routes:
            if method == "POST" and path.endswith("/automatic-admission"):
                body = {**body, "allowed": False, "generation": "explicit-drive-off"}
            routes.append((method, path, code, body))
        self.stub.set_routes(routes)
        result = self.run_streams("drive", "etl", "off")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(json.loads(result.stdout)["enabled"])
        self.stub.automatic_admissions["coord"].update(generation="explicit-drive-off", allowed=False)
        ticked = self.tick("2026-10-06T12:05:00Z")
        self.assertEqual(ticked.returncode, 0, ticked.stderr)
        self.assertEqual(self.goal_posts(), [])
        self.assertEqual((self.stream / "STATE.md").read_bytes(), before)

    def test_off_intent_survives_unavailable_native_observation_and_does_not_guess_a_target(self):
        self.enable()
        self.stub.set_routes([(method, path, 503 if path.endswith("/status") else code, {"error": "Labelled unavailable observation"} if path.endswith("/status") else body) for method, path, code, body in self.stub.routes])
        self.stub.requests.clear()
        stopped = self.run_streams("drive", "etl", "off")
        self.assertNotEqual(stopped.returncode, 0)
        self.assertFalse(self.drive()["enabled"])
        self.assertIn("unconfirmed", stopped.stderr)
        self.assertEqual(self.drive()["remote_state"], "off-unconfirmed")
        self.assertFalse(any(item[0] == "POST" for item in self.stub.requests))
        self.routes(tokens=180000)
        later = self.tick("2026-10-06T12:05:00Z")
        self.assertEqual(later.returncode, 0, later.stderr)
        self.assertEqual(self.goal_posts(), [])
        self.assertFalse(self.drive()["enabled"])

    def test_off_intent_survives_failed_remote_publication_and_never_reenables_on_readiness(self):
        self.enable()
        self.stub.set_routes([(method, path, 503 if method == "POST" and path.endswith("/automatic-admission") else code, {"error": "Labelled disable-publication failure"} if method == "POST" and path.endswith("/automatic-admission") else body) for method, path, code, body in self.stub.routes])
        stopped = self.run_streams("drive", "etl", "off")
        self.assertNotEqual(stopped.returncode, 0)
        self.assertFalse(self.drive()["enabled"])
        self.assertIn("unconfirmed", stopped.stderr)
        self.assertEqual(self.drive()["remote_state"], "off-unconfirmed")
        self.routes(tokens=180000)
        later = self.tick("2026-10-06T12:05:00Z")
        self.assertEqual(later.returncode, 0, later.stderr)
        self.assertEqual(self.goal_posts(), [])
        self.assertFalse(self.drive()["enabled"])
        self.assertTrue(self.stub.automatic_admissions["coord"]["allowed"], "Fixture preserves the unconfirmed remote state rather than pretending stop was durable")

    def test_off_saves_negative_intent_when_exact_native_target_is_missing(self):
        self.enable()
        self.stub.set_routes([(method, path, code, [] if method == "GET" and path == "/api/sessions" else body) for method, path, code, body in self.stub.routes])
        self.stub.requests.clear()
        stopped = self.run_streams("drive", "etl", "off")
        self.assertNotEqual(stopped.returncode, 0)
        self.assertFalse(self.drive()["enabled"])
        self.assertEqual(self.drive()["remote_state"], "off-unconfirmed")
        self.assertIn("unconfirmed", stopped.stderr)
        self.assertFalse(any(item[0] == "POST" for item in self.stub.requests))
        self.routes(tokens=180000)
        later = self.tick("2026-10-06T12:05:00Z")
        self.assertEqual(later.returncode, 0, later.stderr)
        self.assertFalse(any(item[0] == "POST" for item in self.stub.requests))

    def test_on_remains_locally_disabled_if_receiving_enable_publication_fails(self):
        self.stub.set_routes([(method, path, 503 if method == "POST" and path.endswith("/automatic-admission") else code, {"error": "Labelled enable-publication failure"} if method == "POST" and path.endswith("/automatic-admission") else body) for method, path, code, body in self.stub.routes])
        started = self.run_streams("drive", "etl", "on")
        self.assertNotEqual(started.returncode, 0)
        self.assertFalse(self.drive()["enabled"])
        self.assertEqual(self.drive()["remote_state"], "on-unconfirmed")
        self.routes(tokens=180000)
        later = self.tick("2026-10-06T12:05:00Z")
        self.assertEqual(later.returncode, 0, later.stderr)
        self.assertFalse(any(item[0] == "POST" for item in self.stub.requests))

    def test_idle_and_all_outage_labels_get_identical_cause_independent_goal_payload(self):
        self.enable()
        seen = []
        for number, error in enumerate([None, "Codex usage limit, reset later", "Expired Codex login", "Tool login expired", "ENOSPC disk full", "Other model outage"], 1):
            self.write_log("coord", str(self.stream), reply("idle") if error is None else failure(error))
            for native in self.stub.control_goals.values():
                native["state"] = "ended"
            self.routes()
            result = self.tick(f"2026-10-06T12:{number:02d}:00Z")
            self.assertEqual(result.returncode, 0, result.stderr)
            posts = self.goal_posts()
            self.assertEqual(len(posts), 1, (error, self.stub.requests))
            seen.append((posts[0][3]["text"], posts[0][3]["potetoGoal"]))
        self.assertEqual(seen, [(f"/poteto-mode {self.goal}", self.goal)] * 6)

    def test_queued_goal_coalesces_and_changed_objective_preserves_exact_arguments(self):
        self.enable()
        first = self.tick("2026-10-06T12:00:00Z")
        self.assertEqual(first.returncode, 0, first.stderr)
        initial_id = self.drive()["current_delivery"]
        again = self.tick("2026-10-06T12:05:00Z")
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(self.drive()["current_delivery"], initial_id)
        self.assertTrue(all(request[3]["id"] == initial_id for request in self.goal_posts()))
        goal = 'Latest "café" objective\r\nwith $HOME and `literal` punctuation'
        source = self.tmp / "new-objective.txt"
        source.write_bytes(goal.encode())
        changed = self.run_streams("state", "objective", "etl", "--body-file", str(source))
        self.assertEqual(changed.returncode, 0, changed.stderr)
        latest = self.tick("2026-10-06T12:10:00Z")
        self.assertEqual(latest.returncode, 0, latest.stderr)
        posts = self.goal_posts()
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0][3]["text"], f"/poteto-mode {goal}")
        self.assertEqual(posts[0][3]["potetoGoal"], goal)
        self.assertNotEqual(posts[0][3]["id"], initial_id)
        records = self.state(self.stream)["deliveries"]
        self.assertEqual(records[initial_id]["body"], f"/poteto-mode {self.goal}")
        self.assertEqual(records[initial_id]["control"]["state"], "superseded")

    def test_stalled_worker_routes_goal_to_its_busy_coordinator_not_worker_replay(self):
        table = (self.stream / "threads.tsv").read_text()
        (self.stream / "threads.tsv").write_text(table + row("worker", "worker", str(self.fx.alpha_wt), branch="feat-a"))
        self.write_log("worker", str(self.fx.alpha_wt), reply("waiting for stream reconciliation"))
        self.routes(streaming=True, worker=True)
        self.enable()
        data = self.state(self.stream)
        data["sessions"] = {"worker": {"busy": True, "replay": [["uncertain external job submission", "steer"]]}}
        (self.stream / "log/tick-state.json").write_text(json.dumps(data))
        result = self.tick("2026-10-06T12:00:00Z")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([request[1] for request in self.goal_posts()], ["/api/sessions/coord/control-goal"])
        self.assertEqual(self.goal_posts()[0][3]["text"], f"/poteto-mode {self.goal}")
        self.assertFalse(any(request[0] == "POST" and request[1].startswith("/api/sessions/worker/") for request in self.stub.requests))
        self.assertEqual(self.state(self.stream)["sessions"]["worker"]["replay"], [["uncertain external job submission", "steer"]])

    def test_question_stall_uses_control_input_without_sending_a_human_prompt_or_answer(self):
        question = {"askId": "real-human-question", "questions": [{"id": "scope", "question": "Which scope?", "options": [], "allowOther": True}]}
        self.routes(streaming=True, ask=question)
        self.enable()
        result = self.tick("2026-10-06T12:00:00Z")
        self.assertEqual(result.returncode, 0, result.stderr)
        posts = [request for request in self.stub.requests if request[0] == "POST"]
        self.assertEqual([item[1] for item in posts], ["/api/sessions/coord/control-goal"])
        self.assertEqual(posts[0][3]["text"], f"/poteto-mode {self.goal}")
        response = self.run_streams("drive", "etl", "status")
        self.assertEqual(response.returncode, 0, response.stderr)
        self.assertEqual(json.loads(response.stdout)["desired"]["goal"], self.goal)

    def test_stop_fence_retains_current_goal_intent_without_old_outage_or_pending_veto(self):
        self.enable()
        self.stub.automatic_admissions["coord"].update(generation="real-receiving-stop", allowed=False)
        self.write_log("coord", str(self.stream), failure("Expired login is not release authority"))
        self.routes()
        result = self.tick("2026-10-06T12:00:00Z")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.drive()["desired"]["body"], f"/poteto-mode {self.goal}")
        identity = self.drive()["current_delivery"]
        record = self.state(self.stream)["deliveries"][identity]
        self.assertEqual(record["state"], "blocked")
        self.assertEqual(record["body"], f"/poteto-mode {self.goal}")
        self.assertEqual(self.goal_posts(), [])

    def test_known_receiving_refusal_can_admit_same_unsent_intent_later_without_growing_copies(self):
        self.enable()
        routes = [(method, path, 409 if method == "POST" and path.endswith("/control-goal") else code, {"error": "A prior native control admission still owns the slot"} if method == "POST" and path.endswith("/control-goal") else body) for method, path, code, body in self.stub.routes]
        self.stub.set_routes(routes)
        refused = self.tick("2026-10-06T12:00:00Z")
        self.assertEqual(refused.returncode, 0, refused.stderr)
        identity = self.drive()["current_delivery"]
        self.assertEqual(self.state(self.stream)["deliveries"][identity]["state"], "blocked")
        self.routes()
        ready = self.tick("2026-10-06T12:05:00Z")
        self.assertEqual(ready.returncode, 0, ready.stderr)
        self.assertEqual([item[3]["id"] for item in self.goal_posts()], [identity])
        self.assertEqual(self.drive()["current_delivery"], identity)
        self.assertEqual(self.state(self.stream)["deliveries"][identity]["state"], "transport_accepted")

    def test_uncertain_native_control_admission_is_not_replayed_and_goal_stays_visible(self):
        self.enable()
        first = self.tick("2026-10-06T12:00:00Z")
        self.assertEqual(first.returncode, 0, first.stderr)
        identity = self.drive()["current_delivery"]
        self.stub.control_goals[identity]["state"] = "uncertain"
        result = self.tick("2026-10-06T12:05:00Z")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.goal_posts(), [])
        self.assertEqual(self.drive()["desired"]["goal"], self.goal)
        self.assertEqual(self.drive()["current_delivery"], identity)
        self.assertEqual(self.state(self.stream)["deliveries"][identity]["control"]["state"], "uncertain")
