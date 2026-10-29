import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import project, state
from engine.prime import SessionIdentity


class PrimeCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="prime-unit-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.stream = self.root / "stream-one"
        self.stream.mkdir()
        project.git(self.stream, "init")
        project.copy_missing(project.templates_dir() / "prime", self.stream)
        project.save_stream_config(self.stream, project.StreamConfig("fixture", "", backend="prime"))
        project.write_prime_settings(self.stream, 50)
        header = (project.templates_dir() / "stream/threads.tsv").read_text()
        (self.stream / "threads.tsv").write_text(header + f"durable\tcoordinator\t\t{self.stream}\t\t\topenai-codex/gpt-6.1-sol\txhigh\tactive\t2026-10-23T00:00:00Z\n")
        self.identity = SessionIdentity("durable", "routing")
        self.connection = {"sessionId": "durable", "activeSessionId": "routing", "isStreaming": False,
                           "isCompacting": False, "isBashRunning": False, "leafId": "leaf-one"}

    def active(self):
        saved = state.save_message(self.stream, text="Implement A and verify B", command_id=str(uuid4()), session_id="durable", sender="operator", send_as="steer")
        current = state.check_state(self.stream)
        goals = replace(current.goals, objective="Implement the finite fixture", status="active",
                        work=tuple(replace(w, required="A and B", next="execute check") for w in current.goals.work))
        state.update_state(self.stream, expect=current.sha256, goals=goals, rules=None,
                           entry={"subject": "Interpret whole request", "body": {"findings": "A and B remain required"}, "original_entries": [saved["entry"]]})
        return saved["entry"]

    def handler(self, stub, request):
        kind = request["command"]["type"]
        data = {"get_connection_state": self.connection, "get_state": {"hasRunningSubagents": False},
                "get_queue": {"steering": [], "followUp": []}, "get_messages": {"messages": []}}.get(kind)
        return stub.response(request, data)
