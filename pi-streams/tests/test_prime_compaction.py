"""New offline controller behavior. Socket fixtures are not native inference proof."""
import json
from dataclasses import replace
from uuid import uuid4
from prime_support import PrimeCase, project, state
from engine.prime import PrimeClient, check_compaction, run_compaction, send_stream_message, read_compaction_entry
from stub_prime import StubPrime


class CompactionTests(PrimeCase):
    def setUp(self):
        super().setUp()
        self.native = self.root / "native"
        self.native.mkdir()
        self.transcript = self.native / "session.jsonl"
        self.connection.update(sessionFile=str(self.transcript), contextUsage={"percent": 0, "tokens": 0, "contextWindow": 500000})
        self.nodes = [{"id": "leaf-one", "parentId": None, "type": "message", "message": {"role": "user", "content": "fixture"}}]
        self.summary = "Original intent, open work and exact references remain."
        self.persist = True
        self.dump_ok = True
        self.compact_ok = True
        self.checked_save = True
        self.on_compact = None
        self.after_dump = None
        self.after_pause = None
        self.events = []
        self.parked = None

    def handler(self, stub, request):
        kind = request["command"]["type"]
        self.events.append(kind)
        if kind == "prompt_and_wait":
            text = request["command"]["message"]
            body = json.loads(text.split("Message body as JSON follows.\n", 1)[1].split("\n", 1)[0])
            if body.startswith("Prepare this stream session for compaction."):
                self.events.append("save-turn")
                if self.checked_save:
                    current = state.check_state(self.stream)
                    state.update_state(self.stream, expect=current.sha256,
                        goals=replace(current.goals, objective="Fresh checked save objective"), rules=None,
                        entry={"subject": "Checked save before compact", "body": {"findings": "Unfinished work, uncertainty and originals preserved"}, "original_entries": [w.original_entry for w in current.goals.work]})
                if self.after_dump:
                    self.after_dump()
                return stub.response(request) if self.dump_ok else stub.response(request, success=False, error="save turn refused")
            if any(e.get("type") == "compaction" for e in self.nodes):
                self.parked = request
                self.events.append("parked-input")
                return None
            return stub.response(request)
        if kind == "acquire_session_input_pause":
            if self.after_pause:
                self.after_pause()
            return stub.response(request, {"pauseId": "owned-pause"})
        if kind == "release_session_input_pause":
            response = stub.response(request, {"released": True})
            if self.parked:
                pending, self.parked = self.parked, None
                return [response, stub.response(pending)]
            return response
        if kind == "get_session_tree":
            return stub.response(request, {"flatNodes": [{"entry": e} for e in self.nodes], "leafId": self.connection["leafId"]})
        if kind == "compact":
            self.assertIn("Preserve original requests separately", request["command"]["customInstructions"])
            self.assertIn("save-turn", self.events)
            if self.on_compact:
                self.on_compact()
            if not self.compact_ok:
                return stub.response(request, success=False, error="compact refused")
            entry = {"id": "compact-one", "parentId": self.connection["leafId"], "type": "compaction", "summary": self.summary}
            self.nodes.append(entry)
            self.connection["leafId"] = "compact-one"
            if self.persist:
                self.transcript.write_text("\n".join(json.dumps(e) for e in [{"type": "session", "id": "durable"}, *self.nodes]) + "\n")
            self.connection["contextUsage"] = None
            return stub.response(request, {"summary": self.summary, "tokensBefore": 300000})
        return super().handler(stub, request)

    def prepare(self, client):
        ref = self.active()
        original = state._parse_entry(state.read_entry(self.stream, ref))
        send_stream_message(client, self.stream, self.identity, body=original.body["text"],
                            command_id=original.command, sender="operator", lane="steer", sessions_dir=self.native)
        self.connection["contextUsage"] = {"percent": 51, "tokens": 255000, "contextWindow": 500000}
        self.events.clear()
        return ref

    def test_below_equal_above_and_unknown_percentage(self):
        with StubPrime(self.handler) as stub, PrimeClient(stub.path) as client:
            for percent, expected in ((49, "not-due"), (50, "not-due"), (None, "unknown")):
                self.connection["contextUsage"]["percent"] = percent
                self.assertEqual(check_compaction(client, self.stream, self.identity, sessions_dir=self.native)["status"], expected)
            self.connection["contextUsage"] = None
            self.assertEqual(check_compaction(client, self.stream, self.identity, sessions_dir=self.native)["status"], "unknown")
        self.assertNotIn("compact", self.events)

    def test_save_pause_recheck_direct_compact_disk_readback_and_release_before_resume_wait(self):
        with StubPrime(self.handler) as stub, PrimeClient(stub.path) as client:
            self.prepare(client)
            result = check_compaction(client, self.stream, self.identity, sessions_dir=self.native)
        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["readback"]["id"], "compact-one")
        self.assertEqual(result["readback"]["summary"], self.summary)
        self.assertLess(self.events.index("save-turn"), self.events.index("acquire_session_input_pause"))
        self.assertLess(self.events.index("acquire_session_input_pause"), self.events.index("compact"))
        self.assertLess(self.events.index("compact"), self.events.index("release_session_input_pause"))
        self.assertEqual(self.events.count("compact"), 1)
        self.assertEqual(self.events.count("parked-input"), 1)
        self.assertEqual(state.check_state(self.stream).goals.objective, "Fresh checked save objective")
        prompts = [r["command"] for r in stub.requests if r["command"]["type"] == "prompt_and_wait"]
        self.assertIn("Compaction saved native entry", prompts[-1]["message"])
        self.assertEqual(prompts[-1]["streamingBehavior"], "followUp")
        self.assertFalse(any(r["command"]["type"] in {"set_auto_compaction", "compact.run"} for r in stub.requests))

    def test_missing_disk_entry_yields_unknown_no_resume_and_no_second_compact(self):
        self.persist = False
        with StubPrime(self.handler) as stub, PrimeClient(stub.path) as client:
            self.prepare(client)
            result = check_compaction(client, self.stream, self.identity, sessions_dir=self.native)
            again = check_compaction(client, self.stream, self.identity, sessions_dir=self.native)
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(again["status"], "held")
        self.assertEqual(self.events.count("compact"), 1)
        self.assertIn("release_session_input_pause", self.events)
        self.assertEqual(self.events.count("prompt_and_wait"), 1)

    def failed_sequence(self, failure):
        self.checked_save = failure != "unchecked"
        self.dump_ok = failure != "save"
        self.compact_ok = failure != "compact"
        with StubPrime(self.handler) as stub, PrimeClient(stub.path) as client:
            self.prepare(client)
            result = run_compaction(client, self.stream, self.identity, trigger="explicit", sessions_dir=self.native)
        self.assertEqual(result["status"], "unknown")
        self.assertNotIn("Compaction saved native entry", "".join(str(r) for r in stub.requests))

    def test_checked_save_is_required(self):
        self.failed_sequence("unchecked")

    def test_failed_save_cannot_compact_or_resume(self):
        self.failed_sequence("save")
        self.assertNotIn("compact", self.events)

    def test_failed_compact_cannot_resume(self):
        self.failed_sequence("compact")
        self.assertEqual(self.events.count("compact"), 1)

    def test_busy_due_coalesces_and_finishes_without_maintenance_abort(self):
        self.active()
        self.connection.update(isStreaming=True, contextUsage={"percent": 51})
        with StubPrime(self.handler) as stub, PrimeClient(stub.path) as client:
            first = check_compaction(client, self.stream, self.identity, sessions_dir=self.native)
            self.connection["contextUsage"]["percent"] = 52
            second = check_compaction(client, self.stream, self.identity, sessions_dir=self.native)
            self.connection["isStreaming"] = False
            third = check_compaction(client, self.stream, self.identity, sessions_dir=self.native)
        self.assertEqual(first["status"], "deferred")
        self.assertEqual(first["command"], second["command"])
        self.assertEqual(third["status"], "verified")
        self.assertNotIn("abort", self.events)

    def test_new_human_input_has_priority_and_is_held_during_compaction(self):
        held = []
        with StubPrime(self.handler) as stub, PrimeClient(stub.path) as client:
            self.prepare(client)
            self.on_compact = lambda: held.append(send_stream_message(client, self.stream, self.identity, body="New whole human priority", command_id=str(uuid4()), sender="operator", lane="steer", sessions_dir=self.native))
            result = check_compaction(client, self.stream, self.identity, sessions_dir=self.native)
        self.assertEqual(result["status"], "verified")
        self.assertEqual(held[0]["sending_status"], "not sent")
        prompts = [r["command"] for r in stub.requests if r["command"]["type"] == "prompt_and_wait"]
        self.assertIn('"New whole human priority"', prompts[-1]["message"])
        self.assertNotIn("Compaction saved native entry", prompts[-1]["message"])
        self.assertEqual(prompts[-1]["streamingBehavior"], "followUp")

    def test_stop_supersedes_dcr_after_checked_save(self):
        def stop():
            current = state.check_state(self.stream)
            state.update_state(self.stream, expect=current.sha256, goals=replace(current.goals, status="paused"), rules=None,
                               entry={"subject": "Operator stop", "body": {}, "original_entries": []})
        self.after_dump = stop
        with StubPrime(self.handler) as stub, PrimeClient(stub.path) as client:
            self.prepare(client)
            result = check_compaction(client, self.stream, self.identity, sessions_dir=self.native)
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(state.check_state(self.stream).goals.status, "paused")
        self.assertNotIn("compact", self.events)

    def test_busy_after_pause_defers_and_releases_without_compact(self):
        self.after_pause = lambda: self.connection.update(isStreaming=True)
        with StubPrime(self.handler) as stub, PrimeClient(stub.path) as client:
            self.prepare(client)
            result = check_compaction(client, self.stream, self.identity, sessions_dir=self.native)
        self.assertEqual(result["status"], "deferred")
        self.assertNotIn("compact", self.events)
        self.assertIn("release_session_input_pause", self.events)

    def test_identical_explicit_request_cannot_compact_twice(self):
        command = str(uuid4())
        with StubPrime(self.handler) as stub, PrimeClient(stub.path) as client:
            self.prepare(client)
            first = run_compaction(client, self.stream, self.identity, trigger="explicit", sessions_dir=self.native, command_id=command)
            second = run_compaction(client, self.stream, self.identity, trigger="explicit", sessions_dir=self.native, command_id=command)
        self.assertEqual(first["status"], "verified")
        self.assertEqual(second["status"], "complete")
        self.assertEqual(self.events.count("compact"), 1)

    def test_readback_rejects_off_branch_ambiguous_and_wrong_summary(self):
        native = {"id": "compact-one", "parentId": "leaf-one", "type": "compaction", "summary": self.summary}
        self.transcript.write_text("\n".join(json.dumps(row) for row in [{"type": "session", "id": "durable"}, *self.nodes, native]) + "\n")
        tree = {"flatNodes": [{"entry": row} for row in [*self.nodes, native]], "leafId": "compact-one"}
        valid = read_compaction_entry(tree, set(), {"summary": self.summary}, self.transcript, self.native, self.identity)
        self.assertEqual(valid["id"], "compact-one")
        from engine import StreamsError
        for broken, result in (({**tree, "leafId": "leaf-one"}, {"summary": self.summary}), (tree, {"summary": "wrong"})):
            with self.assertRaises(StreamsError):
                read_compaction_entry(broken, set(), result, self.transcript, self.native, self.identity)
        second = {"id": "compact-two", "parentId": "compact-one", "type": "compaction", "summary": self.summary}
        with self.assertRaises(StreamsError):
            read_compaction_entry({"flatNodes": tree["flatNodes"] + [{"entry": second}], "leafId": "compact-two"}, set(), {"summary": self.summary}, self.transcript, self.native, self.identity)

    def test_unknown_compact_timeout_releases_without_resume_or_retry(self):
        def handler(stub, request):
            if request["command"]["type"] == "compact":
                self.events.append("compact")
                return None
            return self.handler(stub, request)
        with StubPrime(handler) as stub, PrimeClient(stub.path, timeout=.05) as client:
            self.prepare(client)
            first = check_compaction(client, self.stream, self.identity, sessions_dir=self.native)
            second = check_compaction(client, self.stream, self.identity, sessions_dir=self.native)
        self.assertEqual(first["status"], "unknown")
        self.assertEqual(second["status"], "held")
        self.assertEqual(self.events.count("compact"), 1)
        self.assertEqual(self.events.count("prompt_and_wait"), 1)
        self.assertIn("release_session_input_pause", self.events)

    def test_native_transcript_traversal_is_not_an_owned_disk_readback(self):
        from engine import StreamsError
        entry = {"id": "compact-escape", "parentId": None, "type": "compaction", "summary": self.summary}
        outside = self.root / "outside-native.jsonl"
        outside.write_text(json.dumps({"type": "session", "id": "durable"}) + "\n" + json.dumps(entry) + "\n")
        tree = {"flatNodes": [{"entry": entry}], "leafId": entry["id"]}
        with self.assertRaisesRegex(StreamsError, "traversal|outside|escape"):
            read_compaction_entry(tree, set(), {"summary": self.summary}, self.native / "../outside-native.jsonl", self.native, self.identity)
        self.assertEqual(outside.read_text().count("compact-escape"), 1)

    def test_settings_are_idempotent_and_conflicts_do_not_reconfigure(self):
        path = project.write_prime_settings(self.stream, 50)
        before = path.read_bytes()
        with self.assertRaises(Exception):
            project.write_prime_settings(self.stream, 20)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(json.loads(before)["compaction"], {"enabled": False, "agentCallable": False, "thresholdPercent": 50})
