from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tick_support import TickCase, failure, info, reply, row, status, user


class FailureMarkerTests(TickCase):
    def setUp(self):
        super().setUp()
        self.stream = self.make_stream(self.home, "etl", row("coi", "coordinator", str(self.home/"etl")))
        self.seed("coi", self.stream)
        self.routes()

    def seed(self, sid: str, cwd: Path):
        call = {**reply(""), "content": [{"type":"toolCall","id":"call-A","name":"read","arguments":{}},{"type":"toolCall","id":"call-B","name":"read","arguments":{}}], "stopReason":"toolUse"}
        result = lambda identity: {"role":"toolResult","toolCallId":identity,"toolName":"read","isError":False,"content":[{"type":"text","text":"Labelled successful offline tool result"}]}
        self.write_log(sid, str(cwd), user("Authorized good multi-tool turn"), call, result("call-A"), result("call-B"), user("Authorized later input"), failure("Labelled expired Codex login: session expired"))
        self.stub.automatic_admissions[sid] = {"sessionId":sid,"cwd":str(cwd),"generation":"native-parked-"+sid,"allowed":False,"durable":True}

    def digest(self, sid, entry):
        with open(self.log_path(sid), "rb") as source:
            raw = next(line for line in source if json.loads(line).get("id") == entry)
        return hashlib.sha256(raw).hexdigest()

    def body(self, sid="coi", cwd=None, checkpoint="e4", digest=None):
        cwd = self.stream if cwd is None else cwd
        body = status(sid)
        body.update(conditionalAdmissionSupport="generation-cas-v1", recoveryControlSupport="question-safe-v1", failureBoundarySupport="persisted-turn-v1", rotationSafety={"entryId":"e6"}, failureBoundary={"version":1,"sessionId":sid,"cwd":str(cwd),"root":str(self.stream),"stream":"etl","state":"parked","checkpoint":{"entryId":checkpoint,"sha256":self.digest(sid, checkpoint) if digest is None else digest},"failure":{"entryId":"e6","sha256":self.digest(sid,"e6"),"kind":"codex-login"}})
        return body

    def routes(self, body=None, extra=()):
        self.stub.set_routes([("GET","/api/sessions",200,[info("coi",str(self.stream),self.log_path("coi")), *extra]),("GET","/api/sessions/coi/status",200,self.body() if body is None else body)])

    def test_exact_complete_batch_checkpoint_becomes_the_only_marker_content(self):
        before=(self.stream/"STATE.md").read_bytes().split(b"## Log",1)[0]
        result=self.tick("2026-10-06T12:00:00Z")
        self.assertEqual(result.returncode,0,result.stderr)
        marker=self.stream/"failures/coi.lastgood"
        self.assertTrue(marker.is_file(),"A parked native failure must publish its exact good-turn marker")
        self.assertEqual(marker.read_bytes(),b"e4\n")
        saved=self.state(self.stream)["failures"]["coi"]
        self.assertEqual(saved["checkpoint"]["entryId"],"e4")
        self.assertEqual(saved["checkpoint"]["sha256"],self.digest("coi","e4"))
        self.assertEqual(saved["failure_entry"],"e6")
        self.assertEqual((self.stream/"STATE.md").read_bytes().split(b"## Log",1)[0],before)
        self.assertFalse(any(item[0]=="POST" for item in self.stub.requests))
        self.assertEqual(self.tick("2026-10-07T12:00:00Z").returncode,0)
        self.assertEqual(marker.read_bytes(),b"e4\n")

    def test_later_sdk_fence_noise_cannot_replace_the_original_native_failure_identity(self):
        with open(self.log_path("coi"),"a") as native:
            native.write(json.dumps({"type":"message","id":"e7","parentId":"e6","message":failure("Labelled SDK fence error, not another provider failure")})+"\n")
        body=self.body(); body["rotationSafety"]["entryId"]="e7"
        self.routes(body)
        result=self.tick("2026-10-06T12:00:00Z")
        self.assertEqual(result.returncode,0,result.stderr)
        episode=self.state(self.stream)["failures"]["coi"]
        self.assertEqual(episode["failure_entry"],"e6")
        self.assertEqual(episode["kind"],"codex-login")
        self.assertEqual(episode["failure_sha256"],self.digest("coi","e6"))
        self.assertEqual((self.stream/"failures/coi.lastgood").read_bytes(),b"e4\n")

    def test_tick_registers_an_unwatched_supported_runtime_before_observing_its_failure(self):
        body=self.body(); native=body.pop("failureBoundary")
        self.stub.set_routes([("GET","/api/sessions",200,[info("coi",str(self.stream),self.log_path("coi"))]),("GET","/api/sessions/coi/status",200,body),("POST","/api/sessions/coi/failure-boundary",200,native)])
        result=self.tick("2026-10-06T12:00:00Z")
        self.assertEqual(result.returncode,0,result.stderr)
        posted=[item[3] for item in self.stub.requests if item[0]=="POST" and item[1].endswith("/failure-boundary")]
        self.assertEqual(posted,[{"cwd":str(self.stream),"stream":"etl","root":str(self.stream)}])
        self.assertEqual((self.stream/"failures/coi.lastgood").read_bytes(),b"e4\n")

    def test_partial_tool_batch_and_wrong_hash_are_refused_without_inventing_a_marker(self):
        for body in (self.body(checkpoint="e3"), self.body(digest="0"*64)):
            with self.subTest(body=body["failureBoundary"]["checkpoint"]):
                self.routes(body)
                result=self.tick("2026-10-06T12:00:00Z")
                self.assertNotEqual(result.returncode,0)
                self.assertFalse((self.stream/"failures/coi.lastgood").exists())
                self.assertFalse(any(item[0]=="POST" for item in self.stub.requests))

    def test_marker_directory_symlink_cannot_redirect_failure_bookkeeping(self):
        outside=self.tmp/"unrelated-marker-directory"; outside.mkdir()
        (self.stream/"failures").symlink_to(outside, target_is_directory=True)
        result=self.tick("2026-10-06T12:00:00Z")
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(list(outside.iterdir()),[])
        self.assertFalse(any(item[0]=="POST" for item in self.stub.requests))

    def test_coordinator_and_affected_worker_keep_separate_full_identity_markers(self):
        worker=self.tmp/"worker-owned"; worker.mkdir()
        self.seed("worker",worker)
        with open(self.stream/"threads.tsv","a") as registry: registry.write(row("worker","research",str(worker)))
        self.stub.set_routes([("GET","/api/sessions",200,[info("coi",str(self.stream),self.log_path("coi")),info("worker",str(worker),self.log_path("worker"))]),("GET","/api/sessions/coi/status",200,self.body()),("GET","/api/sessions/worker/status",200,self.body("worker",worker))])
        before=list(worker.iterdir())
        result=self.tick("2026-10-06T12:00:00Z")
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertTrue((self.stream/"failures/coi.lastgood").is_file())
        self.assertTrue((self.stream/"failures/worker.lastgood").is_file())
        self.assertEqual((self.stream/"failures/worker.lastgood").read_bytes(),b"e4\n")
        self.assertEqual(list(worker.iterdir()),before)
        self.assertEqual(set(self.state(self.stream)["failures"]),{"coi","worker"})
