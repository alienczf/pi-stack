"""Z15 state is new functionality; creation and worktree locks extend existing paths."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import StreamsError, project, state as z15


class ExistingPathTests(unittest.TestCase):
    def test_prime_creation_preserves_current_work_on_repeated_create(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index = root / "index"
            index.mkdir()
            info = project.ProjectSection("product", str(root), "", "", "")
            settings = project.ModelSettings("openai-codex/gpt-6.1-sol", "xhigh")
            config = project.Project(info, settings, settings, project.Caps(), [])
            stream = project.create_stream(index, config, "one", backend="prime")
            text = (stream / "STATE.md").read_text()
            self.assertIn("### Current objective\nText: null\nStatus: unset", text)
            current = text.replace('Text: ""', 'Text: "Keep the whole request"', 1)
            (stream / "STATE.md").write_text(current)
            project.create_stream(index, config, "one", backend="prime")
            self.assertEqual((stream / "STATE.md").read_text(), current)

    def test_prime_creation_rejects_symlink_destination_ancestors_and_registered_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            foreign = Path(tmp) / "foreign"
            foreign.mkdir()
            index = Path(tmp) / "index"
            index.mkdir()
            info = project.ProjectSection("product", str(root), "", "", "")
            settings = project.ModelSettings("openai-codex/gpt-6.1-sol", "xhigh")
            config = project.Project(info, settings, settings, project.Caps(), [])
            streams = root / "streams"
            streams.mkdir()
            (streams / "escape").symlink_to(foreign, target_is_directory=True)
            with self.assertRaisesRegex(StreamsError, "symlink|escape"):
                project.create_stream(index, config, "escape", backend="prime")
            self.assertEqual(list(foreign.iterdir()), [])
            (streams / "escape").unlink()
            streams.rmdir()
            streams.symlink_to(foreign, target_is_directory=True)
            with self.assertRaisesRegex(StreamsError, "symlink|escape"):
                project.create_stream(index, config, "escape", backend="prime")
            self.assertEqual(list(foreign.iterdir()), [])
            streams.unlink()
            project.upsert_stream_row(index, project.StreamRow("escape", str(foreign), "product"))
            with self.assertRaisesRegex(StreamsError, "escape"):
                project.create_stream(index, config, "escape", backend="prime")
            self.assertEqual(list(foreign.iterdir()), [])

    def test_prime_upgrade_preserves_current_work_history_and_custom_role(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index = root / "index"
            index.mkdir()
            info = project.ProjectSection("product", str(root), "", "", "")
            settings = project.ModelSettings("openai-codex/gpt-6.1-sol", "xhigh")
            config = project.Project(info, settings, settings, project.Caps(), [])
            stream = project.create_stream(index, config, "one", backend="prime")
            project.git(stream, "config", "user.name", "Test")
            project.git(stream, "config", "user.email", "test@example.com")
            z15.save_message(stream, text="Keep this current work", command_id=str(UUID(int=1)), session_id="durable", sender="operator", send_as="followUp")
            before = z15.check_state(stream).text
            role = "Custom authorized role\n"
            (stream / "AGENTS.md").write_text(role)
            saved = project.load_stream_config(stream / "stream.toml")
            saved.pi_stack_revision = "0" * 40
            project.save_stream_config(stream, saved)
            project.upgrade_stream(stream, "one")
            self.assertEqual(z15.check_state(stream).text, before)
            self.assertEqual((stream / "AGENTS.md").read_text(), role)
            self.assertEqual(project.load_stream_config(stream / "stream.toml").backend, "prime")
            self.assertFalse((stream / "STREAM.md").exists())

    def test_linked_worktree_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            repo.mkdir()
            project.git(repo, "init")
            project.git(repo, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "--allow-empty", "-m", "init")
            linked = root / "linked"
            project.git(repo, "worktree", "add", "-b", "linked", str(linked))
            with project.stream_lock(linked):
                self.assertEqual((linked / ".git").is_file(), True)
            with project.stream_locks([linked]):
                self.assertTrue((repo / ".git" / "worktrees" / "linked" / "pi-streams.lock").is_file())


class NewStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.stream = Path(self.tmp.name)
        project.git(self.stream, "init")
        project.copy_missing(project.templates_dir() / "prime", self.stream)

    def save(self, number=1, text="Implement A and verify B.\nKeep C unchanged.", **kwargs):
        return z15.save_message(self.stream, text=text, command_id=str(UUID(int=number)), session_id="durable-session", sender="operator", send_as="steer", **kwargs)

    def current(self):
        return z15.check_state(self.stream)

    def update(self, *, goals=None, rules=None, refs=None, body=None, expect=None):
        return z15.update_state(self.stream, expect=expect or self.current().sha256, goals=goals, rules=rules, entry={"subject": "Checked update", "body": body or {"findings": "Work remains requested."}, "original_entries": refs or []})

    def test_unicode_fences_and_exact_original_round_trip(self):
        original = '日本語 café e\u0301 🥔\r\n## Rules\n```json\n{"text":"not a template {body}"}\n```\n~~~\n### false heading\n~~~\u2028end\n'
        saved = self.save(text=original)
        state = self.current()
        self.assertEqual(z15.render_state(z15.parse_state(state.text)), state.text)
        entry = z15.read_entry(self.stream, saved["entry"])
        body = json.loads(entry.split("```json\n", 1)[1].rsplit("\n```", 1)[0])
        self.assertEqual(body["text"].encode(), original.encode())
        self.assertEqual(body["sha256"], hashlib.sha256(original.encode()).hexdigest())
        self.assertEqual(state.goals.work[0].required, None)
        self.assertEqual(state.goals.work[0].original_entry, saved["entry"])
        tilde = state.text.replace("```json\n", "~~~~json\n").replace("\n```\n", "\n~~~~\n")
        self.assertEqual(z15.parse_state(tilde).log[0].body["text"], original)

    def test_exact_sections_and_malformed_json_rejected(self):
        self.save()
        text = self.current().text
        for broken in (text + "\n## Extra\n", text.replace("## Rules", "## Goals"), text.replace('"sender": "operator"', '"sender": "operator", "sender": "forged"'), text.replace('"sender": "operator"', '"sender": NaN'), text.replace("Status: unset", "Status: done"), text.replace("\n", "\r\n"), text + "\n"):
            with self.subTest(broken=broken[-70:]):
                with self.assertRaises(StreamsError):
                    z15.parse_state(broken)
        self.assertEqual(self.current().goals.status, "unset")

    def test_plan_update_preserves_whole_sources_and_unrelated_rulings(self):
        original = self.save()["entry"]
        second = self.save(2, "Never change the compatibility path.")["entry"]
        self.update(rules=[z15.Rule("Keep compatibility", second, "stream")], refs=[second])
        before = z15.read_entry(self.stream, original)
        goals = replace(self.current().goals, objective="Implement A", status="active", work=tuple(replace(work, required="A, B and unchanged C") if work.original_entry == original else work for work in self.current().goals.work))
        self.update(goals=goals, refs=[original])
        self.assertEqual(z15.read_entry(self.stream, original), before)
        self.assertEqual(self.current().rules, (z15.Rule("Keep compatibility", second, "stream"),))
        self.assertEqual(len(self.current().goals.work), 2)

    def test_json_update_shape_preserves_worker_wait_and_source(self):
        original = self.save()["entry"]
        self.update(goals={
            "north_star": {"text": "Deliver the product", "original_entry": original},
            "current_objective": {"text": "Wait for the existing worker", "status": "waiting"},
            "work": [{"summary": "Whole request", "original_entry": original,
                      "required": "A, B and unchanged C", "workers": [{"session": "worker-1", "worktree": "/assigned/product", "work": "A"}],
                      "next": None, "waiting_for": "worker-1 result"}],
        }, refs=[original])
        state = self.current()
        self.assertEqual(state.goals.north_star, "Deliver the product")
        self.assertEqual(state.goals.status, "waiting")
        self.assertEqual(state.goals.work[0].workers, ({"session": "worker-1", "worktree": "/assigned/product", "work": "A"},))
        self.assertEqual(state.goals.work[0].waiting_for, "worker-1 result")
        self.assertEqual(state.goals.work[0].original_entry, original)

    def test_partial_message_answer_and_claimed_green_cannot_remove_whole_request(self):
        original = self.save()["entry"]
        state = self.current()
        with self.assertRaisesRegex(StreamsError, "whole original message"):
            self.update(goals=replace(state.goals, work=()), refs=[original], body={
                "original_entries": [original], "later_instruction_entries": [],
                "target": "/assigned/product", "invocation": {"argv": ["true"], "cwd": "/assigned/product"},
                "result": {"status": "complete", "exit": 0}, "findings": "Implemented only A.",
                "proof_entries": [], "review": None,
            })
        self.assertEqual(self.current().sha256, state.sha256)
        self.assertEqual(z15.read_entry(self.stream, original), state.log[0].text)

    def test_rule_retirement_requires_later_human_source_and_archives_exact_rule(self):
        first = self.save(received_at="2026-10-23T10:00:00Z")["entry"]
        rule = z15.Rule("Keep C unchanged", first, "product C")
        other = z15.Rule("Verify B", first, "product B")
        self.update(rules=[rule, other], refs=[first])
        before = self.current()
        with self.assertRaisesRegex(StreamsError, "later trusted human"):
            self.update(rules=[other], refs=[first])
        self.assertEqual(self.current().sha256, before.sha256)
        later = self.save(2, "Retire only the C ruling.", received_at="2026-10-23T10:01:00Z")["entry"]
        result = self.update(rules=[other], refs=[first, later])
        self.assertEqual(self.current().rules, (other,))
        self.assertEqual(len(result["history_files"]), 1)
        retired = z15.read_entry(self.stream, result["history_files"][0])
        self.assertIn("-rule-retired-", result["history_files"][0])
        proof = z15._parse_entry(retired).body
        self.assertEqual(proof["text"], '- Keep C unchanged\n  Original entry: ' + json.dumps(first) + '\n  Applies to: "product C"\n')
        self.assertEqual(proof["sha256"], hashlib.sha256(proof["text"].encode()).hexdigest())
        self.assertEqual(len(self.current().goals.work), 2)

    def test_later_explicit_cancel_or_information_keeps_linked_original(self):
        for status in ("cancelled", "informational"):
            with self.subTest(status=status):
                number = 10 if status == "cancelled" else 20
                original = self.save(number, "Old whole request", received_at="2026-10-23T09:00:00Z")["entry"]
                later = self.save(number + 1, "Cancel that request." if status == "cancelled" else "That was information only.", received_at="2026-10-23T09:01:00Z")["entry"]
                before = z15.read_entry(self.stream, original)
                body = {"later_instruction_entries": [later], "target": None, "invocation": None, "result": {"status": status}, "findings": "Operator accounted for the whole earlier message.", "proof_entries": [], "review": None}
                goals = replace(self.current().goals, work=tuple(work for work in self.current().goals.work if work.original_entry != original))
                self.update(goals=goals, refs=[original, later], body=body)
                self.assertEqual(z15.read_entry(self.stream, original), before)
                self.assertIn(later, {work.original_entry for work in self.current().goals.work})
                self.assertNotIn(original, {work.original_entry for work in self.current().goals.work})

    def test_cancel_without_later_human_instruction_is_not_accounted(self):
        original = self.save()["entry"]
        body = {"later_instruction_entries": [], "target": None, "invocation": None, "result": {"status": "cancelled"}, "findings": "Model cancelled work to shorten the plan", "proof_entries": [], "review": None}
        before = self.current()
        with self.assertRaisesRegex(StreamsError, "whole original message"):
            self.update(goals=replace(before.goals, work=()), refs=[original], body=body)
        self.assertEqual(self.current().sha256, before.sha256)

    def test_model_sender_claim_cannot_create_rule(self):
        source = z15.save_message(self.stream, text="A ruling", command_id=str(UUID(int=1)), session_id="durable-session", sender=None, send_as="followUp")["entry"]
        before = self.current()
        with self.assertRaisesRegex(StreamsError, "trusted human source"):
            self.update(rules=[z15.Rule("Claimed authority", source, "stream")], refs=[source], body={"sender": "operator"})
        self.assertEqual(self.current().sha256, before.sha256)

    def test_31_unrelated_entries_rotate_only_log_and_keep_original(self):
        original = self.save()["entry"]
        exact = z15.read_entry(self.stream, original)
        goals_text = self.current().goals_text
        for number in range(31):
            z15.append_log(self.stream, subject=f"Finding {number}", body={"finding": number})
        state = self.current()
        self.assertEqual(len(state.log), 30)
        self.assertEqual(state.log[0].body, {"finding": 1})
        self.assertEqual(state.goals_text, goals_text)
        self.assertEqual(z15.read_entry(self.stream, original), exact)
        self.assertEqual((self.stream / "history" / original).read_text(), exact)
        self.assertEqual(len(list((self.stream / "history").iterdir())), 2)
        z15.rotate_log(self.stream)
        self.assertEqual(self.current().sha256, state.sha256)

    def test_no_goal_or_rule_count_retention_limit(self):
        refs = [self.save(n + 1, f"Whole original {n}")["entry"] for n in range(31)]
        rules = [z15.Rule(f"Ruling {n}", ref, "stream") for n, ref in enumerate(refs)]
        self.update(rules=rules, refs=refs)
        self.assertEqual(len(self.current().goals.work), 31)
        self.assertEqual(len(self.current().rules), 31)
        self.assertEqual(len(self.current().log), 30)
        self.assertIn('"text": "Whole original 0"', z15.read_entry(self.stream, refs[0]))

    def test_command_reuse_is_idempotent_after_rotation_but_changed_binding_conflicts(self):
        saved = self.save()
        for number in range(31):
            z15.append_log(self.stream, subject="Unrelated", body={"number": number})
        before = self.current()
        again = self.save(received_at="2026-10-23T11:00:00Z")
        self.assertEqual(again["entry"], saved["entry"])
        self.assertEqual(again["state_sha256"], before.sha256)
        for change in ({"text": "Different bytes"}, {"session_id": "other-session"}, {"send_as": "followUp"}, {"sender": "other-operator"}):
            kwargs = {"text": "Implement A and verify B.\nKeep C unchanged.", "command_id": str(UUID(int=1)), "session_id": "durable-session", "sender": "operator", "send_as": "steer"}
            kwargs.update(change)
            with self.assertRaisesRegex(StreamsError, "UUID conflicts"):
                z15.save_message(self.stream, **kwargs)
        distinct = self.save(2)
        self.assertNotEqual(distinct["entry"], saved["entry"])
        self.assertEqual(len(self.current().goals.work), 2)

    def test_duplicate_log_command_same_bytes_reuses_first_name(self):
        command = str(UUID(int=8))
        first = z15.append_log(self.stream, subject="Native reply", body={"success": False, "error": "Observed failure"}, command_id=command, purpose="reply")
        again = z15.append_log(self.stream, subject="Native reply", body={"success": False, "error": "Observed failure"}, command_id=command, purpose="reply")
        self.assertEqual(again["entry"], first["entry"])
        self.assertEqual(len(self.current().log), 1)
        with self.assertRaisesRegex(StreamsError, "conflicts"):
            z15.append_log(self.stream, subject="Native reply", body={"success": True}, command_id=command, purpose="reply")
        self.assertEqual(self.current().log[0].body["error"], "Observed failure")

    def test_stale_write_refused_and_log_only_change_does_not_stale_current_text(self):
        self.save()
        before = self.current()
        z15.append_log(self.stream, subject="Only Log", body={"result": "waiting"})
        after = self.current()
        with self.assertRaisesRegex(StreamsError, "stale STATE"):
            self.update(expect=before.sha256)
        self.assertEqual(z15.check_current_text(self.stream, before.goals_rules_sha256).sha256, after.sha256)
        self.save(2, "New instruction")
        with self.assertRaisesRegex(StreamsError, "stale Goals/Rules"):
            z15.check_current_text(self.stream, before.goals_rules_sha256)
        self.assertEqual(len(self.current().goals.work), 2)

    def test_concurrent_writers_preserve_all_whole_messages(self):
        with ThreadPoolExecutor(max_workers=6) as pool:
            saved = list(pool.map(lambda n: self.save(n, f"Request {n}"), range(1, 13)))
        state = self.current()
        self.assertEqual(len(state.goals.work), 12)
        self.assertEqual({entry.body["text"] for entry in state.log}, {f"Request {n}" for n in range(1, 13)})
        self.assertEqual({item["entry"] for item in saved}, {work.original_entry for work in state.goals.work})

    def test_concurrent_expected_hash_writers_allow_exactly_one_update(self):
        self.save()
        expected = self.current().sha256
        def change(n):
            try:
                return self.update(expect=expected, body={"number": n})["success"]
            except StreamsError:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            result = list(pool.map(change, [1, 2]))
        self.assertEqual(sorted(result), [False, True])
        self.assertEqual(len(self.current().log), 2)

    def test_already_locked_writer_does_not_relock(self):
        with project.stream_lock(self.stream):
            with patch.object(z15, "stream_lock", side_effect=AssertionError("nested flock")):
                saved = self.save(locked=True)
                z15.append_log(self.stream, subject="Locked note", body={"result": "saved"}, locked=True)
        self.assertEqual(self.current().goals.work[0].original_entry, saved["entry"])
        self.assertEqual(self.current().log[-1].body, {"result": "saved"})

    def fill_log(self):
        self.save()
        for number in range(29):
            z15.append_log(self.stream, subject="Finding", body={"number": number})
        self.assertEqual(len(self.current().log), 30)

    def test_history_failure_never_prunes_state(self):
        self.fill_log()
        before = self.current()
        original = before.log[0]
        publish = z15._publish
        def fail_history(path, text, **kwargs):
            if path.parent.name == "history":
                raise StreamsError("history unavailable")
            return publish(path, text, **kwargs)
        with patch.object(z15, "_publish", side_effect=fail_history):
            with self.assertRaisesRegex(StreamsError, "history unavailable"):
                z15.append_log(self.stream, subject="31st", body={"number": 30})
        self.assertEqual(self.current().text, before.text)
        self.assertEqual(z15.read_entry(self.stream, original.file), original.text)

    def test_real_history_io_error_does_not_prune_and_can_be_retried(self):
        self.fill_log()
        before = self.current()
        with patch.object(z15.os, "link", side_effect=OSError("history disk full")):
            with self.assertRaisesRegex(StreamsError, "not published.*history disk full"):
                z15.append_log(self.stream, subject="31st", body={"number": 30})
        self.assertEqual(self.current().sha256, before.sha256)
        z15.append_log(self.stream, subject="31st", body={"number": 30})
        self.assertEqual(z15.read_entry(self.stream, before.log[0].file), before.log[0].text)
        self.assertEqual(self.current().log[-1].body, {"number": 30})

    def test_state_tempfile_failure_and_cancellation_leave_no_save_claim(self):
        before = self.current()
        with patch.object(z15.tempfile, "mkstemp", side_effect=OSError("no space")):
            with self.assertRaisesRegex(StreamsError, "not published.*no space"):
                self.save()
        self.assertEqual(self.current().sha256, before.sha256)
        with patch.object(z15, "_publish", side_effect=KeyboardInterrupt()):
            with self.assertRaises(KeyboardInterrupt):
                self.save()
        self.assertEqual(self.current().sha256, before.sha256)
        saved = self.save()
        self.assertEqual(self.current().goals.work[0].original_entry, saved["entry"])

    def test_history_first_partial_publication_is_safe_to_retry(self):
        self.fill_log()
        before = self.current()
        original = before.log[0]
        publish = z15._publish
        def fail_state(path, text, **kwargs):
            if path.name == "STATE.md":
                self.assertEqual((self.stream / "history" / original.file).read_text(), original.text)
                raise StreamsError("state unavailable")
            return publish(path, text, **kwargs)
        with patch.object(z15, "_publish", side_effect=fail_state):
            with self.assertRaisesRegex(StreamsError, "state unavailable"):
                z15.append_log(self.stream, subject="31st", body={"number": 30})
        self.assertEqual(self.current().sha256, before.sha256)
        result = z15.append_log(self.stream, subject="31st", body={"number": 30})
        self.assertEqual(result["history_files"], [original.file])
        self.assertEqual(len(self.current().log), 30)
        self.assertEqual(z15.read_entry(self.stream, original.file), original.text)

    def test_unequal_history_bytes_and_source_tampering_fail_without_overwrite(self):
        self.fill_log()
        before = self.current()
        original = before.log[0]
        history = self.stream / "history"
        history.mkdir()
        conflict = original.text.replace("Original message", "Altered message", 1)
        (history / original.file).write_text(conflict)
        with self.assertRaisesRegex(StreamsError, "unequal existing history"):
            z15.append_log(self.stream, subject="31st", body={"number": 30})
        self.assertEqual((self.stream / "STATE.md").read_text(), before.text)
        self.assertEqual((history / original.file).read_text(), conflict)
        (history / original.file).unlink()
        (self.stream / "STATE.md").write_text(before.text.replace("Implement A and verify B.", "Changed original"))
        with self.assertRaisesRegex(StreamsError, "original message identity/hash/lane"):
            self.current()

    def test_post_replace_sync_error_is_unknown_not_rollback(self):
        before = self.current()
        with patch.object(z15, "_sync_dir", side_effect=OSError("sync failed")):
            with self.assertRaisesRegex(StreamsError, "unknown after publication"):
                self.save()
        after = self.current()
        self.assertNotEqual(after.sha256, before.sha256)
        self.assertEqual(len(after.goals.work), 1)

    def test_traversal_symlink_and_duplicate_ids_refused(self):
        saved = self.save()
        state = self.current()
        with self.assertRaisesRegex(StreamsError, "basename"):
            z15.read_entry(self.stream, "../STATE.md")
        history = self.stream / "history"
        history.symlink_to(self.stream, target_is_directory=True)
        with self.assertRaisesRegex(StreamsError, "symlink"):
            z15.read_entry(self.stream, saved["entry"])
        history.unlink()
        duplicate = state.log[0].text.replace(saved["entry"][:23], "20261023T100000.000000Z")
        with self.assertRaisesRegex(StreamsError, "duplicate command/purpose"):
            (self.stream / "STATE.md").write_text(state.text + "\n" + duplicate)
            self.current()
        (self.stream / "STATE.md").write_text(state.text)
        self.assertEqual(self.current().sha256, state.sha256)

    def test_rotate_repair_archives_overflow_before_pruning(self):
        self.save()
        before = self.current()
        extras = tuple(z15._entry(f"Finding {n}", {"number": n}) for n in range(31))
        overflow = replace(before, log=before.log + extras)
        (self.stream / "STATE.md").write_text(z15.render_state(overflow))
        with self.assertRaisesRegex(StreamsError, "exceeds 30"):
            self.current()
        result = z15.rotate_log(self.stream)
        self.assertEqual(len(self.current().log), 30)
        self.assertEqual(len(result["history_files"]), 2)
        self.assertEqual(z15.read_entry(self.stream, before.log[0].file), before.log[0].text)
        self.assertEqual(self.current().goals, before.goals)

    def test_rule_history_failure_preserves_current_ruling(self):
        original = self.save(received_at="2026-10-23T10:00:00Z")["entry"]
        rule = z15.Rule("Keep C", original, "product C")
        self.update(rules=[rule], refs=[original])
        later = self.save(2, "Retire C", received_at="2026-10-23T10:01:00Z")["entry"]
        before = self.current()
        with patch.object(z15, "_archive", side_effect=StreamsError("history failure")):
            with self.assertRaisesRegex(StreamsError, "history failure"):
                self.update(rules=[], refs=[original, later])
        self.assertEqual(self.current().sha256, before.sha256)
        self.assertEqual(self.current().rules, (rule,))

    def test_malformed_known_entry_and_nonfinite_data_refused_before_write(self):
        before = self.current()
        for body in ({"media_type": "text/plain", "text": "missing hash"}, {"sent_text_sha256": "0" * 64}, {"value": float("inf")}, {"text": "human", "received_at": "2026-10-23T10:00:00Z"}):
            with self.subTest(body=body):
                with self.assertRaises(StreamsError):
                    z15.append_log(self.stream, subject="Invalid", body=body)
        self.assertEqual(self.current().sha256, before.sha256)
        result = z15.append_log(self.stream, subject="Valid proof", body={"media_type": "text/plain", "original_entries": [], "text": "exact proof", "sha256": hashlib.sha256(b"exact proof").hexdigest()})
        self.assertIn('"text": "exact proof"', z15.read_entry(self.stream, result["entry"]))

    def test_state_writer_rejects_symlink_ancestor(self):
        child = self.stream / "actual-stream"
        child.mkdir()
        project.git(child, "init")
        project.copy_missing(project.templates_dir() / "prime", child)
        alias = self.stream / "alias"
        alias.symlink_to(self.stream, target_is_directory=True)
        before = (child / "STATE.md").read_bytes()
        with self.assertRaisesRegex(StreamsError, "symlink"):
            z15.save_message(alias / "actual-stream", text="must not escape", command_id=str(UUID(int=3)), session_id="durable", sender="operator", send_as="steer")
        self.assertEqual((child / "STATE.md").read_bytes(), before)

    def test_missing_agents_blocks_write(self):
        before = self.current()
        (self.stream / "AGENTS.md").unlink()
        with self.assertRaisesRegex(StreamsError, "could not read AGENTS"):
            self.save()
        self.assertEqual((self.stream / "STATE.md").read_text(), before.text)


if __name__ == "__main__":
    unittest.main()
