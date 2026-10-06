"""pi-streams init writes a home and leaves it alone on the next run."""
from __future__ import annotations

import json

from support import EngineCase, git, pi_stack_revision, snapshot


def expected_toml(
    root: str,
    home: str,
    revision: str,
    worktrees_dir: str,
    repos: list[tuple[str, str, list[tuple[str, str]]]],
    url: str = "http://127.0.0.1:8504",
    remote: str = "",
    model: str = "openai-codex/gpt-6-astra",
    thinking: str = "xhigh",
) -> str:
    lines = [
        "[project]",
        'name = "proj"',
        f'root = "{root}"',
        f'home = "{home}"',
        f'pi_web_url = "{url}"',
        f'remote = "{remote}"',
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
    def test_init_writes_project_toml_registry_and_one_commit(self) -> None:
        before = {
            "alpha": git(self.fx.alpha, self.env, "status", "--porcelain"),
            "beta": git(self.fx.beta, self.env, "status", "--porcelain"),
            "gamma": git(self.fx.gamma, self.env, "status", "--porcelain"),
        }
        proc = self.run_streams("init", str(self.root), "-y")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.stub.requests, [])
        home = str(self.home.resolve())
        root = str(self.root.resolve())
        alpha = str(self.fx.alpha.resolve())
        beta = str(self.fx.beta.resolve())
        gamma = str(self.fx.gamma.resolve())
        text = (self.home / "project.toml").read_text(encoding="utf-8")
        self.assertEqual(
            text,
            expected_toml(
                root,
                home,
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
        self.assertEqual(
            (self.home / "context" / "README.md").read_text(encoding="utf-8"),
            "# Shared context\n"
            "\n"
            f"alpha\t{alpha}\t{alpha}/AGENTS.md\n"
            f"beta\t{beta}\n"
            f"gamma\t{gamma}\n",
        )
        template = (self.home / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("never write product code", template)
        self.assertEqual(
            (self.xdg / "pi-streams" / "homes").read_text(encoding="utf-8"),
            home + "\n",
        )
        self.assertEqual(git(self.home, self.env, "rev-list", "--count", "HEAD").strip(), "1")
        self.assertEqual(git(self.home, self.env, "log", "-1", "--format=%s").strip(), "pi-streams init")
        self.assertEqual(git(self.home, self.env, "status", "--porcelain"), "")
        self.assertEqual((self.notes_bytes()), b"note\n")
        self.assertEqual(git(self.fx.alpha, self.env, "status", "--porcelain"), before["alpha"])
        self.assertEqual(git(self.fx.beta, self.env, "status", "--porcelain"), before["beta"])
        self.assertEqual(git(self.fx.gamma, self.env, "status", "--porcelain"), before["gamma"])

    def notes_bytes(self) -> bytes:
        return (self.fx.notes / "n.txt").read_bytes()

    def test_second_init_changes_nothing(self) -> None:
        first = self.run_streams("init", str(self.root), "-y")
        self.assertEqual(first.returncode, 0, first.stderr)
        before = snapshot(self.home)
        head = git(self.home, self.env, "rev-parse", "HEAD")
        registry = (self.xdg / "pi-streams" / "homes").read_bytes()
        second = self.run_streams("init", str(self.root), "-y")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(snapshot(self.home), before)
        self.assertEqual(git(self.home, self.env, "rev-parse", "HEAD"), head)
        self.assertEqual(git(self.home, self.env, "status", "--porcelain"), "")
        self.assertEqual(git(self.home, self.env, "rev-list", "--count", "HEAD").strip(), "1")
        self.assertEqual((self.xdg / "pi-streams" / "homes").read_bytes(), registry)

    def test_edited_agents_survives(self) -> None:
        first = self.run_streams("init", str(self.root), "-y")
        self.assertEqual(first.returncode, 0, first.stderr)
        agents = self.home / "AGENTS.md"
        agents.write_text("EDITED by ZF\n", encoding="utf-8")
        second = self.run_streams("init", str(self.root), "-y")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(agents.read_text(encoding="utf-8"), "EDITED by ZF\n")

    def test_flags_set_the_answers(self) -> None:
        proc = self.run_streams(
            "init",
            str(self.root),
            "--pi-web-url",
            "http://127.0.0.1:9999",
            "--remote",
            "https://example.test/streams.git",
            "--coordinator-model",
            "acme/widget",
            "--coordinator-thinking",
            "low",
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        text = (self.home / "project.toml").read_text(encoding="utf-8")
        self.assertIn('pi_web_url = "http://127.0.0.1:9999"', text)
        self.assertIn('remote = "https://example.test/streams.git"', text)
        self.assertEqual(text.count('model = "acme/widget"'), 2)
        self.assertEqual(text.count('thinking = "low"'), 2)
        self.assertNotIn("gpt-6-astra", text)
        self.assertNotIn("xhigh", text)
        self.assertEqual(
            git(self.home, self.env, "remote", "get-url", "origin").strip(),
            "https://example.test/streams.git",
        )

    def test_init_keeps_an_origin_that_is_not_the_remote(self) -> None:
        self.home.mkdir()
        git(self.home, self.env, "init", "--quiet")
        git(self.home, self.env, "remote", "add", "origin", "https://example.test/other.git")
        proc = self.run_streams("init", str(self.root), "--remote", "https://example.test/streams.git", "-y")
        self.assertEqual(
            (proc.returncode, proc.stderr.splitlines()[-1]),
            (1, "origin is https://example.test/other.git, but project.toml names remote https://example.test/streams.git"),
        )
        self.assertEqual(
            git(self.home, self.env, "remote", "get-url", "origin").strip(),
            "https://example.test/other.git",
        )

    def test_pi_web_url_comes_from_config(self) -> None:
        config = self.user_home / ".config" / "pi-web"
        config.mkdir(parents=True)
        (config / "config.json").write_text(
            json.dumps({"host": "127.0.0.1", "port": 9999}),
            encoding="utf-8",
        )
        proc = self.run_streams("init", str(self.root))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        text = (self.home / "project.toml").read_text(encoding="utf-8")
        self.assertIn('pi_web_url = "http://127.0.0.1:9999"', text)

    def test_rerun_refreshes_repos_and_keeps_answers(self) -> None:
        first = self.run_streams("init", str(self.root), "-y")
        self.assertEqual(first.returncode, 0, first.stderr)
        path = self.home / "project.toml"
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
