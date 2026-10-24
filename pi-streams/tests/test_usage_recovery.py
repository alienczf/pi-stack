from __future__ import annotations

import json
import hashlib
from datetime import datetime, timezone

from tick_support import TickCase, PROMPTS, failure, info, reply, row, status, user


class UsageRecoveryTests(TickCase):
    def setUp(self):
        super().setUp()
        self.stream=self.make_stream(self.home,"etl",row("coi","coordinator",str(self.home/"etl")))
        self.stub.reflect_control_goals=True
        self.stub.simulate_conditional_controls=True
        self.error=json.dumps({"error":{"code":"usage_limit_reached","resets_at":datetime(2026,10,6,12,10,tzinfo=timezone.utc).timestamp(),"account_id":"must-not-copy-account","message":"Labelled private provider-metadata fault, not real quota"}})
        self.write_log("coi",str(self.stream),user("Reconcile the original authorized step without duplicate external submissions."),failure(self.error))
        self.routes()

    def routes(self,leaf="e2"):
        body=status("coi")
        body.update(conditionalAdmissionSupport="generation-cas-v1",recoveryControlSupport="question-safe-v1",controlGoalSupport="preserve-ask-v1",rotationSafety={"entryId":leaf})
        self.stub.set_routes([PROMPTS,("GET","/api/sessions",200,[info("coi",str(self.stream),self.log_path("coi"))]),("GET","/api/sessions/coi/status",200,body),("POST","/api/sessions/coi/control-goal",200,{"state":"queued"})])

    def episode(self):
        data=self.state(self.stream)
        self.assertIn("failures",data,"Known explicit native failure must retain a typed episode")
        return data["failures"]["coi"]

    def synthetic_notification_receipt(self):
        path=self.stream/"log/tick-state.json"
        data=json.loads(path.read_text())
        data["failures"]["coi"]["notification"]={"state":"delivered","deliveryId":"labelled-synthetic-offhost-receipt","route":"verified-zf-dm-v1"}
        path.write_text(json.dumps(data))  # Contract fixture only, never a real Slack delivery claim.

    def test_unchanged_error_gets_one_saved_reconciliation_trial_at_reset_without_prior_success(self):
        captured=self.tick("2026-10-06T12:00:00Z")
        self.assertEqual(captured.returncode,0,captured.stderr)
        episode=self.episode()
        self.assertEqual(episode["kind"],"usage-limit")
        self.assertEqual(episode["reset_at"],"2026-10-06T12:10:00Z")
        self.assertEqual(episode["saved_entry"],"e1")
        self.assertNotIn("must-not-copy-account",json.dumps(episode))
        self.assertFalse(self.stub.automatic_admissions["coi"]["allowed"])
        self.synthetic_notification_receipt()
        early=self.tick("2026-10-06T12:09:59Z")
        self.assertEqual(early.returncode,0,early.stderr)
        self.assertFalse(any(item[0]=="POST" and item[1].endswith("/control-goal") for item in self.stub.requests))
        ready=self.tick("2026-10-06T12:10:00Z")
        self.assertEqual(ready.returncode,0,ready.stderr)
        goals=[item for item in self.stub.requests if item[0]=="POST" and item[1].endswith("/control-goal")]
        self.assertEqual(len(goals),1)
        self.assertEqual(goals[0][3]["automaticAdmission"]["kind"],"recovery")
        self.assertIn("Usage-reset reconciliation",goals[0][3]["text"])
        self.assertIn("Never replay an arbitrary shell submission",goals[0][3]["text"])
        self.assertTrue(goals[0][3]["text"].endswith("/poteto-mode <the single human-authorized outcome>"))
        identity=self.episode()["retry_id"]
        self.stub.control_goals[identity]["state"]="uncertain"
        later=self.tick("2026-10-06T13:00:00Z")
        self.assertEqual(later.returncode,0,later.stderr)
        self.assertFalse(any(item[0]=="POST" and item[1].endswith("/control-goal") for item in self.stub.requests))
        self.assertEqual(self.episode()["retry_reset"],"2026-10-06T12:10:00Z")
        self.assertEqual(self.episode()["retry_state"],"uncertain")

    def test_recovery_is_not_claimed_until_the_exact_reconciliation_input_has_native_completion(self):
        self.assertEqual(self.tick("2026-10-06T12:00:00Z").returncode,0)
        self.synthetic_notification_receipt()
        self.assertEqual(self.tick("2026-10-06T12:10:00Z").returncode,0)
        episode=self.episode()
        self.stub.control_goals[episode["retry_id"]]["state"]="ended"
        prefix=episode["retry_body"].rsplit("/poteto-mode ",1)[0]
        expanded=prefix+'<skill name="poteto-mode">Labelled offline native mode fixture</skill>\n\n'+episode["retry_goal"]
        self.write_log("coi",str(self.stream),user("Reconcile the original authorized step without duplicate external submissions."),failure(self.error),user(expanded),reply("The exact saved reconciliation admission completed."))
        self.routes(leaf="e4")
        completed=self.tick("2026-10-06T12:15:00Z")
        self.assertEqual(completed.returncode,0,completed.stderr)
        self.assertEqual(self.episode()["state"],"recovered")
        self.assertEqual(self.episode()["retry_state"],"ended")
        self.assertFalse(any(item[0]=="POST" and item[1].endswith("/control-goal") for item in self.stub.requests))
        alerts=self.alerts().splitlines()
        self.assertEqual(sum(line.startswith('episode '+episode['id']+' recovery ') for line in alerts),1)

    def test_missing_offhost_delivery_proof_keeps_usage_trial_disabled_even_after_reset(self):
        self.assertEqual(self.tick("2026-10-06T12:00:00Z").returncode,0)
        self.assertEqual(self.episode()["notification"],None)
        result=self.tick("2026-10-06T13:00:00Z")
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertFalse(any(item[0]=="POST" and item[1].endswith("/control-goal") for item in self.stub.requests))
        self.assertEqual(self.episode()["retry_id"],"")

    def test_unconfirmed_local_off_blocks_reset_trial_even_if_remote_parked_epoch_is_unchanged(self):
        self.assertEqual(self.tick("2026-10-06T12:00:00Z").returncode,0)
        self.synthetic_notification_receipt()
        parked=dict(self.stub.automatic_admissions["coi"])
        self.stub.simulate_conditional_controls=False
        self.stub.set_routes([("POST","/api/sessions/coi/automatic-admission",503,{"error":"Labelled unavailable off publication"}),*self.stub.routes])
        stopped=self.run_streams("drive","etl","off")
        self.assertNotEqual(stopped.returncode,0)
        self.assertFalse(self.state(self.stream)["drive"]["enabled"])
        self.assertEqual(self.stub.automatic_admissions["coi"],parked)
        self.stub.simulate_conditional_controls=True
        self.routes()
        later=self.tick("2026-10-06T13:00:00Z")
        self.assertEqual(later.returncode,0,later.stderr)
        self.assertFalse(any(item[0]=="POST" for item in self.stub.requests))
        self.assertEqual(self.episode()["retry_id"],"")

    def test_newer_real_stop_cannot_be_rearmed_by_reset_ready_snapshot(self):
        self.assertEqual(self.tick("2026-10-06T12:00:00Z").returncode,0)
        self.synthetic_notification_receipt()
        self.stub.automatic_admissions["coi"].update(generation="newer-genuine-stop",allowed=False)
        result=self.tick("2026-10-06T13:00:00Z")
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertFalse(any(item[0]=="POST" for item in self.stub.requests))
        self.assertFalse(self.stub.automatic_admissions["coi"]["allowed"])
        self.assertEqual(self.episode()["retry_id"],"")

    def test_submitted_uncertain_job_is_retained_instead_of_resubmitted_at_reset(self):
        self.write_log("coi",str(self.stream),user("Reconcile the submitted private job"),{"role":"toolResult","toolCallId":"submit-call","toolName":"private-submit","isError":False,"details":{"jobId":"submitted-job-42","status":"submitted"},"content":[{"type":"text","text":"Labelled already-submitted job fixture"}]},failure(self.error))
        self.routes(leaf="e3")
        self.assertEqual(self.tick("2026-10-06T12:00:00Z").returncode,0)
        self.assertEqual(self.episode()["uncertain_jobs"],[{"id":"submitted-job-42","state":"submitted"}])
        self.synthetic_notification_receipt()
        later=self.tick("2026-10-06T13:00:00Z")
        self.assertEqual(later.returncode,0,later.stderr)
        self.assertFalse(any(item[0]=="POST" for item in self.stub.requests))
        self.assertEqual(self.episode()["retry_id"],"")
        self.assertEqual(self.episode()["uncertain_jobs"],[{"id":"submitted-job-42","state":"submitted"}])

    def test_job_result_after_auth_error_in_same_tool_batch_survives_public_tick_parking(self):
        calls={**reply(""),"content":[{"type":"toolCall","id":"auth-call","name":"private-auth","arguments":{}},{"type":"toolCall","id":"submit-call","name":"private-submit","arguments":{}}],"stopReason":"toolUse"}
        self.write_log("coi",str(self.stream),user("Only the authorized private batch"),calls,{"role":"toolResult","toolCallId":"auth-call","toolName":"private-auth","isError":True,"content":[{"type":"text","text":"Labelled tool login expired: unauthorized token"}]},{"role":"toolResult","toolCallId":"submit-call","toolName":"private-submit","isError":False,"details":{"jobId":"after-error-job","status":"submitted"},"content":[{"type":"text","text":"Labelled job was submitted by the same complete batch"}]},reply("A normal final reply does not ratify the tool-auth failure"))
        self.routes(leaf="e5")
        with open(self.log_path("coi"),"rb") as native:
            raw=next(line for line in native if json.loads(line).get("id")=="e3")
        observed=self.tick("2026-10-06T12:00:00Z")
        self.assertEqual(observed.returncode,0,observed.stderr)
        episode=self.episode()
        self.assertEqual(episode["kind"],"tool-login")
        self.assertEqual(episode["failure_entry"],"e3")
        self.assertEqual(episode["failure_sha256"],hashlib.sha256(raw).hexdigest())
        self.assertEqual(episode["uncertain_jobs"],[{"id":"after-error-job","state":"submitted"}])
        self.synthetic_notification_receipt()
        later=self.tick("2026-10-07T12:00:00Z")
        self.assertEqual(later.returncode,0,later.stderr)
        self.assertFalse(any(item[0]=="POST" for item in self.stub.requests))
        self.assertEqual(self.episode()["failure_entry"],"e3")
        self.assertEqual(self.episode()["uncertain_jobs"],[{"id":"after-error-job","state":"submitted"}])

    def test_tool_auth_error_inside_a_normal_turn_is_parked_without_readiness_release(self):
        self.write_log("coi",str(self.stream),user("Only the authorized task"),{"role":"toolResult","toolCallId":"owned-tool","toolName":"private-tool","isError":True,"content":[{"type":"text","text":"Labelled Tool login expired: unauthorized token"}]},reply("A later ordinary assistant reply is not ratification"))
        self.routes(leaf="e3")
        observed=self.tick("2026-10-06T12:00:00Z")
        self.assertEqual(observed.returncode,0,observed.stderr)
        self.assertEqual(self.episode()["kind"],"tool-login")
        self.assertEqual(self.episode()["saved_entry"],"e1")
        self.synthetic_notification_receipt()
        later=self.tick("2026-10-07T12:00:00Z")
        self.assertEqual(later.returncode,0,later.stderr)
        self.assertFalse(any(item[0]=="POST" for item in self.stub.requests))
        self.assertEqual(self.episode()["state"],"parked")

    def test_nonusage_failure_does_not_release_on_later_success_or_fixed_user_text(self):
        self.write_log("coi",str(self.stream),user("Original authorized task"),failure("Labelled expired Codex login: session expired"))
        first=self.tick("2026-10-06T12:00:00Z")
        self.assertEqual(first.returncode,0,first.stderr)
        episode=self.episode()
        self.assertEqual(episode["kind"],"codex-login")
        self.synthetic_notification_receipt()
        self.write_log("coi",str(self.stream),user("Original authorized task"),failure("Labelled expired Codex login: session expired"),user("fixed, please continue"),reply("Unrelated successful readiness response"))
        self.routes(leaf="e4")
        later=self.tick("2026-10-07T12:00:00Z")
        self.assertEqual(later.returncode,0,later.stderr)
        self.assertFalse(any(item[0]=="POST" for item in self.stub.requests))
        self.assertEqual(self.episode()["id"],episode["id"])
        self.assertEqual(self.episode()["state"],"parked")
        self.assertFalse(self.stub.automatic_admissions["coi"]["allowed"])
