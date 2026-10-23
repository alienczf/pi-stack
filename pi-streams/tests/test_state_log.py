"""Canonical Log occurrences, durable rotation, and explicit ruling mutations."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock

from support import git
from tick_support import TickCase
from test_state_artifacts import STATE

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine import StreamsError, artifacts, project, tick

PREFIX = STATE.split(b"## Log\n", 1)[0] + b"## Log\n"
AT = "2026-10-23T05:00:00.000000Z"
OLD_RULE = "Freeze β until the human rules otherwise.\n"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def seed(stream: Path, count: int, **tick_fields) -> list[bytes]:
    entries = []
    records = []
    offset = 0
    for number in range(1, count + 1):
        data = f"### {AT} Work {number}\nResult {number}.\n".encode()
        entries.append(data)
        records.append({"occurrence": number, "start": offset, "end": offset + len(data),
                        "sha256": digest(data), "timestamp": AT, "subject": f"Work {number}"})
        offset += len(data)
    (stream / "STATE.md").write_bytes(PREFIX + b"".join(entries))
    (stream / "log").mkdir(exist_ok=True)
    metadata = {**tick_fields, "state_log": {"version": 1, "next_occurrence": count + 1,
                "entries": records, "receipts": {}, "pending_history": []}}
    (stream / "log/tick-state.json").write_text(json.dumps(metadata), encoding="utf-8")
    return entries


class LogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stream = Path(tempfile.mkdtemp(prefix="pi-streams-log-"))
        self.addCleanup(lambda: shutil.rmtree(self.stream))
        (self.stream / ".git").mkdir()
        (self.stream / "stream.toml").write_text('project = "private"\npi_stack_revision = "abc"\nstate_schema = 1\n')
        (self.stream / "STATE.md").write_bytes(PREFIX)
        self.metadata_path = self.stream / "log/tick-state.json"

    def metadata(self):
        return json.loads(self.metadata_path.read_text())

    def log(self):
        return (self.stream / "STATE.md").read_bytes().split(b"## Log\n", 1)[1]

    def append(self, body="Result.", request="one", at=AT, subject="Work"):
        return artifacts.append_log(self.stream, at, subject, body, request_id=request)

    def test_tick_state_roundtrip_does_not_discard_log_metadata(self) -> None:
        seed(self.stream, 1, pending=[], outages=["parked"], future={"keep": 7})
        before = self.metadata()
        state = tick.load_state(self.metadata_path)
        tick.save_state(self.metadata_path, state)
        self.assertEqual(self.metadata()["state_log"], before["state_log"])
        self.assertEqual(self.metadata()["future"], {"keep": 7})
        self.assertEqual(self.metadata()["outages"], ["parked"])

    def test_identical_bodies_are_distinct_occurrences_but_request_retry_is_not(self) -> None:
        self.assertEqual(self.append(request="a"), 1)
        self.assertEqual(self.append(request="b"), 2)
        self.assertEqual(self.append(request="a", at="2026-10-23T09:00:00Z"), 1)
        expected = f"### {AT} Work\nResult.\n".encode()
        self.assertEqual(self.log(), expected * 2)
        self.assertEqual([entry["occurrence"] for entry in self.metadata()["state_log"]["entries"]], [1, 2])
        with self.assertRaises(StreamsError):
            self.append(body="Changed intent", request="a")
        self.assertEqual(self.log(), expected * 2)

    def test_free_body_delimiters_and_long_unicode_are_one_accepted_entry(self) -> None:
        body = "### 2099-01-01T00:00:00Z Fake entry\n## Rules\n```\n" + "東京" * 20000
        self.assertEqual(self.append(body=body), 1)
        expected = f"### {AT} Work\n{body}\n".encode()
        self.assertEqual(self.log(), expected)
        self.assertEqual(len(self.metadata()["state_log"]["entries"]), 1)
        self.assertIs(artifacts.update_current_objective(self.stream, "Next β"), True)
        self.assertEqual(self.log(), expected)
        for number in range(30):
            self.append(request=f"later-{number}")
        artifacts.rotate_log(self.stream)
        self.assertEqual(len(self.metadata()["state_log"]["entries"]), 30)
        self.assertEqual([path.read_bytes() for path in (self.stream / "history").glob("*.md")], [expected])

    def test_rotation_counts_and_exact_archives(self) -> None:
        for count in (0, 29, 30, 31, 75):
            with self.subTest(count=count):
                if (self.stream / "history").exists():
                    shutil.rmtree(self.stream / "history")
                entries = seed(self.stream, count, pending=[{"keep": "pending"}], outages=["parked"], extra="keep")
                artifacts.rotate_log(self.stream)
                self.assertEqual((self.stream / "STATE.md").read_bytes(), PREFIX + b"".join(entries[-30:]))
                history = sorted((self.stream / "history").glob("*.md"))
                self.assertEqual([path.read_bytes() for path in history], entries[:max(0, count - 30)])
                before = {path.name: path.read_bytes() for path in history}
                artifacts.rotate_log(self.stream)
                self.assertEqual({path.name: path.read_bytes() for path in (self.stream / "history").glob("*.md")}, before)
                self.assertEqual(self.metadata()["pending"], [{"keep": "pending"}])
                self.assertEqual(self.metadata()["outages"], ["parked"])
                self.assertEqual(self.metadata()["extra"], "keep")

    def test_objective_edits_do_not_invalidate_log_relative_offsets(self) -> None:
        entries = seed(self.stream, 31)
        before = self.metadata()["state_log"]["entries"]
        artifacts.update_current_objective(self.stream, "A much longer current objective with 原本.\nKeep this second line.")
        self.assertEqual(self.metadata()["state_log"]["entries"], before)
        prefix = (self.stream / "STATE.md").read_bytes().split(b"## Log\n", 1)[0] + b"## Log\n"
        artifacts.rotate_log(self.stream)
        self.assertEqual((self.stream / "STATE.md").read_bytes(), prefix + b"".join(entries[1:]))

    def test_non_utc_entry_uses_stable_utc_history_name(self) -> None:
        self.append(at="2026-10-23T13:00:00+08:00")
        entry = f"### {AT} Work\nResult.\n".encode()
        for number in range(30):
            self.append(request=f"next-{number}")
        artifacts.rotate_log(self.stream)
        history = list((self.stream / "history").glob("*.md"))
        self.assertEqual([path.name for path in history], [f"20261023T050000000000Z-entry-00000001-work-{digest(entry)[:16]}.md"])
        self.assertEqual(history[0].read_bytes(), entry)

    def test_history_listing_carries_distinguishable_safe_subject_slugs(self) -> None:
        self.append(subject="../Build frontend / 東京", request="frontend")
        self.append(subject="Verify backend β", request="backend")
        for number in range(30):
            self.append(request=f"slug-tail-{number}")
        artifacts.rotate_log(self.stream)
        paths = list((self.stream / "history").glob("*.md"))
        names = [path.name for path in paths]
        self.assertEqual(len(names), 2)
        self.assertTrue(any("-build-frontend-東京-" in name for name in names), names)
        self.assertTrue(any("-verify-backend-β-" in name for name in names), names)
        self.assertTrue(all(".." not in name for name in names))
        self.assertEqual({path.read_bytes().split(b"\n", 1)[0] for path in paths}, {
            f"### {AT} ../Build frontend / 東京".encode(), f"### {AT} Verify backend β".encode(),
        })

    def test_long_subject_is_preserved_while_the_filename_fits_its_component(self) -> None:
        subject = "東京" * 200
        self.append(subject=subject)
        expected = f"### {AT} {subject}\nResult.\n".encode()
        for number in range(30):
            self.append(request=f"long-subject-tail-{number}")
        artifacts.rotate_log(self.stream)
        paths = list((self.stream / "history").glob("*.md"))
        self.assertEqual(len(paths), 1)
        self.assertLessEqual(len(paths[0].name.encode()), 255)
        self.assertIn("東京", paths[0].name)
        self.assertEqual(paths[0].read_bytes(), expected)
        self.assertEqual(len(list((self.stream / "history").iterdir())), 1)

    def test_append_recovers_before_and_after_state_publication_without_duplicates(self) -> None:
        original = artifacts._write
        for phase in ("before-state", "after-state"):
            with self.subTest(phase=phase):
                seed(self.stream, 0, pending=[{"kept": True}], outages=["parked"])

                def crash(path, text):
                    if phase == "before-state" and path == self.stream / "STATE.md":
                        raise OSError("injected append crash")
                    if phase == "after-state" and path == self.metadata_path and '"pending"' not in json.dumps(json.loads(text).get("state_log", {})):
                        raise OSError("injected append crash")
                    return original(path, text)

                with mock.patch.object(artifacts, "_write", crash):
                    with self.assertRaisesRegex(OSError, "injected append crash"):
                        self.append()
                self.assertIn("pending", self.metadata()["state_log"])
                self.assertEqual(self.append(), 1)
                self.assertEqual(self.log(), f"### {AT} Work\nResult.\n".encode())
                self.assertEqual(self.metadata()["outages"], ["parked"])
                self.assertEqual(self.metadata()["pending"], [{"kept": True}])

    def test_rotation_recovers_archive_then_trim_and_trim_then_ack_crashes(self) -> None:
        original = artifacts._write
        for phase in ("before-trim", "after-trim"):
            with self.subTest(phase=phase):
                if (self.stream / "history").exists():
                    shutil.rmtree(self.stream / "history")
                entries = seed(self.stream, 31)

                def crash(path, text):
                    if phase == "before-trim" and path == self.stream / "STATE.md":
                        raise OSError("injected rotation crash")
                    if phase == "after-trim" and path == self.metadata_path and "pending" not in json.loads(text)["state_log"]:
                        raise OSError("injected rotation crash")
                    return original(path, text)

                with mock.patch.object(artifacts, "_write", crash):
                    with self.assertRaisesRegex(OSError, "injected rotation crash"):
                        artifacts.rotate_log(self.stream)
                history = list((self.stream / "history").glob("*.md"))
                self.assertEqual([path.read_bytes() for path in history], entries[:1])
                artifacts.rotate_log(self.stream)
                self.assertEqual(self.log(), b"".join(entries[1:]))
                self.assertEqual([path.read_bytes() for path in (self.stream / "history").glob("*.md")], entries[:1])

    def test_collision_does_not_overwrite_history_or_trim_log(self) -> None:
        entries = seed(self.stream, 31)
        history = self.stream / "history"
        history.mkdir()
        name = f"20261023T050000000000Z-entry-00000001-work-1-{digest(entries[0])[:16]}.md"
        (history / name).write_bytes(b"foreign bytes\n")
        before = (self.stream / "STATE.md").read_bytes()
        with self.assertRaises(StreamsError):
            artifacts.rotate_log(self.stream)
        self.assertEqual((self.stream / "STATE.md").read_bytes(), before)
        self.assertEqual((history / name).read_bytes(), b"foreign bytes\n")

    def test_incomplete_journal_destination_plan_cannot_authorize_a_trim(self) -> None:
        entries = seed(self.stream, 31)
        original = artifacts._write

        def crash(path, text):
            if path == self.stream / "STATE.md":
                raise OSError("injected pre-trim crash")
            return original(path, text)

        with mock.patch.object(artifacts, "_write", crash):
            with self.assertRaises(OSError):
                artifacts.rotate_log(self.stream)
        data = self.metadata()
        data["state_log"]["pending"]["history"] = []
        self.metadata_path.write_text(json.dumps(data))
        with self.assertRaisesRegex(StreamsError, "prefix plan"):
            artifacts.rotate_log(self.stream)
        self.assertEqual(self.log(), b"".join(entries))
        self.assertEqual([path.read_bytes() for path in (self.stream / "history").glob("*.md")], entries[:1])

    def test_same_timestamp_identical_rotated_entries_keep_distinct_history_files(self) -> None:
        expected = f"### {AT} Work\nResult.\n".encode()
        for number in range(32):
            self.append(request=f"identical-{number}")
        artifacts.rotate_log(self.stream)
        paths = list((self.stream / "history").glob("*.md"))
        self.assertEqual(len(paths), 2)
        self.assertEqual([path.read_bytes() for path in paths], [expected, expected])
        self.assertEqual(self.log(), expected * 30)
        self.assertEqual(len({path.name for path in paths}), 2)

    def test_crlf_prefix_survives_rule_and_log_size_changes(self) -> None:
        prefix = PREFIX.replace(b"\n", b"\r\n")
        (self.stream / "STATE.md").write_bytes(prefix)
        for number in range(31):
            self.append(body="原本", request=f"crlf-{number}")
        artifacts.rotate_log(self.stream)
        self.assertTrue((self.stream / "STATE.md").read_bytes().startswith(prefix))
        self.assertEqual(len(self.metadata()["state_log"]["entries"]), 30)

    def test_recover_rotation_before_objective_update_then_accept_new_tail(self) -> None:
        entries = seed(self.stream, 31)
        original = artifacts._write

        def crash(path, text):
            if path == self.stream / "STATE.md":
                raise OSError("injected pre-trim crash")
            return original(path, text)

        with mock.patch.object(artifacts, "_write", crash):
            with self.assertRaises(OSError):
                artifacts.rotate_log(self.stream)
        artifacts.update_current_objective(self.stream, "After recovery 原本")
        self.assertEqual(self.append(request="post-recovery"), 32)
        artifacts.rotate_log(self.stream)
        self.assertEqual(self.log(), b"".join(entries[2:]) + f"### {AT} Work\nResult.\n".encode())
        self.assertIn("After recovery 原本".encode(), (self.stream / "STATE.md").read_bytes())
        self.assertEqual(len(list((self.stream / "history").glob("*.md"))), 2)

    def test_ruling_crash_preserves_exact_retirement_and_retries_once(self) -> None:
        original = artifacts._write

        def crash(path, text):
            if path == self.stream / "STATE.md":
                raise OSError("injected ruling crash")
            return original(path, text)

        with mock.patch.object(artifacts, "_write", crash):
            with self.assertRaises(OSError):
                artifacts.record_ruling(self.stream, AT, "Replace freeze", "Permit β.\n", notice_id="recover-rule", supersedes=OLD_RULE)
        self.assertEqual((self.stream / "STATE.md").read_bytes(), PREFIX)
        self.assertEqual(artifacts.record_ruling(self.stream, AT, "Replace freeze", "Permit β.\n", notice_id="recover-rule", supersedes=OLD_RULE), 1)
        self.assertEqual([path.read_bytes() for path in (self.stream / "history").glob("*.md")], [OLD_RULE.encode()])
        self.assertEqual(len(self.metadata()["state_log"]["entries"]), 1)
        self.assertIn("Permit β.\n".encode(), (self.stream / "STATE.md").read_bytes())

    def test_unregistered_or_malformed_bypass_bytes_are_not_dropped(self) -> None:
        for suffix in (b"### incomplete", b"unregistered tail\n"):
            with self.subTest(suffix=suffix):
                seed(self.stream, 31)
                source = (self.stream / "STATE.md").read_bytes() + suffix
                (self.stream / "STATE.md").write_bytes(source)
                with self.assertRaises(StreamsError):
                    artifacts.rotate_log(self.stream)
                self.assertEqual((self.stream / "STATE.md").read_bytes(), source)
        self.metadata_path.unlink()
        (self.stream / "STATE.md").write_bytes(PREFIX + b"unregistered old log\n")
        with self.assertRaises(StreamsError):
            self.append()
        self.assertEqual(self.log(), b"unregistered old log\n")

    def test_concurrent_append_and_rotation_preserve_all_occurrences(self) -> None:
        entries = seed(self.stream, 31)
        with ThreadPoolExecutor(max_workers=3) as workers:
            jobs = [workers.submit(self.append, request=f"parallel-{i}") for i in range(8)]
            jobs += [workers.submit(artifacts.rotate_log, self.stream) for _ in range(3)]
            results = [job.result(timeout=10) for job in jobs]
        artifacts.rotate_log(self.stream)
        self.assertEqual(sorted(results[:8]), list(range(32, 40)))
        book = self.metadata()["state_log"]
        self.assertEqual(len(book["entries"]), 30)
        self.assertEqual(book["next_occurrence"], 40)
        history = list((self.stream / "history").glob("*.md"))
        self.assertEqual(len(history), 9)
        self.assertEqual({path.read_bytes() for path in history}, set(entries[:9]))

    def test_human_ruling_updates_rules_logs_arrival_and_retires_exact_text(self) -> None:
        self.assertEqual(artifacts.record_ruling(self.stream, AT, "ZF replaces freeze", "Permit β after review.\n", notice_id="notice-42", supersedes=OLD_RULE), 1)
        source = (self.stream / "STATE.md").read_bytes()
        self.assertTrue(source.startswith(PREFIX.split(b"## Rules\n", 1)[0]))
        self.assertIn("Permit β after review.\n".encode(), source)
        self.assertNotIn(OLD_RULE.encode(), source.split(b"## Log\n", 1)[0])
        self.assertIn(b"## Future notes\nUntouched text, not an implemented feature.\n\n", source)
        history = list((self.stream / "history").glob("*-rule-retired-*.md"))
        self.assertEqual([path.read_bytes() for path in history], [OLD_RULE.encode()])
        self.assertIn(b"notice-42", self.log())
        self.assertEqual(artifacts.record_ruling(self.stream, AT, "ZF replaces freeze", "Permit β after review.\n", notice_id="notice-42", supersedes=OLD_RULE), 1)
        self.assertEqual(len(self.metadata()["state_log"]["entries"]), 1)
        with self.assertRaises(StreamsError):
            artifacts.record_ruling(self.stream, AT, "Other", "New rule", notice_id="notice-43", supersedes="not present")
        self.assertEqual((self.stream / "STATE.md").read_bytes(), source)

    def test_rule_edits_preserve_existing_log_relative_occurrences(self) -> None:
        entries = seed(self.stream, 31)
        before = self.metadata()["state_log"]["entries"]
        artifacts.record_ruling(self.stream, AT, "Replace freeze", "A longer human-authorized rule for β.\n", notice_id="relative-rule", supersedes=OLD_RULE)
        self.assertEqual(self.metadata()["state_log"]["entries"][:31], before)
        prefix, log = (self.stream / "STATE.md").read_bytes().split(b"## Log\n", 1)
        artifacts.rotate_log(self.stream)
        source = (self.stream / "STATE.md").read_bytes()
        self.assertEqual(source.split(b"## Log\n", 1)[0], prefix)
        self.assertEqual(source.split(b"## Log\n", 1)[1], log[len(entries[0]) + len(entries[1]):])
        self.assertEqual(len(self.metadata()["state_log"]["entries"]), 30)
        self.assertEqual(len(list((self.stream / "history").glob("*.md"))), 3)

    def test_new_ruling_and_steer_body_are_logged_without_a_tag_field(self) -> None:
        artifacts.record_ruling(self.stream, AT, "New ruling", "Keep the explicit stop.\n", notice_id="ruling-1")
        self.append(body="ZF notice steer-2\nKeep the original task intent.", request="steer-2", subject="ZF steer at arrival")
        self.assertIn(OLD_RULE.encode(), (self.stream / "STATE.md").read_bytes())
        self.assertIn(b"Keep the explicit stop.\n", (self.stream / "STATE.md").read_bytes())
        self.assertIn(b"ZF notice steer-2\nKeep the original task intent.\n", self.log())
        self.assertEqual(len(self.metadata()["state_log"]["entries"]), 2)
        self.assertNotIn("tag", self.metadata()["state_log"]["entries"][0])

    def test_legacy_schema_is_not_parsed_or_silently_upgraded(self) -> None:
        (self.stream / "stream.toml").write_text('project = "private"\npi_stack_revision = "abc"\n')
        (self.stream / "STATE.md").write_bytes(b"legacy state that is not canonical\n")
        self.assertEqual(artifacts.rotate_log(self.stream), [])
        with self.assertRaises(StreamsError):
            self.append()
        self.assertEqual((self.stream / "STATE.md").read_bytes(), b"legacy state that is not canonical\n")
        self.assertFalse(self.metadata_path.exists())


class LogCliTickTests(TickCase):
    def setUp(self) -> None:
        super().setUp()
        self.stream = self.make_stream(self.home, "canonical", "")
        (self.stream / "STATE.md").write_bytes(PREFIX)

    def test_append_cli_records_actual_body_and_request_receipt(self) -> None:
        body = self.tmp / "body.md"
        body.write_text("A real private artifact operation. 東京\n")
        result = self.run_streams("state", "append", "canonical", "--subject", "Completed private check", "--body-file", str(body), "--request-id", "cli-1", "--at", AT, "--home", str(self.index))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"occurrence": 1, "request_id": "cli-1"})
        self.assertEqual((self.stream / "STATE.md").read_bytes(), PREFIX + f"### {AT} Completed private check\nA real private artifact operation. 東京\n".encode())
        self.assertEqual(self.stub.requests, [])

    def test_eventless_tick_rotates_and_commits_exact_engine_history_without_nested_lock(self) -> None:
        entries = seed(self.stream, 31, pending=[], outages=[])
        result = self.tick("2026-10-23T06:00:00Z", "--home", str(self.index))
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        self.assertEqual((self.stream / "STATE.md").read_bytes(), PREFIX + b"".join(entries[1:]))
        paths = git(self.stream, self.env, "ls-tree", "-r", "--name-only", "HEAD").splitlines()
        history = [name for name in paths if name.startswith("history/")]
        self.assertEqual(len(history), 1)
        self.assertEqual(git(self.stream, self.env, "show", "HEAD:" + history[0]).encode(), entries[0])
        self.assertEqual(self.state(self.stream)["state_log"]["pending_history"], [])
        self.assertEqual(len(self.state(self.stream)["state_log"]["entries"]), 30)
        self.assertEqual(self.stub.requests, [])

    def test_ruling_and_objective_cli_use_the_canonical_engine_boundaries(self) -> None:
        ruling = self.tmp / "ruling.md"
        ruling.write_text("Permit β after review.\n")
        retired = self.tmp / "retired.md"
        retired.write_text(OLD_RULE)
        result = self.run_streams("state", "ruling", "canonical", "--subject", "ZF replaces freeze", "--body-file", str(ruling), "--supersedes-file", str(retired), "--notice-id", "cli-rule", "--at", AT, "--home", str(self.index))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"occurrence": 1, "request_id": "ruling:cli-rule"})
        self.assertEqual([path.read_bytes() for path in (self.stream / "history").glob("*.md")], [OLD_RULE.encode()])
        log = (self.stream / "STATE.md").read_bytes().split(b"## Log\n", 1)[1]
        objective = self.tmp / "objective.md"
        objective.write_text("Next δ")
        result = self.run_streams("state", "objective", "canonical", "--body-file", str(objective), "--home", str(self.index))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"changed": True})
        self.assertIn("Next δ\n".encode(), (self.stream / "STATE.md").read_bytes())
        self.assertEqual((self.stream / "STATE.md").read_bytes().split(b"## Log\n", 1)[1], log)
        self.assertEqual(self.stub.requests, [])

    def test_tick_commit_ack_uses_raw_crlf_nonascii_history_bytes(self) -> None:
        (self.stream / "STATE.md").write_bytes(PREFIX.replace(b"\n", b"\r\n"))
        retired = OLD_RULE.replace("\n", "\r\n")
        artifacts.record_ruling(self.stream, AT, "ZF replaces freeze", "Permit β with 原本.\r\n", notice_id="crlf-rule", supersedes=retired)
        first_log = (self.stream / "STATE.md").read_bytes().split(b"## Log\r\n", 1)[1]
        for number in range(30):
            artifacts.append_log(self.stream, AT, "Later work", "Keep 原本.\r\n", request_id=f"crlf-tick-{number}")
        result = self.tick("2026-10-23T06:00:00Z", "--home", str(self.index))
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        paths = list((self.stream / "history").glob("*.md"))
        self.assertEqual(len(paths), 2)
        expected = {retired.encode(), first_log}
        self.assertEqual({path.read_bytes() for path in paths}, expected)
        committed = {
            subprocess.check_output(["git", "-C", str(self.stream), "show", "HEAD:history/" + path.name], env=self.env)
            for path in paths
        }
        self.assertEqual(committed, expected)
        self.assertEqual(self.state(self.stream)["state_log"]["pending_history"], [])
        self.assertEqual(len(self.state(self.stream)["state_log"]["entries"]), 30)

    def test_mismatched_schema_cannot_be_reseeded_by_new_or_upgrade(self) -> None:
        config = self.stream / "stream.toml"
        config.write_text(config.read_text().replace("state_schema = 1", f"state_schema = {1 - project.TEMPLATE_STATE_SCHEMA}"))
        before = {path.name: path.read_bytes() for path in self.stream.iterdir() if path.is_file()}
        for command in ("new", "upgrade"):
            result = self.run_streams(command, "canonical", "--home", str(self.index))
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn("schema mismatch", result.stderr)
        self.assertEqual({path.name: path.read_bytes() for path in self.stream.iterdir() if path.is_file()}, before)
        self.assertEqual(self.stub.requests, [])

    def test_rotation_precedes_a_missing_project_gate(self) -> None:
        entries = seed(self.stream, 31)
        rows = (self.index / "streams.tsv").read_text().replace("\t" + self.root.name + "\n", "\tmissing-project\n")
        (self.index / "streams.tsv").write_text(rows)
        result = self.tick("2026-10-23T06:00:00Z", "--home", str(self.index))
        self.assertEqual(result.returncode, 1)
        self.assertIn("missing project", result.stderr)
        self.assertEqual((self.stream / "STATE.md").read_bytes(), PREFIX + b"".join(entries[1:]))
        self.assertEqual([path.read_bytes() for path in (self.stream / "history").glob("*.md")], entries[:1])


if __name__ == "__main__":
    unittest.main()
