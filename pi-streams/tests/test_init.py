"""pi-streams init writes an index and leaves it alone on the next run."""
from __future__ import annotations

import json

from support import EngineCase, git, pi_stack_revision, snapshot


def expected_toml(
    root: str,
    revision: str,
    worktrees_dir: str,
    repos: list[tuple[str, str, list[tuple[str, str]]]],
    url: str = "http://127.0.0.1:8504",
    model: str = "openai-codex/gpt-6-astra",
    thinking: str = "xhigh",
) -> str:
    lines = [
        "[project]",
        'name = "proj"',
        f'root = "{root}"',
        f'pi_web_url = "{url}"',
        f'worktrees_dir = "{worktrees_dir}"',
        f'pi_stack_revision = "{revision}"',
        "",
        "[coordinator]",
        f'model = "{model}"',
        f'thinking = "{thinking}"',
        "",
        "[threads]",
        f'model = "{model}"',
        f'thinking = "{thinking}"',
        "",
        "[caps]",
        "warm_context_tokens = 60000",
        "warm_idle_hours = 6",
        "thread_handover_tokens = 150000",
        "steer_queue_minutes = 10",
        "",
    ]
    for name, path, worktrees in repos:
        lines.append("[[repos]]")
        lines.append(f'name = "{name}"')
        lines.append(f'path = "{path}"')
        lines.append("worktrees = [")
        for wt_path, branch in worktrees:
            lines.append(f'  {{ path = "{wt_path}", branch = "{branch}" }},')
        lines.append("]")
        lines.append("")
    return "\n".join(lines)


class InitTests(EngineCase):
    def test_init_writes_the_index_and_does_not_make_streams_a_git_repo(self) -> None:
        before = {
            "alpha": git(self.fx.alpha, self.env, "status", "--porcelain"),
            "beta": git(self.fx.beta, self.env, "status", "--porcelain"),
            "gamma": git(self.fx.gamma, self.env, "status", "--porcelain"),
        }
        proc = self.run_streams("init", str(self.root), "-y")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, f"{self.index.resolve()}\n")
        self.assertEqual(self.stub.requests, [])
        root = str(self.root.resolve())
        alpha = str(self.fx.alpha.resolve())
        beta = str(self.fx.beta.resolve())
        gamma = str(self.fx.gamma.resolve())
        text = self.project_file.read_text(encoding="utf-8")
        self.assertEqual(
            text,
            expected_toml(
                root,
                pi_stack_revision(),
                str((self.root / ".worktrees").resolve()),
                [
                    ("alpha", alpha, [(str(self.fx.alpha_wt.resolve()), "feat-a")]),
                    ("beta", beta, [(str(self.fx.beta_wt.resolve()), "x")]),
                    ("gamma", gamma, [(str(self.fx.gamma_wt.resolve()), "g")]),
                ],
            ),
        )
        self.assertEqual(text.count("[[repos]]"), 3)
        self.assertNotIn('name = "notes"', text)
        self.assertNotIn('name = "alpha-wt"', text)
        self.assertNotIn('name = "streams"', text)
        self.assertNotIn("remote = ", text)
        self.assertNotIn("home = ", text)
        self.assertEqual((self.index / "streams.tsv").read_text(encoding="utf-8"), "id\tpath\tproject\n")
        self.assertEqual((self.index / "ALERTS").read_bytes(), b"")
        self.assertFalse((self.index / ".git").exists())
        self.assertFalse((self.home / ".git").exists())
        self.assertEqual(
            (self.xdg / "pi-streams" / "homes").read_text(encoding="utf-8"),
            str(self.index.resolve()) + "\n",
        )
        self.assertEqual((self.fx.notes / "n.txt").read_bytes(), b"note\n")
        self.assertEqual(git(self.fx.alpha, self.env, "status", "--porcelain"), before["alpha"])
        self.assertEqual(git(self.fx.beta, self.env, "status", "--porcelain"), before["beta"])
        self.assertEqual(git(self.fx.gamma, self.env, "status", "--porcelain"), before["gamma"])

    def test_second_init_changes_nothing(self) -> None:
        first = self.run_streams("init", str(self.root), "-y")
        self.assertEqual(first.returncode, 0, first.stderr)
        before = snapshot(self.index)
        registry = (self.xdg / "pi-streams" / "homes").read_bytes()
        second = self.run_streams("init", str(self.root), "-y")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(snapshot(self.index), before)
        self.assertEqual((self.xdg / "pi-streams" / "homes").read_bytes(), registry)
        self.assertFalse((self.home / ".git").exists())

    def test_flags_set_the_answers(self) -> None:
        proc = self.run_streams(
            "init",
            str(self.root),
            "--pi-web-url",
            "http://127.0.0.1:9999",
            "--coordinator-model",
            "acme/widget",
            "--coordinator-thinking",
            "low",
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        text = self.project_file.read_text(encoding="utf-8")
        self.assertIn('pi_web_url = "http://127.0.0.1:9999"', text)
        self.assertEqual(text.count('model = "acme/widget"'), 2)
        self.assertEqual(text.count('thinking = "low"'), 2)
        self.assertNotIn("gpt-6-astra", text)
        self.assertNotIn("xhigh", text)
        self.assertNotIn("remote = ", text)

    def test_pi_web_url_comes_from_config(self) -> None:
        config = self.user_home / ".config" / "pi-web"
        config.mkdir(parents=True)
        (config / "config.json").write_text(
            json.dumps({"host": "127.0.0.1", "port": 9999}),
            encoding="utf-8",
        )
        proc = self.run_streams("init", str(self.root))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        text = self.project_file.read_text(encoding="utf-8")
        self.assertIn('pi_web_url = "http://127.0.0.1:9999"', text)

    def test_rerun_refreshes_repos_and_keeps_answers(self) -> None:
        first = self.run_streams("init", str(self.root), "-y")
        self.assertEqual(first.returncode, 0, first.stderr)
        path = self.project_file
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                'pi_web_url = "http://127.0.0.1:8504"',
                'pi_web_url = "http://127.0.0.1:9999"',
            ),
            encoding="utf-8",
        )
        extra = self.root / "alpha-wt-b"
        git(self.fx.alpha, self.env, "branch", "feat-b")
        git(self.fx.alpha, self.env, "worktree", "add", str(extra), "feat-b")
        second = self.run_streams("init", str(self.root), "-y")
        self.assertEqual(second.returncode, 0, second.stderr)
        text = path.read_text(encoding="utf-8")
        self.assertIn('pi_web_url = "http://127.0.0.1:9999"', text)
        self.assertNotIn("http://127.0.0.1:8504", text)
        self.assertIn('branch = "feat-b"', text)
        self.assertIn(str(extra.resolve()), text)
        self.assertIn('model = "openai-codex/gpt-6-astra"', text)


if __name__ == "__main__":
    unittest.main()
