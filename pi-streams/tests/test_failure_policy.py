from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

from support import ROOT
sys.path.insert(0, str(ROOT / "pi-streams"))
from engine import failure


class FailurePolicyTests(unittest.TestCase):
    def test_usage_reset_uses_only_allowlisted_metadata_and_not_account_or_header_data(self):
        observed = "2026-10-06T12:00:00Z"
        raw = json.dumps({"error": {"code": "usage_limit_reached", "resets_at": 1791288600, "account_id": "private-account-must-not-persist", "headers": {"authorization": "secret-must-not-persist"}}})
        result = failure.classify("openai-codex", raw, observed)
        self.assertEqual(result.kind, "usage-limit")
        self.assertEqual(result.code, "usage_limit_reached")
        self.assertEqual(result.reset_at, "2026-10-06T12:10:00Z")
        self.assertNotIn("private-account", json.dumps(result.public()))
        self.assertNotIn("secret-must", json.dumps(result.public()))

    def test_relative_provider_fallback_is_conservative_and_saved_once(self):
        result = failure.classify("openai-codex", "You have hit your ChatGPT usage limit. Try again in ~9 min.", "2026-10-06T12:00:00Z")
        self.assertEqual(result.kind, "usage-limit")
        self.assertEqual(result.reset_at, "2026-10-06T12:10:00Z")
        self.assertEqual(result.reset_source, "relative-message-fallback")
        unknown = failure.classify("openai-codex", "You have hit your ChatGPT usage limit.", "2026-10-06T12:00:00Z")
        self.assertEqual(unknown.reset_at, "")

    def test_other_four_failure_classes_never_gain_an_automatic_readiness_retry(self):
        cases = [("openai-codex", "Expired Codex login: session expired", False, "codex-login"), ("tool", "Tool login expired: unauthorized token", True, "tool-login"), ("engine", "ENOSPC: no space left on device", False, "resource"), ("openai-codex", "Other model 503 unavailable", False, "model-error")]
        for provider, message, tool, expected in cases:
            with self.subTest(kind=expected):
                result = failure.classify(provider, message, "2026-10-06T12:00:00Z", tool_error=tool)
                self.assertEqual(result.kind, expected)
                self.assertFalse(result.automatic_retry)
                self.assertEqual(result.reset_at, "")

    def test_reset_trial_requires_saved_step_notification_and_same_uncancelled_generation(self):
        episode = failure.Episode(id="episode-one", session="full-owned-sid", cwd="/private/owned", kind="usage-limit", code="usage_limit_reached", label="Codex usage limit", observed_at="2026-10-06T12:00:00Z", failure_entry="e3", failure_sha256="f" * 64, reset_at="2026-10-06T12:10:00Z", reset_source="provider-metadata", saved_entry="e2", saved_sha256="a" * 64, pause_generation="parked-generation", pause_owned=True)
        self.assertFalse(failure.retry_ready(episode, "2026-10-06T12:09:59Z", "parked-generation", False))
        self.assertFalse(failure.retry_ready(episode, "2026-10-06T12:10:00Z", "parked-generation", False))
        episode.notification = {"state": "delivered", "deliveryId": "offhost-message", "route": "verified-zf-dm-v1"}
        self.assertTrue(failure.retry_ready(episode, "2026-10-06T12:10:00Z", "parked-generation", False))
        self.assertFalse(failure.retry_ready(episode, "2026-10-06T12:10:00Z", "newer-stop-generation", False))
        episode.retry_reset = episode.reset_at
        self.assertFalse(failure.retry_ready(episode, "2026-10-06T13:00:00Z", "parked-generation", False))
        episode.reset_at = "2026-10-06T12:05:00Z"
        self.assertFalse(failure.retry_ready(episode, "2026-10-06T13:00:00Z", "parked-generation", False))

    def test_uncertain_job_or_cancelled_work_stays_parked_after_reset_and_readiness(self):
        episode = failure.Episode(id="episode-jobs", session="full-owned-sid", cwd="/private/owned", kind="usage-limit", code="usage_limit_reached", label="Codex usage limit", observed_at="2026-10-06T12:00:00Z", failure_entry="e3", failure_sha256="f" * 64, reset_at="2026-10-06T12:10:00Z", reset_source="provider-metadata", saved_entry="e2", saved_sha256="a" * 64, pause_generation="parked-generation", pause_owned=True, notification={"state": "delivered", "deliveryId": "offhost-message", "route": "verified-zf-dm-v1"}, uncertain_jobs=[{"id": "submitted-job-42", "state": "unknown"}])
        self.assertFalse(failure.retry_ready(episode, "2026-10-07T12:00:00Z", "parked-generation", False))
        episode.uncertain_jobs = []
        episode.cancelled = True
        self.assertFalse(failure.retry_ready(episode, "2026-10-07T12:00:00Z", "parked-generation", False))
