"""New independent clean-worker and stream-chosen reviewer dispatch."""
from prime_support import PrimeCase, project, state
from engine.prime import PrimeClient
from engine.threads import spawn_prime_worker, load_threads
from stub_prime import StubPrime


class WorkerTests(PrimeCase):
    def test_symlink_worker_ancestor_is_refused_before_native_create(self):
        from engine import StreamsError
        source = self.active()
        product = self.root / "product"
        product.mkdir()
        project.git(product, "init")
        alias = self.root / "alias"
        alias.symlink_to(self.root, target_is_directory=True)
        with StubPrime(self.handler) as stub, PrimeClient(stub.path) as client:
            with self.assertRaisesRegex(StreamsError, "symlink"):
                spawn_prime_worker(client, self.stream, worktree=alias / "product", work="A", original_entries=[source],
                    poteto_path="/installed/poteto/SKILL.md", model="openai-codex/gpt-6.1-sol", thinking="xhigh")
        self.assertEqual(stub.requests, [])
        self.assertFalse((product / "STATE.md").exists())

    def test_pause_arriving_during_worker_creation_refuses_kickoff(self):
        from dataclasses import replace
        from engine import StreamsError
        source = self.active()
        worktree = self.root / "paused-product"
        worktree.mkdir()
        project.git(worktree, "init")
        project.git(worktree, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "--allow-empty", "-m", "init")
        def handler(stub, request):
            if request["command"]["type"] == "create":
                current = state.check_state(self.stream)
                state.update_state(self.stream, expect=current.sha256, goals=replace(current.goals, status="paused"), rules=None,
                    entry={"subject": "Operator pause during create", "body": {}, "original_entries": [source]})
                data = {"sessionId": "worker-durable", "activeSessionId": "worker-routing"}
            elif request["command"]["type"] == "get_connection_state":
                data = {"sessionId": "worker-durable", "activeSessionId": "worker-routing", "cwd": str(worktree), "thinkingLevel": "xhigh", "model": {"provider": "openai-codex", "id": "gpt-6.1-sol"}}
            elif request["command"]["type"] == "get_messages":
                data = {"messages": []}
            else:
                data = None
            return stub.response(request, data)
        with StubPrime(handler) as stub, PrimeClient(stub.path, timeout=1) as client:
            with self.assertRaisesRegex(StreamsError, "stale|paused|kickoff"):
                spawn_prime_worker(client, self.stream, worktree=worktree, work="Implement A", original_entries=[source],
                    poteto_path="/installed/poteto/SKILL.md", model="openai-codex/gpt-6.1-sol", thinking="xhigh")
        self.assertFalse(any(r["command"]["type"] == "prompt_and_wait" for r in stub.requests))
        self.assertEqual(state.check_state(self.stream).goals.status, "paused")
        self.assertEqual(state.check_state(self.stream).goals.work[0].original_entry, source)

    def test_clean_worker_and_optional_reviewer_keep_product_instructions(self):
        source = self.active()
        for reviewer in (False, True):
            worktree = self.root / ("review-worktree" if reviewer else "product-worktree")
            worktree.mkdir()
            project.git(worktree, "init")
            project.git(worktree, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "--allow-empty", "-m", "init")
            (worktree / "AGENTS.md").write_text("Keep native product instructions.\n")
            def handler(stub, request):
                kind = request["command"]["type"]
                if kind == "create":
                    self.assertEqual(request["command"]["config"]["cwd"], str(worktree))
                    data = {"sessionId": "worker-durable", "activeSessionId": "worker-routing"}
                elif kind == "get_connection_state":
                    data = {"sessionId": "worker-durable", "activeSessionId": "worker-routing", "cwd": str(worktree), "thinkingLevel": "xhigh", "model": {"provider": "openai-codex", "id": "gpt-6.1-sol"}}
                elif kind == "get_messages":
                    data = {"messages": [{"role": "assistant", "content": [{"type": "text", "text": "Worker summary with uncertainty"}]}]}
                else:
                    current = state.check_state(self.stream)
                    self.assertEqual(current.goals.work[0].workers[-1]["session"], "worker-durable")
                    self.assertEqual(current.goals.work[0].waiting_for, "worker-durable")
                    text = request["command"]["message"]
                    self.assertTrue(text.startswith('Context handover for clean worker session "worker-durable".'))
                    self.assertIn('Read the installed process entry at "/installed/poteto/SKILL.md"', text)
                    self.assertNotIn("Current files for stream", text)
                    self.assertNotIn(str(self.stream / "STATE.md"), text)
                    self.assertEqual("Review the handed-over result adversarially" in text, reviewer)
                    self.assertEqual(load_threads(self.stream / "threads.tsv")[-1].session, "worker-durable")
                    data = None
                return stub.response(request, data)
            with StubPrime(handler) as stub, PrimeClient(stub.path) as client:
                identity, result = spawn_prime_worker(client, self.stream, worktree=worktree, work="Review A" if reviewer else "Implement A", original_entries=[source], poteto_path="/installed/poteto/SKILL.md", model="openai-codex/gpt-6.1-sol", thinking="xhigh", reviewer=reviewer)
            self.assertEqual(identity.session_id, "worker-durable")
            self.assertEqual(result["frame"]["success"], True)
            self.assertEqual((worktree / "AGENTS.md").read_text(), "Keep native product instructions.\n")
            self.assertFalse((worktree / "STATE.md").exists())
            self.assertFalse((worktree / "stream.toml").exists())
            self.assertIn("Worker summary with uncertainty", state.read_entry(self.stream, result["entry"]))
        self.assertIn("Review every reported summary adversarially", (self.stream / "AGENTS.md").read_text())
