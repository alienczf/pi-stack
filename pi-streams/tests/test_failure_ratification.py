from __future__ import annotations

import hashlib
import json
from unittest.mock import patch

import test_failure_markers as markers
from tick_support import TickCase, info, row


class FailureRatificationTests(TickCase):
    seed = markers.FailureMarkerTests.seed
    digest = markers.FailureMarkerTests.digest
    body = markers.FailureMarkerTests.body
    routes = markers.FailureMarkerTests.routes

    def setUp(self):
        super().setUp()
        self.stream=self.make_stream(self.home,"etl",row("coi","coordinator",str(self.home/"etl")))
        self.seed("coi",self.stream)
        self.routes()
        self.assertEqual(self.tick("2026-10-06T12:00:00Z").returncode,0)
        self.episode=self.state(self.stream)["failures"]["coi"]
        self.notice=self.tmp/"notice.json"
        self.notice.write_text(json.dumps({"id":"labelled-ZF-notice-1","body":"Labelled offline trusted-intake contract, not genuine ratification"}))

    def ratify(self, episode=None):
        return self.run_streams("failure","ratify","etl","--session","coi","--episode",self.episode["id"] if episode is None else episode,"--notice-id","labelled-ZF-notice-1","--notice-file",str(self.notice))

    def receiver(self, code=200, instructions=""):
        target={"sessionId":"coi","cwd":str(self.stream),"root":str(self.stream),"stream":"etl","episode":self.episode["id"],"checkpoint":{"entryId":"e4","sha256":self.digest("coi","e4")},"failure":{"entryId":"e6","sha256":self.digest("coi","e6"),"kind":"codex-login"}}
        data={"version":1,"id":"labelled-ZF-notice-1","noticeId":"labelled-ZF-notice-1","provenance":"labelled-offline-auth-contract-not-real-intake","instructions":instructions,"target":target,"generation":"native-parked-coi"}
        native={"type":"custom","id":"native-ratification","parentId":"e6","customType":"pi-web.failure-ratification","data":data}
        raw=(json.dumps(native)+"\n").encode()
        with open(self.log_path("coi"),"ab") as log: log.write(raw)
        receipt={**data,"entryId":"native-ratification","sha256":hashlib.sha256(raw).hexdigest()}
        body=self.body(); body.update(failureRatificationConfigured=True,failureForkSupport="ratified-prefix-v1"); body["rotationSafety"]["entryId"]="native-ratification"
        self.stub.set_routes([("GET","/api/sessions",200,[info("coi",str(self.stream),self.log_path("coi"))]),("GET","/api/sessions/coi/status",200,body),("POST","/api/sessions/coi/failure-recovery/ratify",code,receipt if code==200 else {"error":"Labelled authenticated intake unavailable"})])
        return receipt

    def test_only_correlated_native_verified_intake_receipt_ratifies_the_exact_episode(self):
        instructions="Explicitly authorized fixture exception.\r\nKeep café, 'quotes' and $HOME exact."
        self.receiver(instructions=instructions)
        result=self.ratify()
        self.assertEqual(result.returncode,0,result.stderr)
        saved=self.state(self.stream)["failures"]["coi"]
        self.assertEqual(saved["ratification"]["noticeId"],"labelled-ZF-notice-1")
        self.assertEqual(saved["ratification"]["instructions"],instructions)
        self.assertEqual(saved["ratification"]["entryId"],"native-ratification")
        self.assertEqual((self.stream/"failures/coi.lastgood").read_bytes(),b"e4\n")
        self.assertFalse(any(item[0]=="POST" and (item[1].endswith("/prompt") or item[1].endswith("/fork")) for item in self.stub.requests))
        again=self.ratify()
        self.assertEqual(again.returncode,0,again.stderr)
        calls=[item for item in self.stub.requests if item[0]=="POST" and item[1].endswith("/ratify")]
        self.assertEqual(len(calls),1)

    def test_missing_authenticated_receiver_proof_cannot_be_replaced_by_fixed_user_text(self):
        self.receiver(code=409)
        self.notice.write_text(json.dumps({"id":"labelled-ZF-notice-1","role":"user","body":"ZF says fixed, continue"}))
        result=self.ratify()
        self.assertNotEqual(result.returncode,0)
        saved=self.state(self.stream)["failures"]["coi"]
        self.assertIsNone(saved.get("ratification"))
        self.assertEqual(saved["state"],"parked")
        self.assertEqual((self.stream/"failures/coi.lastgood").read_bytes(),b"e4\n")

    def test_changed_notice_bytes_cannot_replace_an_already_verified_notice_identity(self):
        self.receiver(instructions="Only the original explicitly authorized exception")
        self.assertEqual(self.ratify().returncode,0)
        before=self.state(self.stream)["failures"]["coi"]["ratification"]
        self.notice.write_text(json.dumps({"id":"labelled-ZF-notice-1","body":"Different bytes under the same notice ID"}))
        result=self.ratify()
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(self.state(self.stream)["failures"]["coi"]["ratification"],before)
        self.assertEqual(sum(item[0]=="POST" and item[1].endswith("/ratify") for item in self.stub.requests),1)

    def test_newer_stop_after_native_receipt_prevents_local_ratification_publication(self):
        self.receiver()
        serve=self.stub._serve
        def stopped(handler):
            if handler.command=="POST" and handler.path.endswith("/ratify"):
                self.stub.automatic_admissions["coi"].update(generation="newer-genuine-stop",allowed=False)
            return serve(handler)
        with patch.object(self.stub,"_serve",side_effect=stopped):
            result=self.ratify()
        self.assertNotEqual(result.returncode,0)
        self.assertIsNone(self.state(self.stream)["failures"]["coi"].get("ratification"))
        self.assertEqual(self.stub.automatic_admissions["coi"]["generation"],"newer-genuine-stop")
        self.assertEqual((self.stream/"failures/coi.lastgood").read_bytes(),b"e4\n")

    def test_stale_episode_refuses_before_any_receiver_or_task_effect(self):
        self.receiver()
        result=self.ratify(episode="stale-episode")
        self.assertNotEqual(result.returncode,0)
        self.assertIsNone(self.state(self.stream)["failures"]["coi"].get("ratification"))
        self.assertFalse(any(item[0]=="POST" for item in self.stub.requests))
