"""Durable snapshots, interrupted registration, and exact-path automatic commits."""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from support import EngineCase, git, make_env

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine import StreamsError
from engine import project, threads


class SnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="pi-streams-snapshot-"))
        self.addCleanup(lambda: shutil.rmtree(self.tmp))
        self.project = project.Project(
            project.ProjectSection("demo", "/private/demo", "http://127.0.0.1:9", "/private/wt", "abc"),
            project.ModelSettings("openai-codex/gpt-6.1-sol", "xhigh"),
            project.ModelSettings("openai-codex/gpt-6.1-sol", "xhigh"),
            project.Caps(), [],
        )

    def writers(self):
        return (
            (self.tmp / "projects" / "demo.toml", lambda: project.save_project(self.tmp, self.project)),
            (self.tmp / "stream.toml", lambda: project.save_stream_config(self.tmp, project.StreamConfig("demo", "abc"))),
            (self.tmp / "threads.tsv", lambda: threads.save_threads(self.tmp / "threads.tsv", [])),
            (self.tmp / "streams.tsv", lambda: project.save_stream_rows(self.tmp, [])),
        )

    def test_interrupted_writes_leave_the_previous_snapshot(self) -> None:
        original = Path.write_text
        for path, save in self.writers():
            with self.subTest(path=path.name):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"previous complete snapshot\n")

                def short_write(destination, text, *args, **kwargs):
                    original(destination, text[:len(text) // 2], *args, **kwargs)
                    raise OSError("injected short write")

                with mock.patch.object(Path, "write_text", short_write):
                    with self.assertRaisesRegex(OSError, "injected short write"):
                        save()
                self.assertEqual(path.read_bytes(), b"previous complete snapshot\n")
                self.assertEqual(list(path.parent.glob(".pi-streams-*.tmp")), [])
                save()
                self.assertNotEqual(path.read_bytes(), b"previous complete snapshot\n")

    def test_failed_replacement_or_file_sync_preserves_old_bytes(self) -> None:
        for operation in ("replace", "fsync"):
            for path, save in self.writers():
                with self.subTest(operation=operation, path=path.name):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b"old complete bytes\n")
                    with mock.patch.object(os, operation, side_effect=OSError("injected publication failure")):
                        with self.assertRaisesRegex(OSError, "injected publication failure"):
                            save()
                    self.assertEqual(path.read_bytes(), b"old complete bytes\n")
                    self.assertEqual(list(path.parent.glob(".pi-streams-*.tmp")), [])

    def test_readers_see_old_bytes_until_the_complete_replacement(self) -> None:
        original = Path.write_text
        for path, save in self.writers():
            with self.subTest(path=path.name):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"old complete bytes\n")
                observed = []

                def observe_write(destination, text, *args, **kwargs):
                    original(destination, text[:len(text) // 2], *args, **kwargs)
                    observed.append(path.read_bytes())
                    return original(destination, text, *args, **kwargs)

                with mock.patch.object(Path, "write_text", observe_write):
                    save()
                self.assertEqual(observed, [b"old complete bytes\n"])
                self.assertNotEqual(path.read_bytes(), b"old complete bytes\n")


class RegistrationTests(EngineCase):
    def test_retry_repairs_registration_without_overwriting_owned_documents(self) -> None:
        proc = self.run_streams("init", str(self.root), "-y")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        with mock.patch.dict(os.environ, self.env, clear=True):
            config = project.load_project(self.project_file)
            stream = project.create_stream(self.index, config, "retry")
            (stream / "STATE.md").write_bytes(b"owned state must survive\n")
            (self.index / "streams.tsv").write_text("id\tpath\tproject\n", encoding="utf-8")
            before = {name: (stream / name).read_bytes() for name in ("STATE.md", "AGENTS.md", "context/README.md", "stream.toml")}
            project.create_stream(self.index, config, "retry")
            project.create_stream(self.index, config, "retry")
        self.assertEqual((self.index / "streams.tsv").read_text(), f"id\tpath\tproject\nretry\t{stream}\t{self.root.name}\n")
        self.assertEqual({name: (stream / name).read_bytes() for name in before}, before)
        self.assertEqual(self.stub.requests, [])


class ScopedCommitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="pi-streams-git-"))
        self.addCleanup(lambda: shutil.rmtree(self.tmp))
        self.env = make_env(self.tmp / "home", self.tmp / "config", "http://127.0.0.1:9")
        self.env["GIT_CONFIG_GLOBAL"] = os.devnull
        self.env["HOME"] = str(self.tmp / "home")
        Path(self.env["HOME"]).mkdir()
        self.environment = mock.patch.dict(os.environ, self.env, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.repo = self.tmp / "stream"
        self.repo.mkdir()
        git(self.repo, self.env, "init", "--quiet")
        self.put("STATE.md", b"old state\n")
        self.put("checks/check.py", b"print('old')\n")
        git(self.repo, self.env, "add", "--", "STATE.md", "checks/check.py")
        git(self.repo, self.env, "commit", "-qm", "seed")

    def put(self, name: str, body: bytes) -> None:
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)

    def test_commits_only_owned_records_and_approved_tracked_text(self) -> None:
        self.put("STATE.md", b"new state\n")
        self.put("checks/check.py", b"print('new')\n")
        for name, body in (("scratch.dll", b"MZ\x00payload"), ("package.zip", b"PK\x00payload"),
                           ("data.csv", b"a,b\n1,2\n"), ("checks/unapproved.py", b"print('not approved')\n")):
            self.put(name, body)
        self.put("foreign.md", b"staged foreign version\n")
        git(self.repo, self.env, "add", "--", "foreign.md")
        self.put("foreign.md", b"unstaged foreign version\n")
        staged = git(self.repo, self.env, "ls-files", "--stage", "--", "foreign.md")
        self.assertTrue(project.commit_repo(self.repo, "automatic"))
        self.assertEqual(git(self.repo, self.env, "show", "--format=", "--name-only", "HEAD"), "STATE.md\nchecks/check.py\n")
        self.assertEqual(git(self.repo, self.env, "show", "HEAD:STATE.md"), "new state\n")
        self.assertEqual(git(self.repo, self.env, "show", "HEAD:checks/check.py"), "print('new')\n")
        self.assertEqual(git(self.repo, self.env, "ls-files", "--stage", "--", "foreign.md"), staged)
        self.assertEqual(git(self.repo, self.env, "show", ":foreign.md"), "staged foreign version\n")
        self.assertEqual((self.repo / "foreign.md").read_bytes(), b"unstaged foreign version\n")
        self.assertEqual(git(self.repo, self.env, "diff", "--cached", "--name-only"), "foreign.md\n")
        self.assertFalse(project.commit_repo(self.repo, "nothing owned"))

    def test_unrelated_staged_binary_survives_but_is_never_committed(self) -> None:
        self.put("foreign.dll", b"MZ\x00foreign bytes")
        git(self.repo, self.env, "add", "--", "foreign.dll")
        staged = git(self.repo, self.env, "ls-files", "--stage", "--", "foreign.dll")
        self.put("STATE.md", b"new state\n")
        self.assertTrue(project.commit_repo(self.repo, "automatic"))
        self.assertEqual(git(self.repo, self.env, "show", "--format=", "--name-only", "HEAD"), "STATE.md\n")
        self.assertEqual(git(self.repo, self.env, "ls-files", "--stage", "--", "foreign.dll"), staged)
        self.assertEqual((self.repo / "foreign.dll").read_bytes(), b"MZ\x00foreign bytes")

    def test_binary_candidate_refuses_without_changing_head_or_index(self) -> None:
        for name in ("STATE.md", "checks/check.py"):
            with self.subTest(name=name):
                self.put(name, b"bad\x00binary update")
                index = (self.repo / ".git/index").read_bytes()
                head = git(self.repo, self.env, "rev-parse", "HEAD")
                with self.assertRaisesRegex(StreamsError, "binary"):
                    project.commit_repo(self.repo, "must refuse")
                self.assertEqual((self.repo / ".git/index").read_bytes(), index)
                self.assertEqual(git(self.repo, self.env, "rev-parse", "HEAD"), head)
                self.assertEqual((self.repo / name).read_bytes(), b"bad\x00binary update")
                self.put(name, b"restored text\n")

    def test_overlapping_staged_edit_refuses_without_losing_either_version(self) -> None:
        self.put("STATE.md", b"foreign staged state\n")
        git(self.repo, self.env, "add", "--", "STATE.md")
        self.put("STATE.md", b"working state\n")
        index = (self.repo / ".git/index").read_bytes()
        head = git(self.repo, self.env, "rev-parse", "HEAD")
        with self.assertRaisesRegex(StreamsError, "staged"):
            project.commit_repo(self.repo, "must refuse")
        self.assertEqual((self.repo / ".git/index").read_bytes(), index)
        self.assertEqual(git(self.repo, self.env, "rev-parse", "HEAD"), head)
        self.assertEqual(git(self.repo, self.env, "show", ":STATE.md"), "foreign staged state\n")
        self.assertEqual((self.repo / "STATE.md").read_bytes(), b"working state\n")

    def test_explicit_new_report_is_allowed_but_data_and_path_escapes_are_not(self) -> None:
        self.put("checks/new report.md", b"explicitly approved result\n")
        self.put("STATE.md", b"updated with the report\n")
        self.assertTrue(project.commit_repo(self.repo, "report", paths=("checks/new report.md",)))
        self.assertEqual(git(self.repo, self.env, "show", "HEAD:checks/new report.md"), "explicitly approved result\n")
        self.assertEqual(git(self.repo, self.env, "show", "HEAD:STATE.md"), "updated with the report\n")
        for name in ("data.csv", "../outside.md", ".git/config", "checks"):
            with self.subTest(name=name):
                index = (self.repo / ".git/index").read_bytes()
                head = git(self.repo, self.env, "rev-parse", "HEAD")
                with self.assertRaises(StreamsError):
                    project.commit_repo(self.repo, "must refuse", paths=(name,))
                self.assertEqual((self.repo / ".git/index").read_bytes(), index)
                self.assertEqual(git(self.repo, self.env, "rev-parse", "HEAD"), head)

    def test_tracked_data_is_not_an_automatic_text_report(self) -> None:
        self.put("data.csv", b"a,b\n1,2\n")
        git(self.repo, self.env, "add", "--", "data.csv")
        git(self.repo, self.env, "commit", "-qm", "historical data contamination")
        self.put("data.csv", b"a,b\n3,4\n")
        self.put("STATE.md", b"new state\n")
        self.assertTrue(project.commit_repo(self.repo, "automatic"))
        self.assertEqual(git(self.repo, self.env, "show", "HEAD:data.csv"), "a,b\n1,2\n")
        self.assertEqual((self.repo / "data.csv").read_bytes(), b"a,b\n3,4\n")
        self.assertEqual(git(self.repo, self.env, "diff", "--name-only"), "data.csv\n")

    def test_rename_reconciles_both_paths_without_absorbing_foreign_staging(self) -> None:
        (self.repo / "checks/check.py").rename(self.repo / "checks/renamed.py")
        self.put("foreign.md", b"foreign staged report\n")
        git(self.repo, self.env, "add", "--", "foreign.md")
        self.assertTrue(project.commit_repo(self.repo, "rename", paths=("checks/renamed.py",)))
        self.assertEqual(git(self.repo, self.env, "ls-tree", "-r", "--name-only", "HEAD"), "STATE.md\nchecks/renamed.py\n")
        self.assertEqual(git(self.repo, self.env, "show", "HEAD:checks/renamed.py"), "print('old')\n")
        self.assertEqual(git(self.repo, self.env, "diff", "--cached", "--name-only"), "foreign.md\n")
        self.assertEqual(git(self.repo, self.env, "show", ":foreign.md"), "foreign staged report\n")
        self.assertEqual(git(self.repo, self.env, "diff", "--name-only"), "")

    def test_failed_commit_preserves_the_original_index_and_worktree(self) -> None:
        self.put("foreign.md", b"foreign stage\n")
        git(self.repo, self.env, "add", "--", "foreign.md")
        self.put("STATE.md", b"new state\n")
        index = (self.repo / ".git/index").read_bytes()
        head = git(self.repo, self.env, "rev-parse", "HEAD")
        original = project.git

        def refuse_commit(cwd, *args, **kwargs):
            if "commit" in args or "commit-tree" in args:
                raise StreamsError("injected commit failure")
            return original(cwd, *args, **kwargs)

        with mock.patch.object(project, "git", refuse_commit):
            with self.assertRaisesRegex(StreamsError, "injected commit failure"):
                project.commit_repo(self.repo, "commit failure")
        self.assertEqual((self.repo / ".git/index").read_bytes(), index)
        self.assertEqual(git(self.repo, self.env, "rev-parse", "HEAD"), head)
        self.assertEqual((self.repo / "STATE.md").read_bytes(), b"new state\n")
        self.assertFalse((self.repo / ".git/index.lock").exists())

    def test_existing_index_lock_is_not_removed_or_overwritten(self) -> None:
        lock = self.repo / ".git/index.lock"
        lock.write_bytes(b"another Git writer\n")
        index = (self.repo / ".git/index").read_bytes()
        self.put("STATE.md", b"new state\n")
        with self.assertRaisesRegex(StreamsError, "locked"):
            project.commit_repo(self.repo, "must refuse")
        self.assertEqual(lock.read_bytes(), b"another Git writer\n")
        self.assertEqual((self.repo / ".git/index").read_bytes(), index)
        self.assertEqual(git(self.repo, self.env, "show", "HEAD:STATE.md"), "old state\n")

    def test_symlink_to_an_outside_report_is_not_followed(self) -> None:
        outside = self.tmp / "outside.md"
        outside.write_bytes(b"outside report\n")
        (self.repo / "checks/link.md").symlink_to(outside)
        with self.assertRaisesRegex(StreamsError, "not an approved"):
            project.commit_repo(self.repo, "must refuse", paths=("checks/link.md",))
        self.assertEqual(outside.read_bytes(), b"outside report\n")
        self.assertEqual(git(self.repo, self.env, "rev-list", "--count", "HEAD"), "1\n")
        self.assertEqual(git(self.repo, self.env, "ls-files", "checks/link.md"), "")

    def test_initial_commit_includes_only_known_harness_files(self) -> None:
        repo = self.tmp / "new-stream"
        repo.mkdir()
        git(repo, self.env, "init", "--quiet")
        project.copy_missing(project.templates_dir() / "stream", repo)
        project.save_stream_config(repo, project.StreamConfig("demo", "abc"))
        (repo / "scratch.csv").write_bytes(b"a,b\n1,2\n")
        (repo / "unapproved.md").write_bytes(b"not an engine record\n")
        self.assertTrue(project.commit_repo(repo, "initial"))
        self.assertEqual(git(repo, self.env, "ls-files"), (
            ".gitignore\nAGENTS.md\nSTATE.md\nchecks/.gitkeep\ncontext/README.md\n"
            "failures/.gitkeep\nhandover/.gitkeep\nhistory/.gitkeep\nstream.toml\nsubscriptions.tsv\nthreads.tsv\n"
        ))
        self.assertEqual(git(repo, self.env, "rev-list", "--count", "HEAD"), "1\n")
        self.assertEqual((repo / "scratch.csv").read_bytes(), b"a,b\n1,2\n")

    def test_failed_index_publication_reports_the_exact_published_commit(self) -> None:
        self.put("STATE.md", b"new state\n")
        index = (self.repo / ".git/index").read_bytes()
        with mock.patch.object(os, "replace", side_effect=OSError("injected index failure")):
            with self.assertRaisesRegex(StreamsError, "index publication is unconfirmed") as failure:
                project.commit_repo(self.repo, "published")
        head = git(self.repo, self.env, "rev-parse", "HEAD").strip()
        self.assertIn(head, str(failure.exception))
        self.assertEqual(git(self.repo, self.env, "show", "HEAD:STATE.md"), "new state\n")
        self.assertEqual((self.repo / ".git/index").read_bytes(), index)
        self.assertFalse(project.commit_repo(self.repo, "must not duplicate"))
        self.assertEqual(git(self.repo, self.env, "rev-list", "--count", "HEAD"), "2\n")


if __name__ == "__main__":
    unittest.main()
