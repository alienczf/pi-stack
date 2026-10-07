"""init, new, thread spawn, status, and rotate against pi-web's real response shapes.

The shapes follow @jmfederico/pi-web 1.202607.3: SessionInfo from
POST /api/sessions and GET /api/sessions, SessionStatus from
GET /api/sessions/:id/status.
"""
from __future__ import annotations

import json
import unittest

from support import EngineCase, git

COORD_1 = "019a3c1e-7d2a-7c41-9e1b-0c7a5f2e9a01"
COORD_2 = "019a3c1e-91f0-7a2b-8c3d-4e5f6a7b8c02"
THREAD = "019a3c1f-02ab-7cde-9f01-23456789ab03"


def session_info(sid: str, cwd: str, *, message_count: int, archived: bool = False) -> dict[str, object]:
    info: dict[str, object] = {
        "id": sid,
        "path": f"/home/u/.pi/agent/sessions/{sid}.jsonl",
        "cwd": cwd,
        "created": "2026-10-06T10:00:00.000Z",
        "modified": "2026-10-06T10:05:00.000Z",
        "messageCount": message_count,
        "firstMessage": "",
    }
    if archived:
        info["archived"] = True
        info["archivedAt"] = "2026-10-06T11:00:00.000Z"
    else:
        info["persisted"] = True
    return info


def spawned(sid: str, cwd: str) -> dict[str, object]:
    info = session_info(sid, cwd, message_count=0)
    info["persisted"] = False
    return info


def session_status(sid: str, *, cost: float, tokens: int | None) -> dict[str, object]:
    return {
        "sessionId": sid,
        "persisted": True,
        "model": {
            "provider": "openai-codex",
            "id": "gpt-6-astra",
            "name": "GPT-6 Astra",
            "contextWindow": 400000,
            "reasoning": True,
        },
        "thinkingLevel": "xhigh",
        "isStreaming": False,
        "isCompacting": False,
        "isBashRunning": False,
        "pendingMessageCount": 0,
        "queuedMessages": [],
        "messageCount": 4,
        "tokens": {"input": 1200, "output": 300, "cacheRead": 0, "cacheWrite": 0, "total": 1500},
        "cost": cost,
        "contextUsage": {
            "tokens": tokens,
            "contextWindow": 400000,
            "percent": None if tokens is None else tokens / 4000,
        },
        "warnings": [],
    }


def configured(sid: str, status: dict[str, object]) -> list[tuple[str, str, int, object]]:
    return [
        ("POST", f"/api/sessions/{sid}/model", 200, {"provider": "openai-codex", "id": "gpt-6-astra"}),
        ("POST", f"/api/sessions/{sid}/thinking-level", 200, {"level": "xhigh"}),
        ("GET", f"/api/sessions/{sid}/status", 200, status),
        ("POST", f"/api/sessions/{sid}/prompt", 200, {"accepted": True}),
    ]


