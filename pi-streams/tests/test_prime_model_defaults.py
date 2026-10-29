"""Behavioral role defaults at the actual public native create boundary."""
from pathlib import Path
from prime_support import PrimeCase, project
from engine.prime import PrimeClient, create_stream_session, create_worker_session
from engine.threads import spawn_prime_worker, load_threads
from stub_prime import StubPrime


class RoleDefaultsTests(PrimeCase):
    def native(self, stub, request):
        command = request["command"]
        if command["type"] == "create":
            self.created = command["config"]
            self.serial = getattr(self, "serial", 0) + 1
            self.native_identity = {"sessionId": f"new-worker-{self.serial}", "activeSessionId": f"new-route-{self.serial}"}
            data = self.native_identity
        elif command["type"] == "get_connection_state":
            data = {**self.native_identity, "cwd": self.created["cwd"],
                    "model": {"provider": self.created["provider"], "id": self.created["model"]}, "thinkingLevel": self.created["thinking"]}
        elif command["type"] == "get_messages":
            data = {"messages": []}
        else:
            data = None
        return stub.response(request, data)

    def test_omitted_stream_and_direct_worker_settings_reach_native_create(self):
        with StubPrime(self.native) as stub, PrimeClient(stub.path) as client:
            create_stream_session(client, self.stream)
            self.assertEqual(self.created, {"cwd": str(self.stream), "provider": "openai-codex", "model": "gpt-6.1-sol", "thinking": "xhigh"})
            create_worker_session(client, self.root)
            self.assertEqual(self.created, {"cwd": str(self.root), "provider": "openai-codex", "model": "gpt-6-luna", "thinking": "xhigh"})

    def test_omitted_worker_and_reviewer_settings_cover_actual_handover_kickoff(self):
        source = self.active()
        for reviewer in (False, True):
            product = self.root / ("review" if reviewer else "product")
            product.mkdir()
            project.git(product, "init")
            project.git(product, "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "--allow-empty", "-m", "fixture")
            with StubPrime(self.native) as stub, PrimeClient(stub.path) as client:
                spawn_prime_worker(client, self.stream, worktree=product, work="Check whole request", original_entries=[source], poteto_path="/process/poteto/SKILL.md", reviewer=reviewer)
            self.assertEqual(self.created, {"cwd": str(product), "provider": "openai-codex", "model": "gpt-6-luna", "thinking": "xhigh"})
            prompt = next(r["command"]["message"] for r in stub.requests if r["command"]["type"] == "prompt_and_wait")
            self.assertIn("Context handover for clean worker", prompt)
            self.assertIn('Read the installed process entry at "/process/poteto/SKILL.md"', prompt)
            self.assertNotIn("Current files for stream", prompt)
            self.assertEqual("Review the handed-over result adversarially" in prompt, reviewer)
            self.assertEqual(load_threads(self.stream / "threads.tsv")[-1].model, "openai-codex/gpt-6-luna")
            self.assertFalse((product / "STATE.md").exists())

    def test_explicit_per_role_arguments_override_defaults(self):
        with StubPrime(self.native) as stub, PrimeClient(stub.path) as client:
            create_stream_session(client, self.stream, "custom/stream", "high")
            self.assertEqual((self.created["provider"], self.created["model"], self.created["thinking"]), ("custom", "stream", "high"))
            create_worker_session(client, self.root, "custom/worker", "low")
            self.assertEqual((self.created["provider"], self.created["model"], self.created["thinking"]), ("custom", "worker", "low"))

    def test_registered_project_role_settings_are_independent_and_arguments_win(self):
        from engine.install_prime import prepare_project
        prefix = self.root / "installation"
        prefix.mkdir()
        config = prepare_project(prefix, prefix / "project", "custom/coordinator", "high", 12, prefix / "poteto", worker_model="custom/worker", worker_thinking="low")
        stream = project.create_stream(prefix / "index", config, "configured", backend="prime")
        project.write_prime_settings(stream, 12)
        with StubPrime(self.native) as stub, PrimeClient(stub.path) as client:
            create_stream_session(client, stream)
            self.assertEqual((self.created["provider"], self.created["model"], self.created["thinking"]), ("custom", "coordinator", "high"))
            create_stream_session(client, stream, thinking="medium")
            self.assertEqual((self.created["model"], self.created["thinking"]), ("coordinator", "medium"))
        self.assertEqual(project.load_project(prefix / "index/projects/project.toml").threads, project.ModelSettings("custom/worker", "low"))
        source = __import__("engine.state", fromlist=["save_message"]).save_message(stream, text="Check fixture", command_id="00000000-0000-0000-0000-000000000002", session_id="fixture", sender="operator", send_as="steer")["entry"]
        product = prefix / "product"
        product.mkdir()
        project.git(product, "init")
        project.git(product, "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "--allow-empty", "-m", "fixture")
        with StubPrime(self.native) as stub, PrimeClient(stub.path) as client:
            spawn_prime_worker(client, stream, worktree=product, work="Check", original_entries=[source], poteto_path="/poteto")
            self.assertEqual((self.created["model"], self.created["thinking"]), ("worker", "low"))
            spawn_prime_worker(client, stream, worktree=product, work="Check", original_entries=[source], poteto_path="/poteto", model="override/worker", thinking="medium")
            self.assertEqual((self.created["provider"], self.created["model"], self.created["thinking"]), ("override", "worker", "medium"))
