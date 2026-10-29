"""OFFLINE public-socket scenario for the assembled verifier, not native inference evidence."""
import json
import re
import subprocess
from dataclasses import replace

from engine import state
from engine.threads import load_threads


class OwnedFixtureProcess:
    returncode = None

    def poll(self):
        return self.returncode

    def wait(self):
        return self.returncode


class PocScenario:
    def __init__(self, root, mode="success"):
        self.root, self.mode = root, mode
        self.stream = root / "project/streams/one"
        self.product = root / "worktrees/one-product"
        self.native_path = root / "prime/agent/sessions/offline-stream.jsonl"
        self.pending_first = None
        self.delayed_steer = None
        self.parked = None
        self.nodes = []
        self.messages = {"stream-route": [], "worker-route": []}
        self.events = []
        self.marker = None
        self.paused = False
        self.compacted = False
        self.stream_state = self.connection("offline-stream", "stream-route", self.stream)
        self.worker_state = self.connection("offline-worker", "worker-route", self.product)
        self.worker_state["model"]["id"] = "gpt-6-luna"
        self.worker_state["sessionFile"] = str(root / "prime/agent/sessions/offline-worker.jsonl")
        self.process = OwnedFixtureProcess()
        self.stopped = False

    def connection(self, durable, routing, cwd):
        return {"sessionId": durable, "activeSessionId": routing, "cwd": str(cwd), "thinkingLevel": "xhigh",
                "model": {"provider": "openai-codex", "id": "gpt-6.1-sol"}, "isStreaming": False,
                "isCompacting": False, "isBashRunning": False, "contextUsage": {"percent": 0, "tokens": 0, "contextWindow": 500000},
                "leafId": None, "sessionFile": str(self.native_path)}

    def append_node(self, name, kind="message", **fields):
        entry = {"id": name, "parentId": self.stream_state["leafId"], "type": kind, **fields}
        self.nodes.append(entry)
        self.stream_state["leafId"] = name
        return entry

    def persist(self, *, omit_compact=False):
        self.native_path.parent.mkdir(parents=True, exist_ok=True)
        rows = [{"type": "session", "id": "offline-stream", "cwd": str(self.stream)},
                {"type": "model_change", "provider": "openai-codex", "modelId": "gpt-6.1-sol"},
                {"type": "thinking_level_change", "thinkingLevel": "xhigh"}]
        rows.extend(e for e in self.nodes if not (omit_compact and e["type"] == "compaction"))
        self.native_path.write_text("\n".join(json.dumps(e) for e in rows) + "\n")

    def checked_update(self, subject, *, review=False):
        current = state.check_state(self.stream)
        refs = [w.original_entry for w in current.goals.work]
        goals = replace(current.goals, north_star="Preserve the whole finite fixture intent", original_entry=refs[0],
                        objective="Review the finite fixture result", status="active",
                        work=tuple(replace(w, required="Marker, 2 + 3 = 5, answer.json and protected behavior") for w in current.goals.work))
        if self.mode == "waiting_for_verifier":
            if "worker" not in self.events:
                goals = replace(goals, status="waiting", work=tuple(replace(w, next=None, waiting_for="Verifier to dispatch clean worker and return its result; pi-stack compaction; verifier closing check.") for w in goals.work))
            else:
                goals = replace(goals, status=current.goals.status)
        body = {"findings": "Whole original intent and unresolved work retained"}
        if review:
            text = f"Adversarial review against {self.marker} at {self.product}. Verified original intent, answer 5 and protected.txt. No unsupported worker-plan claims replace the original. Uncertainty remains until the actual computed check."
            body = {"original_entries": refs, "media_type": "text/plain", "text": text, "sha256": state.sha256(text)}
        state.update_state(self.stream, expect=current.sha256, goals=goals, rules=None,
                           entry={"subject": subject, "body": body, "original_entries": refs})

    def worker_prompt(self, stub, request):
        self.events.append("worker")
        text = request["command"]["message"]
        assert text.startswith('Context handover for clean worker session "offline-worker".')
        assert "Current files for stream" not in text
        assert any(row.session == "offline-worker" for row in load_threads(self.stream / "threads.tsv"))
        assert any(worker["session"] == "offline-worker" for work in state.check_state(self.stream).goals.work for worker in work.workers)
        self.product.joinpath("answer.json").write_text(json.dumps({"marker": self.marker, "answer": 6 if self.mode == "worker_failure" else 5}) + "\n")
        result = subprocess.run(["python3", "check_fixture.py"], cwd=self.product, capture_output=True, text=True)
        if self.mode == "worker_failure":
            assert result.returncode != 0
            return stub.response(request, success=False, error="fixture worker check failed")
        assert result.returncode == 0, result.stderr
        summary = f"Worker observed {self.marker} at {self.product}; python3 check_fixture.py returned 0. Protected behavior retained; stream review and computed close still required."
        self.messages["worker-route"] = [{"role": "assistant", "content": [{"type": "text", "text": summary}]}]
        return stub.response(request, {"completed": True})

    def handle(self, stub, request):
        command = request["command"]
        kind = command["type"]
        self.events.append(kind)
        if kind == "create":
            native = self.stream_state if command["config"]["cwd"] == str(self.stream) else self.worker_state
            assert command["config"] == {"cwd": native["cwd"], "provider": "openai-codex", "model": "gpt-6.1-sol" if native is self.stream_state else "gpt-6-luna", "thinking": "xhigh"}
            if native is self.worker_state:
                from pathlib import Path
                path = Path(native["sessionFile"])
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('\n'.join(json.dumps(e) for e in ({"type": "session", "id": "offline-worker", "cwd": str(self.product)},
                    {"type": "model_change", "provider": "openai-codex", "modelId": "gpt-6-luna"}, {"type": "thinking_level_change", "thinkingLevel": "xhigh"})) + '\n')
            return stub.response(request, {"sessionId": native["sessionId"], "activeSessionId": native["activeSessionId"], "cwd": native["cwd"]})
        target = command.get("activeSessionId")
        native = self.worker_state if target in {"worker-route", "offline-worker"} else self.stream_state
        if kind == "get_connection_state":
            if native is self.stream_state and self.delayed_steer is not None:
                pending, self.delayed_steer = self.delayed_steer, None
                self.checked_update("Delayed native steer interpretation")
                self.stream_state["isStreaming"] = False
                self.append_node("native-delayed-steer")
                self.persist()
                self.events.append("delayed-steer-finished")
                return [stub.response(pending, {"completed": True}), stub.response(request, dict(native))]
            return stub.response(request, dict(native))
        if kind == "get_state":
            return stub.response(request, {"sessionId": native["sessionId"], "activeSessionId": native["activeSessionId"], "hasRunningSubagents": False})
        if kind == "get_queue":
            return stub.response(request, {"steering": [], "followUp": []})
        if kind == "get_messages":
            return stub.response(request, {"messages": self.messages[native["activeSessionId"]]})
        if kind == "get_session_tree":
            return stub.response(request, {"flatNodes": [{"entry": e} for e in self.nodes], "leafId": self.stream_state["leafId"]})
        if kind == "acquire_session_input_pause":
            assert "checked-save" in self.events
            self.paused = True
            return stub.response(request, {"pauseId": "fixture-pause"})
        if kind == "release_session_input_pause":
            self.events.append("release")
            if self.mode == "release_failure":
                return stub.response(request, success=False, error="fixture pause release refused")
            self.paused = False
            result = [stub.response(request, {"released": True})]
            if self.parked is not None and self.mode != "missing_resume_result":
                self.events.append("self-review")
                if self.mode not in {"missing_review", "save_review_without_resume_review"}:
                    self.checked_update("Native stream adversarial review during continuation", review=True)
                if self.mode == "changed_output_after_check":
                    path = self.product / "check_fixture.py"
                    path.write_text(path.read_text() + 'Path("answer.json").write_text(' + repr(json.dumps({"marker": self.marker, "answer": 6}) + "\n") + ')\n')
                self.events.append("resume-result")
                result.append(stub.response(self.parked, {"completed": True}))
                self.parked = None
            return result
        if kind == "compact":
            assert self.paused and "checked-save" in self.events
            if self.mode == "compact_failure":
                return stub.response(request, success=False, error="fixture direct compact refused")
            self.compacted = True
            summary = "Preserve whole originals, marker, clean worker identities, waits and current proof."
            self.append_node("native-compaction", "compaction", summary=summary)
            self.persist(omit_compact=self.mode == "missing_disk")
            self.stream_state["contextUsage"] = None
            return stub.response(request, {"summary": "wrong summary" if self.mode == "wrong_summary" else summary, "tokensBefore": 1000})
        if kind != "prompt_and_wait":
            raise AssertionError(f"unexpected public command {kind}")
        if native is self.worker_state:
            return self.worker_prompt(stub, request)
        text = command["message"]
        body = json.loads(text.split("Message body as JSON follows.\n", 1)[1].split("\n", 1)[0])
        if body.startswith("Finite PoC whole request."):
            self.marker = re.search(r"Marker (poc-[0-9a-f-]+)\.", body).group(1)
            self.pending_first = request
            if self.mode == "intake_failure":
                self.append_node("native-failed-input")
                self.persist()
                return stub.response(request, success=False, error="fixture native intake refused")
            self.checked_update("Native interpretation of original")
            self.append_node("native-first-input")
            self.stream_state.update(isStreaming=True, contextUsage={"percent": .2, "tokens": 1000, "contextWindow": 500000})
            self.persist()
            return None
        if body.startswith("Steer "):
            assert self.stream_state["isStreaming"] is True
            self.events.append("busy-steer")
            if self.mode == "delayed_steer_state":
                self.delayed_steer = request
                return stub.response(self.pending_first, {"completed": True})
            self.checked_update("Native interpretation of whole steer")
            self.stream_state["isStreaming"] = False
            self.append_node("native-steer-input")
            self.persist()
            self.messages["stream-route"] = [{"role": "assistant", "content": [{"type": "text", "text": "Whole inputs retained; no computed close yet."}]}]
            steer = stub.response(request, success=False, error="fixture native steer refused") if self.mode == "steer_failure" else stub.response(request, {"completed": True})
            return [stub.response(self.pending_first, {"completed": True}), steer]
        if body.startswith("Prepare this stream session for compaction."):
            if self.mode != "save_after_compact":
                self.checked_update("Native checked save before compact", review=self.mode == "save_review_without_resume_review")
                self.events.append("checked-save")
            self.append_node("native-save-input")
            self.persist()
            return stub.response(request, {"completed": True})
        if body.startswith("Compaction saved native entry "):
            assert self.paused and self.compacted
            self.events.append("resume-parked")
            self.parked = request
            self.append_node("native-resume-input")
            self.persist(omit_compact=self.mode == "missing_disk")
            return None
        raise AssertionError(f"unexpected stream body {body[:100]}")