class ScenarioTests(EngineCase):
    def calls(self) -> list[tuple[str, str]]:
        return [(method, path) for method, path, _query, _body in self.stub.requests]

    def test_a_stream_from_init_to_rotation(self) -> None:
        init = self.run_streams("init", str(self.root), "-y")
        self.assertEqual(init.returncode, 0, init.stderr)
        stream = str((self.home / "etl").resolve())
        worktree = str((self.root / ".worktrees" / "alpha" / "etl-datapull").resolve())

        self.stub.requests.clear()
        self.stub.set_routes([
            ("GET", "/api/sessions", 200, []),
            ("POST", "/api/sessions", 200, spawned(COORD_1, stream)),
            *configured(COORD_1, session_status(COORD_1, cost=0, tokens=None)),
        ])
        new = self.run_streams("new", "etl")
        self.assertEqual(new.returncode, 0, new.stderr)
        self.assertEqual(new.stdout, f"http://127.0.0.1:8504\n{COORD_1}\n")
        self.assertEqual(self.stub.requests[-1][3], {"text": "/skill:stream-kickoff"})

        stream_md = self.home / "etl" / "STREAM.md"
        stream_md.write_text(stream_md.read_text(encoding="utf-8").replace("ratified: no", "ratified: 2026-10-06"), encoding="utf-8")

        self.stub.requests.clear()
        self.stub.set_routes([
            ("GET", "/api/sessions", 200, []),
            ("POST", "/api/sessions", 200, spawned(THREAD, worktree)),
            *configured(THREAD, session_status(THREAD, cost=0, tokens=None)),
        ])
        spawn = self.run_streams("thread", "spawn", "etl", "--repo", "alpha", "--role", "datapull")
        self.assertEqual(spawn.returncode, 0, spawn.stderr)
        self.assertEqual(spawn.stdout, f"{THREAD}\n")
        self.assertEqual(git(self.root / ".worktrees" / "alpha" / "etl-datapull", self.env, "branch", "--show-current"), "stream/etl/datapull\n")

        self.stub.requests.clear()
        self.stub.set_routes([
            ("GET", f"/api/sessions/{COORD_1}/status", 200, session_status(COORD_1, cost=0.5, tokens=None)),
            ("GET", f"/api/sessions/{THREAD}/status", 200, session_status(THREAD, cost=2.0, tokens=91000)),
        ])
        status = self.run_streams("status", "--json")
        self.assertEqual(status.returncode, 0, status.stderr)
        self.assertEqual(json.loads(status.stdout), {
            "streams": [{
                "id": "etl",
                "ratified": True,
                "coordinator": {
                    "session": COORD_1,
                    "isStreaming": False,
                    "contextUsage": {"tokens": None},
                    "model": "gpt-6-astra",
                    "thinkingLevel": "xhigh",
                    "cost": 0.5,
                },
                "threads": {"active": 1, "waiting_quota": 0, "done": 0, "archived": 0},
                "coordinatorCostShare": 0.25,
            }],
        })
        text = self.run_streams("status")
        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertEqual(
            text.stdout,
            f"etl\tratified=yes\t{COORD_1}\tstreaming=no\ttokens=-\tmodel=gpt-6-astra\tthinking=xhigh\t"
            "cost=0.5\tthreads=active=1,waiting_quota=0,done=0,archived=0\tshare=0.25\n",
        )

        self.stub.requests.clear()
        self.stub.set_routes([
            ("POST", f"/api/sessions/{COORD_1}/archive", 200, {"archived": True}),
            ("GET", "/api/sessions", 200, [session_info(COORD_1, stream, message_count=40, archived=True)]),
            ("POST", "/api/sessions", 200, spawned(COORD_2, stream)),
            *configured(COORD_2, session_status(COORD_2, cost=0, tokens=None)),
        ])
        rotate = self.run_streams("rotate", "etl")
        self.assertEqual(rotate.returncode, 0, rotate.stderr)
        self.assertEqual(rotate.stdout, f"http://127.0.0.1:8504\n{COORD_2}\n")
        self.assertEqual(self.calls(), [
            ("POST", f"/api/sessions/{COORD_1}/archive"),
            ("GET", "/api/sessions"),
            ("POST", "/api/sessions"),
            ("POST", f"/api/sessions/{COORD_2}/model"),
            ("POST", f"/api/sessions/{COORD_2}/thinking-level"),
            ("GET", f"/api/sessions/{COORD_2}/status"),
            ("POST", f"/api/sessions/{COORD_2}/prompt"),
        ])

        rows = (self.home / "etl" / "threads.tsv").read_text(encoding="utf-8").splitlines()
        self.assertEqual([row.split("\t")[:2] + [row.split("\t")[8]] for row in rows[1:]], [
            [COORD_1, "coordinator", "archived"],
            [THREAD, "datapull", "active"],
            [COORD_2, "coordinator", "active"],
        ])
        repo = self.home / "etl"
        self.assertEqual(git(repo, self.env, "log", "--format=%s").splitlines(), [
            "pi-streams rotate etl",
            "pi-streams thread spawn etl datapull",
            "pi-streams new etl",
        ])
        self.assertEqual(git(repo, self.env, "status", "--porcelain"), "")


if __name__ == "__main__":
    unittest.main()
