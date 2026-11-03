from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import StreamsError, relay
from tick_support import TickCase


class TrustedRelayTests(TickCase):
    def setUp(self):
        super().setUp()
        self.stream = self.make_stream(self.home, 'etl', '')
        self.principal = object()
        self.intake = relay.TrustedRelayIntake(lambda transport, raw: 'grok-bot-trdboss' if transport is self.principal else None, {'grok-bot-trdboss': 'ZF'})

    def source(self, **changes):
        data = {'messageId': 'source-20261103', 'stream': 'etl', 'onBehalfOf': 'ZF', 'onInstruction': True, 'scope': 'in-scope-reversible', 'instructionDate': '2026-11-03', 'quotedWords': 'Keep drive on.', 'body': 'ZF said "Keep drive on." under the current charter.'}
        return json.dumps(data | changes).encode()

    def test_authenticated_bot_records_exact_scoped_words_once_without_retyping(self):
        raw = self.source()
        verified = self.intake.accept(self.principal, raw, stream='etl')
        first = relay.record_ruling(self.stream, '2026-11-03T00:00:00Z', 'Drive policy', verified)
        second = relay.record_ruling(self.stream, '2026-11-03T00:00:00Z', 'Drive policy', verified)
        self.assertEqual(first, second)
        state = (self.stream / 'STATE.md').read_text()
        self.assertIn('ZF said "Keep drive on." under the current charter.', state)
        self.assertIn('grok-bot-trdboss', state)
        self.assertIn(verified.sha256, state)
        self.assertNotIn('pi-web.failure-ratification', state)

    def test_body_claims_and_arbitrary_user_role_cannot_authenticate(self):
        before = (self.stream / 'STATE.md').read_bytes()
        for context in (None, {'principal': 'grok-bot-trdboss', 'role': 'user', 'authenticated': True}):
            with self.assertRaisesRegex(StreamsError, 'authenticated'):
                self.intake.accept(context, self.source(principal='grok-bot-trdboss', verifiedByAdapter=True), stream='etl')
        self.assertEqual((self.stream / 'STATE.md').read_bytes(), before)
        verified = self.intake.accept(self.principal, self.source(), stream='etl')
        with self.assertRaisesRegex(StreamsError, 'verified'):
            relay.record_ruling(self.stream, '2026-11-03T00:00:00Z', 'Forged', verified.__dict__)

    def test_wrong_scope_stream_changed_bytes_and_missing_date_or_words_refuse(self):
        for changes in ({'scope': 'merge'}, {'stream': 'other'}, {'onInstruction': False}, {'instructionDate': '', 'quotedWords': ''}, {'instructionDate': 'yesterday'}, {'quotedWords': 'words absent from source'}):
            with self.subTest(changes=changes), self.assertRaises(StreamsError):
                self.intake.accept(self.principal, self.source(**changes), stream='etl')
        first = self.intake.accept(self.principal, self.source(), stream='etl')
        relay.record_ruling(self.stream, '2026-11-03T00:00:00Z', 'Policy', first)
        changed = self.intake.accept(self.principal, self.source(body='Keep drive on. Changed bytes.'), stream='etl')
        with self.assertRaises(StreamsError):
            relay.record_ruling(self.stream, '2026-11-03T00:00:00Z', 'Policy', changed)
