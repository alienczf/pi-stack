from __future__ import annotations

import base64
import json
import os
import sys
from unittest import mock

from support import EngineCase, ROOT, git, snapshot
from test_artifact_migration import AT, STREAM, DECISIONS, authority_map

sys.path.insert(0, str(ROOT / "pi-streams"))
from engine import StreamsError, artifacts, migration
from engine.project import load_stream_config, stream_lock


class MigrationApplyTests(EngineCase):
    def setUp(self):
        super().setUp()
        self.assertEqual(self.run_streams("init", str(self.root), "-y").returncode, 0)
        self.stream = self.seed("legacy")
        self.stub.requests.clear()

    def seed(self, name):
        stream = self.register_stream(name)
        (stream / "threads.tsv").write_text("session\trole\trepo\tworktree\tbranch\tbase\tmodel\tthinking\tstatus\tstarted\n")
        (stream / "stream.toml").write_text('project = "proj"\npi_stack_revision = "legacy"\n')
        (stream / "STREAM.md").write_bytes(STREAM)
        (stream / "DECISIONS.md").write_bytes(DECISIONS)
        (stream / "STATE.md").write_bytes(b"legacy preamble\r\n## Work\r\nunfinished owned reference\r\n")
        (stream / "unrelated.md").write_text("tracked unrelated original\n")
        git(stream, self.env, "init")
        git(stream, self.env, "add", "--all")
        git(stream, self.env, "commit", "-m", "legacy private fixture")
        return stream

    def plan(self, stream=None):
        with mock.patch.dict(os.environ, self.env, clear=True):
            return migration.plan_migration(stream or self.stream, authority_map(), started_at=AT).public()

    def apply(self, plan=None, stream=None):
        root = stream or self.stream
        with mock.patch.dict(os.environ, self.env, clear=True), stream_lock(root):
            return migration.apply_migration_locked(root, plan)

    def count(self, stream=None):
        return int(git(stream or self.stream, self.env, "rev-list", "--count", "HEAD"))

    def test_scoped_once_commit_preserves_foreign_stage_excluded_and_worker_bytes(self):
        failures = self.stream / "failures"
        failures.mkdir()
        for number in (1, 2):
            (failures / f"00000000-0000-0000-0000-{number:012d}.lastgood").write_text(f"exact-entry-{number}\n")
        (failures / "recovery.json").write_bytes(b'{ "uncertainJob": "never-resubmit", "notice": "actual-human-source" }\r\n')
        for name in ("TODO.md", "PLAN.md", "ALERTS.md", "decisions.tsv"):
            (self.stream / name).write_bytes(b"do not import or modify\r\n")
        (self.stream / "foreign.md").write_text("foreign staged bytes\n")
        git(self.stream, self.env, "add", "foreign.md")
        staged = git(self.stream, self.env, "ls-files", "--stage", "foreign.md")
        (self.stream / "unrelated.md").write_text("unrelated unstaged change\n")
        before = snapshot(self.stream)
        workers = snapshot(self.fx.alpha_wt)
        count = self.count()
        plan = self.plan()
        result = self.apply(plan)
        self.assertEqual(self.count(), count + 1)
        self.assertEqual(result["id"], plan["id"])
        self.assertTrue(result["changed"])
        self.assertFalse((self.stream / "STREAM.md").exists())
        self.assertFalse((self.stream / "DECISIONS.md").exists())
        self.assertEqual(load_stream_config(self.stream / "stream.toml").state_schema, 1)
        with mock.patch.dict(os.environ, self.env, clear=True):
            state = artifacts.read_stream_state(self.stream)
        self.assertEqual(artifacts.resolve_current_goal(state), "Verify the retained artifact.")
        self.assertEqual(state.source[state.log.body.start:].count(b"### "), 1)
        self.assertEqual(git(self.stream, self.env, "ls-files", "--stage", "foreign.md"), staged)
        changed = set(git(self.stream, self.env, "diff-tree", "--no-commit-id", "--name-only", "--no-renames", "-r", "HEAD").splitlines())
        approved = {"STATE.md", "STREAM.md", "DECISIONS.md", "stream.toml", ".gitignore", "failures/.gitkeep", *(p["path"] for p in plan["history"])}
        self.assertLessEqual(changed, approved)
        self.assertNotIn("unrelated.md", changed)
        for name in ("TODO.md", "PLAN.md", "ALERTS.md", "decisions.tsv", "foreign.md", "unrelated.md"):
            self.assertEqual((self.stream / name).read_bytes(), before[name])
        for name, raw in before.items():
            if name.startswith("failures/"):
                self.assertEqual((self.stream / name).read_bytes(), raw)
        self.assertEqual(snapshot(self.fx.alpha_wt), workers)
        archives = [p for p in plan["history"] if p["source"] == "STATE.md"]
        self.assertEqual(b"".join((self.stream / p["path"]).read_bytes() for p in archives), before["STATE.md"])
        for part in plan["history"]:
            self.assertEqual((self.stream / part["path"]).read_bytes(), base64.b64decode(part["bytes"]))
        head = result["commit"]
        again = self.apply()
        self.assertFalse(again["changed"])
        self.assertEqual(again["commit"], head)
        self.assertEqual(self.count(), count + 1)
        self.assertEqual(self.stub.requests, [])

    def test_crash_phase_retries_converge_without_duplicate_seed_archive_or_commit(self):
        for phase in ("history", "state", "retire", "commit"):
            with self.subTest(phase=phase):
                root = self.seed("crash-" + phase)
                plan = self.plan(root)
                real = migration._set_phase
                fired = False
                def interrupt(path, operation, current):
                    nonlocal fired
                    real(path, operation, current)
                    if current == phase and not fired:
                        fired = True
                        raise OSError("labelled private migration interruption: " + phase)
                with mock.patch("engine.migration._set_phase", side_effect=interrupt):
                    with self.assertRaisesRegex(OSError, "labelled"):
                        self.apply(plan, root)
                result = self.apply(stream=root)
                self.assertTrue(result["commit"])
                self.assertEqual(self.count(root), 2)
                self.assertEqual((root / "STATE.md").read_bytes().count(b"Stream artifact migration"), 1)
                self.assertEqual(len(list((root / "history").glob("*.md"))), len(plan["history"]))
                self.assertFalse(self.apply(stream=root)["changed"])
        self.assertEqual(self.stub.requests, [])

    def test_crash_after_commit_before_receipt_reconciles_exact_own_commit(self):
        plan = self.plan()
        real = migration.commit_repo
        def after_commit(*args, **kwargs):
            real(*args, **kwargs)
            raise OSError("labelled post-commit pre-receipt interruption")
        with mock.patch("engine.migration.commit_repo", side_effect=after_commit):
            with self.assertRaisesRegex(OSError, "post-commit"):
                self.apply(plan)
        head = git(self.stream, self.env, "rev-parse", "HEAD").strip()
        result = self.apply()
        self.assertEqual(result["commit"], head)
        self.assertEqual(self.count(), 2)
        self.assertFalse(self.apply()["changed"])

    def test_changed_source_or_plan_refuses_before_publication(self):
        plan = self.plan()
        altered = dict(plan)
        altered["state"] = base64.b64encode(b"forged state\n").decode()
        before = snapshot(self.stream)
        with self.assertRaisesRegex(StreamsError, "plan|changed"):
            self.apply(altered)
        self.assertEqual(snapshot(self.stream), before)
        (self.stream / "DECISIONS.md").write_bytes(DECISIONS + b"A new active human freeze.\n")
        before = snapshot(self.stream)
        with self.assertRaisesRegex(StreamsError, "changed|plan"):
            self.apply(plan)
        self.assertEqual(snapshot(self.stream), before)
        self.assertEqual(self.count(), 1)

    def test_interrupted_archive_refuses_unexpected_non_state_change(self):
        plan = self.plan()
        real = migration._set_phase
        def interrupt(path, operation, phase):
            real(path, operation, phase)
            if phase == "state":
                raise OSError("labelled after-history interruption")
        with mock.patch("engine.migration._set_phase", side_effect=interrupt):
            with self.assertRaises(OSError):
                self.apply(plan)
        (self.stream / "STREAM.md").write_bytes(STREAM + b"New ruling after interruption.\n")
        before = snapshot(self.stream)
        with self.assertRaisesRegex(StreamsError, "changed"):
            self.apply()
        self.assertEqual(snapshot(self.stream), before)
        self.assertEqual(self.count(), 1)

    def test_pending_operation_blocks_canonical_writers_and_native_dispatch(self):
        real = migration._set_phase
        def interrupt(path, operation, phase):
            real(path, operation, phase)
            if phase == "commit":
                raise OSError("labelled pre-commit interruption")
        with mock.patch("engine.migration._set_phase", side_effect=interrupt):
            with self.assertRaises(OSError):
                self.apply(self.plan())
        before = (self.stream / "STATE.md").read_bytes()
        with mock.patch.dict(os.environ, self.env, clear=True):
            with self.assertRaisesRegex(StreamsError, "migration"):
                artifacts.update_current_objective(self.stream, "must not cross migration")
        result = self.run_streams("new", "legacy")
        self.assertEqual(result.returncode, 1)
        self.assertIn("migration", result.stderr)
        self.assertEqual((self.stream / "STATE.md").read_bytes(), before)
        self.assertEqual(self.stub.requests, [])
        self.apply()

    def test_foreign_overlapping_staged_state_refuses_without_mutation(self):
        (self.stream / "STATE.md").write_bytes(b"foreign staged legacy content\n")
        git(self.stream, self.env, "add", "STATE.md")
        plan = self.plan()
        before = snapshot(self.stream)
        staged = git(self.stream, self.env, "ls-files", "--stage")
        with self.assertRaisesRegex(StreamsError, "staged|overlap"):
            self.apply(plan)
        self.assertEqual(snapshot(self.stream), before)
        self.assertEqual(git(self.stream, self.env, "ls-files", "--stage"), staged)

    def test_completed_migration_never_rewinds_later_canonical_goal_or_log(self):
        result = self.apply(self.plan())
        with mock.patch.dict(os.environ, self.env, clear=True):
            artifacts.update_current_objective(self.stream, "A genuinely later objective.")
            artifacts.append_log(self.stream, AT, "Later work", "Owned later facts.\n", request_id="later-work-1")
        before = snapshot(self.stream)
        again = self.apply()
        self.assertEqual(again, {"id": result["id"], "commit": result["commit"], "changed": False})
        self.assertEqual(snapshot(self.stream), before)
        self.assertIn(b"A genuinely later objective.", (self.stream / "STATE.md").read_bytes())

    def test_unborn_repository_and_untracked_legacy_sources_get_one_commit(self):
        root = self.register_stream("unborn")
        (root / "threads.tsv").write_text("session\trole\trepo\tworktree\tbranch\tbase\tmodel\tthinking\tstatus\tstarted\n")
        (root / "stream.toml").write_text('project = "proj"\npi_stack_revision = "legacy"\n')
        (root / "STREAM.md").write_bytes(STREAM)
        (root / "DECISIONS.md").write_bytes(DECISIONS)
        (root / "STATE.md").write_text("never committed legacy STATE\n")
        git(root, self.env, "init")
        result = self.apply(self.plan(root), root)
        self.assertTrue(result["changed"])
        self.assertEqual(self.count(root), 1)
        self.assertFalse(self.apply(stream=root)["changed"])

    def test_schema_metadata_preserves_unknown_configuration_and_refuses_unresolved_plan(self):
        config = self.stream / "stream.toml"
        config.write_text(config.read_text() + 'state_schema = 0\nopaque = "retained"\n')
        plan = self.plan()
        self.apply(plan)
        self.assertIn(b'opaque = "retained"\n', config.read_bytes())
        self.assertEqual(config.read_bytes().count(b"state_schema"), 1)
        root = self.seed("unresolved")
        with mock.patch.dict(os.environ, self.env, clear=True):
            unresolved = migration.plan_migration(root, started_at=AT).public()
        before = snapshot(root)
        with self.assertRaisesRegex(StreamsError, "unresolved"):
            self.apply(unresolved, root)
        self.assertEqual(snapshot(root), before)

    def test_interruption_layout_change_refuses_before_any_commit(self):
        real = migration._set_phase
        def interrupt(path, operation, phase):
            real(path, operation, phase)
            if phase == "commit":
                raise OSError("labelled pre-commit layout interruption")
        with mock.patch("engine.migration._set_phase", side_effect=interrupt):
            with self.assertRaises(OSError):
                self.apply(self.plan())
        (self.stream / ".gitignore").unlink()
        with self.assertRaises(StreamsError):
            self.apply()
        self.assertEqual(self.count(), 1, "changed layout must refuse before creating a bad migration commit")

    def test_interruption_layout_index_lock_keeps_post_commit_receipt_unconfirmed(self):
        real = migration.commit_repo
        def interrupted(*args, **kwargs):
            real(*args, **kwargs)
            raise OSError("labelled post-commit interruption")
        with mock.patch("engine.migration.commit_repo", side_effect=interrupted):
            with self.assertRaises(OSError):
                self.apply(self.plan())
        lock = self.stream / ".git/index.lock"
        lock.write_text("labelled owned fixture lock, not an actual unknown lock\n")
        with self.assertRaisesRegex(StreamsError, "index|publication"):
            self.apply()
        self.assertTrue(lock.exists())
        lock.unlink()
        self.assertFalse(self.apply()["changed"])
        self.assertEqual(self.count(), 2)

    def test_cli_explicit_apply_then_resume_is_a_zero_native_zero_commit_noop(self):
        path = self.tmp / "plan.json"
        path.write_text(json.dumps(self.plan()))
        first = self.run_streams("migrate", "legacy", "--apply", str(path))
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertTrue(json.loads(first.stdout)["changed"])
        second = self.run_streams("migrate", "legacy", "--resume")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertFalse(json.loads(second.stdout)["changed"])
        self.assertEqual(self.count(), 2)
        self.assertEqual(self.stub.requests, [])
