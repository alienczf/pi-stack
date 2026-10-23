"""Fresh streams expose the implemented STATE contract, not retired planning files."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest import mock

from support import EngineCase, ROOT
from test_new import status_body
from test_state_log import PREFIX

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine import StreamsError, artifacts, project, threads


class GeneratedStateContractTests(EngineCase):
    def setUp(self) -> None:
        super().setUp()
        result = self.run_streams("init", str(self.root), "-y")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.stub.set_routes([
            ("GET", "/api/sessions", 200, []),
            ("POST", "/api/sessions", 200, {"id": "coord-contract"}),
            ("GET", "/api/sessions/coord-contract/status", 200, status_body("coord-contract")),
            ("POST", "/api/sessions/coord-contract/prompt", 200, {"accepted": True}),
        ])
        result = self.run_streams("new", "contract")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.stream = self.home / "contract"

    def test_new_stream_has_only_current_state_seeds_and_is_explicitly_unratified(self) -> None:
        state = artifacts.parse_state((self.stream / "STATE.md").read_bytes())
        self.assertEqual(state.source[state.authority.start:state.authority.end], b"ratified: no\n")
        self.assertEqual(state.source[state.log.body.start:], b"")
        self.assertEqual([state.goals.name, state.rules.name, state.log.name], ["Goals", "Rules", "Log"])
        self.assertEqual(project.load_stream_config(self.stream / "stream.toml").state_schema, 1)
        for retired in ("STREAM.md", "DECISIONS.md", "GOAL.md", "ACTIONS.md", "TODO.md", "PLAN.md"):
            self.assertFalse((self.stream / retired).exists(), retired)
        self.assertTrue((self.stream / "history/.gitkeep").is_file())
        self.assertTrue((self.stream / "failures/.gitkeep").is_file())

    def test_generated_append_and_objective_commands_work_without_manual_schema_repair(self) -> None:
        body = self.tmp / "body.md"
        body.write_text("Completed the private fixture step.\n")
        result = self.run_streams("state", "append", "contract", "--subject", "Private fixture complete", "--body-file", str(body), "--request-id", "generated-entry", "--home", str(self.index))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"occurrence": 1, "request_id": "generated-entry"})
        before = (self.stream / "STATE.md").read_bytes()
        body.write_text("Check the generated fixture next.\n")
        result = self.run_streams("state", "objective", "contract", "--body-file", str(body), "--home", str(self.index))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"changed": True})
        self.assertEqual((self.stream / "STATE.md").read_bytes().split(b"## Log\n", 1)[1], before.split(b"## Log\n", 1)[1])

    def test_generated_role_loads_two_stream_files_and_uses_implemented_operations(self) -> None:
        role = (self.stream / "AGENTS.md").read_text()
        self.assertIn("1. Read AGENTS.md and STATE.md.", role)
        self.assertIn("On demand", role)
        self.assertIn("context/README.md", role)
        self.assertIn("Never read engine-only", role)
        self.assertIn("Do not use TODO.md or PLAN.md", role)
        self.assertIn("pi-streams state append", role)
        self.assertIn("pi-streams state objective", role)
        self.assertIn("never prune or rotate", role)
        for stale in ("Read STREAM.md", "Read context/README.md every turn", "continue on the default", "matching checks/ script passes", "Rewrite STATE.md before ending"):
            self.assertNotIn(stale, role)

    def test_worker_brief_uses_state_and_disables_overlay_planning(self) -> None:
        brief = threads.render_brief(stream="contract", stream_dir=str(self.stream), role="worker", repo="alpha", worktree=str(self.fx.alpha_wt), branch="feat-a", base="abc", note="Only the assigned slice.")
        self.assertIn(str(self.stream / "STATE.md"), brief)
        self.assertNotIn(str(self.stream / "STREAM.md"), brief)
        self.assertIn("Do not use TODO.md or PLAN.md", brief)
        self.assertIn("On demand", brief)
        self.assertIn("Only the assigned slice.", brief)
        self.assertIn(str(self.fx.alpha_wt), brief)
        self.assertIn("handover/worker.md", brief)

    def test_canonical_status_reads_first_line_authority_and_opaque_log_without_registry_reads(self) -> None:
        source = PREFIX.replace(b"ratified: ZF notice 42, charter v3", b"ratified: no", 1)
        (self.stream / "STATE.md").write_bytes(source)
        config = project.load_stream_config(self.stream / "stream.toml")
        config.state_schema = 1
        project.save_stream_config(self.stream, config)
        (self.stream / "STREAM.md").unlink(missing_ok=True)
        artifacts.append_log(self.stream, "2026-10-23T05:00:00Z", "A historical example", "## Rules\nratified: yes\n```", request_id="example")
        metadata = (self.stream / "log/tick-state.json").read_bytes()
        result = self.run_streams("status", "contract", "--json", "--home", str(self.index))
        self.assertEqual(result.returncode, 0, result.stderr)
        view = json.loads(result.stdout)["streams"][0]
        self.assertIs(view["ratified"], False)
        self.assertEqual(view["path"], str(self.stream))
        self.assertEqual(view["threadSessions"], [])
        self.assertEqual((self.stream / "log/tick-state.json").read_bytes(), metadata)
        (self.stream / "STATE.md").write_bytes((self.stream / "STATE.md").read_bytes().replace(b"ratified: no\n", b"ratified: 2026-10-23 ZF confirmed\n", 1))
        result = self.run_streams("status", "contract", "--json", "--home", str(self.index))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIs(json.loads(result.stdout)["streams"][0]["ratified"], True)

    def test_canonical_replacement_pickup_uses_paths_and_the_shared_current_goal(self) -> None:
        config = project.load_stream_config(self.stream / "stream.toml")
        config.state_schema = 1
        project.save_stream_config(self.stream, config)
        (self.stream / "STATE.md").write_bytes(PREFIX)
        artifacts.update_current_objective(self.stream, "Resume the canonical fixture objective.")
        self.stub.requests.clear()
        self.stub.set_routes([
            ("GET", "/api/sessions", 200, []),
            ("POST", "/api/sessions", 200, {"id": "coord-next"}),
            ("GET", "/api/sessions/coord-next/status", 200, status_body("coord-next")),
            ("POST", "/api/sessions/coord-next/prompt", 200, {"accepted": True}),
        ])
        result = self.run_streams("rotate", "contract", "--home", str(self.index))
        self.assertEqual(result.returncode, 0, result.stderr)
        prompt = [body["text"] for method, path, query, body in self.stub.requests if path == "/api/sessions/coord-next/prompt"]
        self.assertEqual(len(prompt), 1)
        self.assertIn(str(self.stream / "AGENTS.md"), prompt[0])
        self.assertIn(str(self.stream / "STATE.md"), prompt[0])
        self.assertIn("Goal at pickup:\nResume the canonical fixture objective.", prompt[0])
        self.assertNotIn("STREAM.md", prompt[0])

    def test_status_does_not_repair_a_pending_artifact_operation(self) -> None:
        artifacts.append_log(self.stream, "2026-10-23T05:00:00Z", "Before read", "Completed.", request_id="pending-read")
        path = self.stream / "log/tick-state.json"
        data = json.loads(path.read_text())
        data["state_log"]["pending"] = {}
        path.write_text(json.dumps(data))
        before = path.read_bytes()
        source = (self.stream / "STATE.md").read_bytes()
        self.stub.requests.clear()
        result = self.run_streams("status", "contract", "--json", "--home", str(self.index))
        self.assertEqual(result.returncode, 1)
        self.assertIn("artifact operation pending", result.stderr)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual((self.stream / "STATE.md").read_bytes(), source)
        self.assertEqual(self.stub.requests, [])

    def test_stream_overlay_exception_preserves_the_nonstream_mappings(self) -> None:
        overlay = (ROOT / "overlay/AGENTS.md").read_text()
        sticky = (ROOT / "overlay/APPEND_SYSTEM.md").read_text()
        self.assertIn("Outside a pi-streams role", overlay)
        self.assertIn("`TodoWrite` is `TODO.md` in the working tree. Do not register a todo tool.", overlay)
        self.assertIn("Plan mode is `PLAN.md` in the working tree.", overlay)
        self.assertIn("Within a pi-streams role", overlay)
        self.assertIn("Do not use TODO.md or PLAN.md", overlay)
        self.assertIn("Outside a pi-streams role", sticky)
        self.assertIn("Within a pi-streams role", sticky)
        self.assertIn("Read `TODO.md` and `PLAN.md` in the working tree when they exist.", sticky)
        self.assertIn("Write progress in `TODO.md`.", sticky)

    def test_kickoff_uses_goals_rules_log_without_inventing_budget_or_acceptance_demands(self) -> None:
        kickoff = (ROOT / "skills/stream-kickoff/SKILL.md").read_text()
        self.assertIn("### North Star", kickoff)
        self.assertIn("### Current objective", kickoff)
        self.assertIn("### Charter", kickoff)
        self.assertIn("Goals", kickoff)
        self.assertIn("Rules", kickoff)
        self.assertIn("Log", kickoff)
        self.assertIn("context/README.md", kickoff)
        self.assertIn("pi-streams state append", kickoff)
        for stale in ("STREAM.md", "DECISIONS.md", "Get each cap as a number", "how much may it spend", "Name a script in `checks/` for each check", "stream.toml` names it"):
            self.assertNotIn(stale, kickoff)
        self.assertIn("explicitly", kickoff)

    def test_new_stream_schema_does_not_silently_convert_a_legacy_root(self) -> None:
        with mock.patch.dict(os.environ, self.env, clear=True):
            config = project.load_project(self.project_file)
            legacy = self.home / "legacy"
            legacy.mkdir()
            project.ensure_git(legacy)
            project.save_stream_config(legacy, project.StreamConfig(config.info.name, "old"))
            (legacy / "STATE.md").write_bytes(b"legacy owned state\n")
            with self.assertRaisesRegex(StreamsError, "schema mismatch"):
                project.create_stream(self.index, config, "legacy")
        self.assertEqual((legacy / "STATE.md").read_bytes(), b"legacy owned state\n")
