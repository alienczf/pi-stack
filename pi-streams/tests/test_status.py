"""pi-streams status --json is a stable document."""
from __future__ import annotations

from support import EngineCase

STATUS_JSON = """\
{
  "streams": [
    {
      "id": "etl",
      "ratified": false,
      "coordinator": {
        "session": "coord-1",
        "isStreaming": false,
        "contextUsage": {
          "tokens": 1200
        },
        "model": "gpt-6-astra",
        "thinkingLevel": "xhigh",
        "cost": 2
      },
      "threads": {
        "active": 1,
        "waiting_quota": 0,
        "done": 0,
        "archived": 1
      },
      "coordinatorCostShare": 0.5
    }
  ]
}
"""

HEADER = "session\trole\trepo\tworktree\tbranch\tbase\tmodel\tthinking\tstatus\tstarted\n"
COORD = "coord-1\tcoordinator\t\t/wt\t\t\topenai-codex/gpt-6-astra\txhigh\tactive\t2026-10-06T00:00:00Z\n"
THREAD_ACTIVE = "thread-1\tdatapull\talpha\t/wt/t\tstream/etl/datapull\tabc\topenai-codex/gpt-6-astra\txhigh\tactive\t2026-10-06T00:00:00Z\n"
THREAD_ARCHIVED = "thread-2\treview\talpha\t/wt/r\tstream/etl/review\tabc\topenai-codex/gpt-6-astra\txhigh\tarchived\t2026-10-06T00:00:00Z\n"
OTHER = "other-coord\tcoordinator\t\t/wt\t\t\topenai-codex/gpt-6-astra\txhigh\tactive\t2026-10-06T00:00:00Z\n"


def live(sid: str, cost: int, tokens: int = 10) -> dict[str, object]:
    return {
        "sessionId": sid,
        "isStreaming": False,
        "contextUsage": {"tokens": tokens},
        "model": {"provider": "openai-codex", "id": "gpt-6-astra"},
        "thinkingLevel": "xhigh",
        "cost": cost,
    }


class StatusTests(EngineCase):
    def test_status_json_literal(self) -> None:
        proc = self.run_streams("init", str(self.root), "-y")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        etl = self.home / "etl"
        etl.mkdir()
        (etl / "STREAM.md").write_text("ratified: no\n", encoding="utf-8")
        (etl / "threads.tsv").write_text(HEADER + COORD + THREAD_ACTIVE + THREAD_ARCHIVED, encoding="utf-8")
        other = self.home / "other"
        other.mkdir()
        (other / "STREAM.md").write_text("ratified: yes\n", encoding="utf-8")
        (other / "threads.tsv").write_text(HEADER + OTHER, encoding="utf-8")
        self.stub.set_routes([
            ("GET", "/api/sessions/coord-1/status", 200, live("coord-1", 2, tokens=1200)),
            ("GET", "/api/sessions/thread-1/status", 200, live("thread-1", 4)),
            ("GET", "/api/sessions/thread-2/status", 200, live("thread-2", 1)),
        ])
        got = self.run_streams("status", "etl", "--json")
        self.assertEqual(got.returncode, 0, got.stderr)
        self.assertEqual(got.stdout, STATUS_JSON)
        self.assertEqual(
            [path for _method, path, _query, _body in self.stub.requests],
            ["/api/sessions/coord-1/status", "/api/sessions/thread-1/status"],
        )
        text = self.run_streams("status", "etl")
        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertIn("coord-1", text.stdout)
        self.assertNotIn("other", text.stdout)


if __name__ == "__main__":
    unittest.main()
