"""A predecessor's exit evidence cannot close its same-role successor."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from support import EngineCase, ROOT, git, seed_ratified_stream

sys.path.insert(0, str(ROOT / "pi-streams"))
from engine.project import git_blob

HEADER = "session\trole\trepo\tworktree\tbranch\tbase\tmodel\tthinking\tstatus\tstarted\n"
OLD = "a438be29-aaaa-4000-8000-000000000001"
CURRENT = "a438be29-aaaa-4000-8000-000000000002"
OTHER = "b438be29-aaaa-4000-8000-000000000003"
COORD = "c438be29-aaaa-4000-8000-000000000004"


def handover(sid: str, body: str = "intent: finish the assigned slice\nproof: private fixture checked\n") -> bytes:
    return f"session: {sid}\n{body}".encode()


def status(sid: str) -> dict[str, object]:
    return {"sessionId": sid, "isStreaming": False, "contextUsage": {"tokens": 10},
            "model": {"provider": "openai-codex", "id": "gpt-6-astra"},
            "thinkingLevel": "xhigh", "cost": 0}


class HandoverIdentityTests(EngineCase):
    def setUp(self) -> None:
        super().setUp()
        result = self.run_streams("init", str(self.root), "-y")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.stream = self.register_stream("etl")
        seed_ratified_stream(self.stream, self.root.name)
        self.table = self.stream / "threads.tsv"
        self.table.write_text(HEADER + self.row(COORD, "coordinator", "active")
                              + self.row(OLD, "worker", "archived")
                              + self.row(CURRENT, "worker", "active"))
        git(self.stream, self.env, "init")
        git(self.stream, self.env, "add", "-A")
        git(self.stream, self.env, "commit", "-m", "private fixture")
        self.stub.requests.clear()

    def row(self, sid: str, role: str, state: str) -> str:
        return f"{sid}\t{role}\talpha\t{self.fx.alpha_wt}\tfeat-a\tbase\topenai-codex/gpt-6-astra\txhigh\t{state}\t2026-10-23T05:00:00Z\n"

    def write_handover(self, sid: str, role: str = "worker", *, body: bytes | None = None, legacy: bool = False) -> Path:
        path = self.stream / "handover" / (f"{role}.md" if legacy else f"{role}/{sid}.md")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(handover(sid) if body is None else body)
        return path

    def assert_refused(self, message: str) -> None:
        before = self.table.read_bytes()
        head = git(self.stream, self.env, "rev-parse", "HEAD")
        result = self.run_streams("close", "etl")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(message, result.stderr)
        self.assertEqual(self.stub.requests, [])
        self.assertEqual(self.table.read_bytes(), before)
        self.assertEqual(git(self.stream, self.env, "rev-parse", "HEAD"), head)

    def test_predecessor_handover_cannot_close_successor_then_own_artifact_can(self) -> None:
        legacy = self.write_handover(OLD, legacy=True)
        old_file = self.write_handover(OLD)
        old_bytes = old_file.read_bytes()
        legacy_bytes = legacy.read_bytes()
        self.assert_refused(CURRENT)
        self.assertEqual(old_file.read_bytes(), old_bytes)
        self.assertEqual(legacy.read_bytes(), legacy_bytes)
        current = self.write_handover(CURRENT)
        result = self.run_streams("close", "etl")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, f"archived {CURRENT} worker\ndone {COORD} coordinator\n")
        self.assertEqual(self.stub.requests, [("POST", f"/api/sessions/{CURRENT}/archive", "", {})])
        self.assertEqual(git_blob(self.stream, f"HEAD:handover/worker/{CURRENT}.md"), current.read_bytes())
        self.assertEqual(old_file.read_bytes(), old_bytes)
        self.assertEqual(legacy.read_bytes(), legacy_bytes)

    def test_same_role_successor_brief_uses_the_actual_full_spawned_id(self) -> None:
        self.table.write_text(HEADER)
        prompts = []
        for sid in (OLD, CURRENT):
            self.stub.set_routes([
                ("GET", "/api/sessions", 200, []),
                ("POST", "/api/sessions", 200, {"id": sid}),
                ("GET", f"/api/sessions/{sid}/status", 200, status(sid)),
                ("POST", f"/api/sessions/{sid}/prompt", 200, {"accepted": True}),
            ])
            result = self.run_streams("thread", "spawn", "etl", "--repo", "alpha", "--role", "worker")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, sid + "\n")
            prompts.append(self.stub.requests[-1][3]["text"])
            if sid == OLD:
                self.table.write_text(self.table.read_text().replace("\tactive\t", "\tarchived\t"))
        self.assertIn(f"{self.stream}/handover/worker/{OLD}.md", prompts[0])
        self.assertIn(f"{self.stream}/handover/worker/{CURRENT}.md", prompts[1])
        self.assertNotIn(f"handover/worker/{OLD}.md", prompts[1])
        self.assertIn(f"session: {CURRENT}", prompts[1])
        self.assertIn("owned worktree", prompts[1])
        self.assertIn("exact copies", prompts[1])

    def test_scoped_close_approves_only_exact_validated_paths(self) -> None:
        current = self.write_handover(CURRENT)
        old = self.write_handover(OLD)
        legacy = self.write_handover(OTHER, legacy=True)
        foreign = self.stream / "foreign.md"
        foreign.write_text("unrelated staged report\n")
        data = self.stream / "sample.csv"
        data.write_bytes(b"a,b\n1,2\n")
        git(self.stream, self.env, "add", "foreign.md")
        staged = git(self.stream, self.env, "ls-files", "--stage", "foreign.md")
        result = self.run_streams("close", "etl")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(git_blob(self.stream, f"HEAD:handover/worker/{CURRENT}.md"), current.read_bytes())
        self.assertEqual(git_blob(self.stream, f"HEAD:handover/worker/{OLD}.md"), old.read_bytes())
        committed = git(self.stream, self.env, "ls-tree", "-r", "--name-only", "HEAD").splitlines()
        for excluded in ("handover/worker.md", "foreign.md", "sample.csv"):
            self.assertNotIn(excluded, committed)
        self.assertEqual(git(self.stream, self.env, "ls-files", "--stage", "foreign.md"), staged)
        self.assertEqual(legacy.read_bytes(), handover(OTHER))
        self.assertEqual(data.read_bytes(), b"a,b\n1,2\n")

    def test_legacy_exact_recorded_identity_is_accepted_without_copy_or_rewrite(self) -> None:
        original = (f"session: {CURRENT}\r\nintent: preserve caf\u00e9 and proof\r\n").encode()
        legacy = self.write_handover(CURRENT, body=original, legacy=True)
        result = self.run_streams("close", "etl")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(legacy.read_bytes(), original)
        self.assertEqual(git_blob(self.stream, "HEAD:handover/worker.md"), original)
        self.assertFalse((self.stream / f"handover/worker/{CURRENT}.md").exists())
        self.assertEqual(self.stub.requests, [("POST", f"/api/sessions/{CURRENT}/archive", "", {})])

    def test_legacy_uncertain_buried_or_prefix_identity_refuses(self) -> None:
        initial = self.table.read_bytes()
        for content in (b"intent: old role-only evidence\n", handover(OLD), handover(CURRENT[:8]),
                        f"intent: quoted metadata\nsession: {CURRENT}\n".encode()):
            with self.subTest(content=content):
                self.table.write_bytes(initial)
                self.stub.requests.clear()
                legacy = self.write_handover(CURRENT, body=content, legacy=True)
                self.assert_refused(CURRENT)
                self.assertEqual(legacy.read_bytes(), content)
                self.assertFalse((self.stream / f"handover/worker/{CURRENT}.md").exists())

    def test_canonical_identity_mismatch_cannot_fall_back_to_legacy(self) -> None:
        self.write_handover(CURRENT, body=handover(OLD))
        self.write_handover(CURRENT, legacy=True)
        self.assert_refused(CURRENT)

    def test_empty_invalid_utf8_and_binary_canonical_artifacts_refuse(self) -> None:
        initial = self.table.read_bytes()
        for content in (b" \n", f"session: {CURRENT}\n".encode(), handover(CURRENT, "\x00\n"), handover(CURRENT) + b"\xff"):
            with self.subTest(content=content):
                self.table.write_bytes(initial)
                self.stub.requests.clear()
                self.write_handover(CURRENT, body=content)
                self.write_handover(CURRENT, legacy=True)
                self.assert_refused(CURRENT)

    def test_legacy_symlink_is_not_handover_evidence(self) -> None:
        outside = self.tmp / "outside.md"
        outside.write_bytes(handover(CURRENT))
        (self.stream / "handover/worker.md").symlink_to(outside)
        self.assert_refused("symlink")
        self.assertEqual(outside.read_bytes(), handover(CURRENT))

    def test_canonical_role_directory_symlink_refuses_without_touching_target(self) -> None:
        outside = self.tmp / "outside-handover"
        outside.mkdir()
        artifact = outside / f"{CURRENT}.md"
        artifact.write_bytes(handover(CURRENT))
        (self.stream / "handover/worker").symlink_to(outside, target_is_directory=True)
        self.write_handover(CURRENT, legacy=True)
        self.assert_refused("symlink")
        self.assertEqual(artifact.read_bytes(), handover(CURRENT))

    def test_duplicate_recorded_session_identity_refuses_compatibility(self) -> None:
        self.table.write_text(HEADER + self.row(CURRENT, "worker", "active") + self.row(CURRENT, "review", "done"))
        self.write_handover(CURRENT, legacy=True)
        self.write_handover(CURRENT, "review", legacy=True)
        self.assert_refused("ambiguous recorded session identity")

    def test_unsafe_session_cannot_escape_handover_directory(self) -> None:
        self.table.write_text(HEADER + self.row("../escape", "worker", "active"))
        self.write_handover(CURRENT, body=handover("../escape"), legacy=True)
        self.assert_refused("invalid handover session")

    def test_busy_close_retry_commits_both_validated_session_artifacts(self) -> None:
        self.table.write_text(HEADER + self.row(COORD, "coordinator", "active")
                              + self.row(CURRENT, "worker", "active") + self.row(OTHER, "review", "done"))
        first = self.write_handover(CURRENT)
        second = self.write_handover(OTHER, "review")
        self.write_handover(CURRENT, legacy=True)
        self.write_handover(OTHER, "review", legacy=True)
        self.stub.set_routes([("POST", f"/api/sessions/{OTHER}/archive", 409, {"error": "Stop current session activity before archiving"})])
        result = self.run_streams("close", "etl")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Stop current session activity", result.stderr)
        self.assertIn(f"{CURRENT}\tworker", self.table.read_text())
        self.assertEqual(self.table.read_text().splitlines()[2].split("\t")[8], "archived")
        self.stub.requests.clear()
        self.stub.set_routes([])
        result = self.run_streams("close", "etl")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.stub.requests, [("POST", f"/api/sessions/{OTHER}/archive", "", {})])
        self.assertEqual(git_blob(self.stream, f"HEAD:handover/worker/{CURRENT}.md"), first.read_bytes())
        self.assertEqual(git_blob(self.stream, f"HEAD:handover/review/{OTHER}.md"), second.read_bytes())
        self.assertNotIn("handover/worker.md", git(self.stream, self.env, "ls-tree", "-r", "--name-only", "HEAD").splitlines())

    def test_owned_evidence_reference_survives_helper_output_removal(self) -> None:
        helper_output = self.fx.beta / "helper-output.txt"
        helper_output.write_bytes(b"tiny exact tool result\r\n")
        owned = self.fx.alpha_wt / "reports" / "tool-result.txt"
        owned.parent.mkdir()
        shutil.copyfile(helper_output, owned)
        proof = handover(CURRENT, f"intent: retain required tool evidence\nartifact: {owned}\nsource: disposable beta helper\n")
        self.write_handover(CURRENT, body=proof)
        before = git(self.fx.alpha_wt, self.env, "status", "--porcelain")
        helper_output.unlink()
        result = self.run_streams("close", "etl")
        self.assertEqual(result.returncode, 0, result.stderr)
        committed = git_blob(self.stream, f"HEAD:handover/worker/{CURRENT}.md")
        self.assertEqual(committed, proof)
        reference = next(line.removeprefix("artifact: ") for line in committed.decode().splitlines() if line.startswith("artifact: "))
        self.assertEqual(Path(reference).read_bytes(), b"tiny exact tool result\r\n")
        self.assertFalse(helper_output.exists())
        self.assertEqual(git(self.fx.alpha_wt, self.env, "status", "--porcelain"), before)
