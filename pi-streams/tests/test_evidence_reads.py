"""Exact JSONL evidence survives native archive relocation without restoration."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from unittest import mock

from support import EngineCase, ROOT

sys.path.insert(0, str(ROOT / "pi-streams"))
from engine import StreamsError, piweb


class EvidenceReadTests(EngineCase):
    def setUp(self) -> None:
        super().setUp()
        self.cwd = self.root
        self.sid = "019a3c1e-7d2a-7c41-9e1b-0c7a5f2e9a01"
        self.live = self.tmp / "native-live.jsonl"
        self.archive = self.tmp / "metadata-selected-archive.jsonl"
        self.records = (
            b'{ "type": "message", "id": "first", "message": {"role":"user","content":"verify"}}\r\n',
            '{"type":"message","id":"second","message":{"role":"assistant","content":"原本"}}\n'.encode(),
        )
        header = json.dumps({"type": "session", "id": self.sid, "cwd": str(self.cwd)}).encode() + b"\n"
        self.live.write_bytes(header + b"".join(self.records))
        self.routes()
        self.stub.requests.clear()

    def routes(self, *, sid: str | None = None, archived: bool = False, extra: list | None = None) -> None:
        info = {"id": self.sid if sid is None else sid, "cwd": str(self.cwd), "path": str(self.live), "archived": archived}
        if archived:
            info["archivePath"] = str(self.archive)
        self.stub.set_routes([("GET", "/api/sessions", 200, [info, *(extra or [])])])

    def read(self, entry: str = "first", *, expected: str | None = None, hint: int | None = None):
        digest = hashlib.sha256(self.records[0]).hexdigest() if expected is None else expected
        with mock.patch.dict(os.environ, self.env, clear=True):
            return piweb.read_evidence(str(self.cwd), self.sid, entry, digest, line_hint=hint)

    def test_two_original_byte_hashes_match_before_and_after_archive(self) -> None:
        for archived in (False, True):
            if archived:
                self.live.rename(self.archive)
                self.routes(archived=True)
            for entry, raw in zip(("first", "second"), self.records):
                with self.subTest(archived=archived, entry=entry):
                    result = self.read(entry, expected=hashlib.sha256(raw).hexdigest(), hint=999)
                    self.assertEqual(result.raw, raw)
                    self.assertEqual(result.sha256, hashlib.sha256(raw).hexdigest())
                    self.assertEqual(result.session_id, self.sid)
                    self.assertEqual(result.entry_id, entry)
                    self.assertEqual(result.archived, archived)
        self.assertEqual([method for method, _, _, _ in self.stub.requests], ["GET"] * 4)
        self.assertFalse(self.live.exists())

    def test_one_byte_change_is_a_hash_mismatch(self) -> None:
        self.live.write_bytes(self.live.read_bytes().replace(b'"verify"', b'"Verify"'))
        with self.assertRaisesRegex(StreamsError, "hash mismatch"):
            self.read()

    def test_unknown_record_and_missing_source_are_unavailable(self) -> None:
        with self.assertRaisesRegex(StreamsError, "unavailable"):
            self.read("unknown")
        self.live.unlink()
        with self.assertRaisesRegex(StreamsError, "unavailable"):
            self.read()

    def test_wrong_session_header_and_prefix_metadata_are_refused(self) -> None:
        original = self.live.read_bytes()
        self.live.write_bytes(original.replace(self.sid.encode(), b"different-session", 1))
        with self.assertRaisesRegex(StreamsError, "session identity"):
            self.read()
        self.live.write_bytes(original)
        self.routes(sid=self.sid + "-not-exact")
        with self.assertRaisesRegex(StreamsError, "unavailable"):
            self.read()

    def test_duplicate_metadata_or_entry_identity_is_ambiguous(self) -> None:
        self.routes(extra=[{"id": self.sid, "cwd": str(self.cwd), "path": str(self.live)}])
        with self.assertRaisesRegex(StreamsError, "ambiguous"):
            self.read()
        self.routes()
        self.live.write_bytes(self.live.read_bytes() + self.records[0])
        with self.assertRaisesRegex(StreamsError, "ambiguous"):
            self.read()

    def test_archived_read_never_uses_a_recreated_live_path(self) -> None:
        self.live.rename(self.archive)
        self.live.write_bytes(b"unrelated recreated live file\n")
        self.routes(archived=True)
        self.assertEqual(self.read().raw, self.records[0])
        self.assertEqual(self.live.read_bytes(), b"unrelated recreated live file\n")

    def test_missing_archive_metadata_does_not_guess_a_location(self) -> None:
        self.live.rename(self.archive)
        self.stub.set_routes([("GET", "/api/sessions", 200, [{"id": self.sid, "cwd": str(self.cwd), "path": str(self.live), "archived": True}])])
        with self.assertRaisesRegex(StreamsError, "archive.*unavailable"):
            self.read()

    def test_a_line_hint_cannot_substitute_for_record_identity(self) -> None:
        with self.assertRaisesRegex(StreamsError, "unavailable"):
            self.read("unknown", hint=2)
        evidence = self.read(hint=3)
        self.assertEqual(evidence.entry_id, "first")
        self.assertEqual(evidence.line_number, 2)
        self.assertEqual(evidence.raw, self.records[0])
        self.assertEqual([method for method, _, _, _ in self.stub.requests], ["GET", "GET"])
