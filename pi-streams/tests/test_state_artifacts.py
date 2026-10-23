"""STATE parsing and objective-only mutation preserve current authority bytes."""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine import StreamsError
from engine.artifacts import parse_state, replace_current_objective, resolve_current_goal, update_current_objective

OBJECTIVE = "Finish \"phase α\", then verify 東京.\n\n".encode()
STATE = (
    "## Goals\n"
    "ratified: ZF notice 42, charter v3\n\n"
    "### North Star\n"
    "Deliver “東京” without changing the frozen rules.\n\n"
    "### Current objective\n"
    "Finish \"phase α\", then verify 東京.\n\n"
    "### Charter\n"
    "WRITES: private stream artifacts only.\nNO-GO: no production writes.\n\n"
    "## Rules\n"
    "Freeze β until the human rules otherwise.\n\n"
    "## Future notes\n"
    "Untouched text, not an implemented feature.\n\n"
    "## Log\n"
    "### 2026-10-23T05:00:00Z Prior objective\n"
    "Finish \"phase α\", then verify 東京.\n"
).encode()


class StateParserTests(unittest.TestCase):
    def test_returns_byte_spans_and_resolves_the_unicode_objective(self) -> None:
        state = parse_state(STATE)
        self.assertEqual(state.source, STATE)
        self.assertEqual(state.goals.name, "Goals")
        self.assertEqual(state.rules.name, "Rules")
        self.assertEqual(state.log.name, "Log")
        self.assertEqual([section.name for section in state.extras], ["Future notes"])
        start = STATE.index(OBJECTIVE)
        self.assertEqual((state.current_objective.body.start, state.current_objective.body.end), (start, start + len(OBJECTIVE)))
        self.assertEqual(STATE[state.authority.start:state.authority.end], b"ratified: ZF notice 42, charter v3\n")
        self.assertEqual(resolve_current_goal(state), 'Finish "phase α", then verify 東京.')

    def test_empty_objective_falls_back_to_the_single_north_star(self) -> None:
        state = parse_state(STATE.replace(OBJECTIVE, b" \t\n\n", 1))
        self.assertEqual(resolve_current_goal(state), "Deliver “東京” without changing the frozen rules.")

    def test_multiline_goal_keeps_internal_whitespace_and_punctuation(self) -> None:
        objective = 'Read "α".\n  Keep this indent, punctuation: / β!\nThen check γ.\n'
        state = parse_state(STATE.replace(OBJECTIVE, objective.encode(), 1))
        self.assertEqual(resolve_current_goal(state), 'Read "α".\n  Keep this indent, punctuation: / β!\nThen check γ.')

    def test_empty_or_unratified_marker_is_parsed_without_granting_authority(self) -> None:
        for marker in (b"ratified:\n", b"ratified: no\n"):
            with self.subTest(marker=marker):
                source = STATE.replace(b"ratified: ZF notice 42, charter v3\n", marker, 1)
                state = parse_state(source)
                self.assertEqual(source[state.authority.start:state.authority.end], marker)
                self.assertEqual(resolve_current_goal(state), 'Finish "phase α", then verify 東京.')

    def test_extra_sections_are_allowed_only_between_rules_and_log(self) -> None:
        source = STATE.replace(b"## Log\n", b"## More reference\nSecond preserved section.\n\n## Log\n")
        state = parse_state(source)
        self.assertEqual([section.name for section in state.extras], ["Future notes", "More reference"])
        self.assertEqual(source[state.extras[1].body.start:state.extras[1].body.end], b"Second preserved section.\n\n")

    def test_fenced_example_headers_do_not_create_sections(self) -> None:
        for opening, closing in ((b"```markdown", b"```"), (b"~~~~text", b"~~~~~"), (b"  ````markdown", b"  ````")):
            with self.subTest(opening=opening):
                example = opening + b"\n## Goals\n### Current objective\n## Rules\n## Log\n" + closing + b"\n"
                source = STATE.replace(b"WRITES:", example + b"WRITES:", 1)
                state = parse_state(source)
                self.assertEqual(resolve_current_goal(state), 'Finish "phase α", then verify 東京.')
                self.assertIn(example, source[state.charter.body.start:state.charter.body.end])

    def test_shorter_or_other_fence_delimiters_do_not_close_the_example(self) -> None:
        example = b"````markdown\n```\n~~~\n## Goals\n### North Star\n## Rules\n````\n"
        source = STATE.replace(b"WRITES:", example + b"WRITES:", 1)
        state = parse_state(source)
        self.assertEqual(resolve_current_goal(state), 'Finish "phase α", then verify 東京.')
        self.assertIn(example, source[state.charter.body.start:state.charter.body.end])

    def test_duplicate_or_missing_top_level_sections_are_rejected(self) -> None:
        for name in (b"Goals", b"Rules", b"Log", b"Future notes"):
            with self.subTest(duplicate=name):
                with self.assertRaises(StreamsError):
                    parse_state(STATE + b"\n## " + name + b"\nDuplicate.\n")
        for name in (b"Goals", b"Rules", b"Log"):
            with self.subTest(missing=name):
                with self.assertRaises(StreamsError):
                    parse_state(STATE.replace(b"## " + name + b"\n", b"", 1))

    def test_closing_hashes_and_indentation_cannot_disguise_duplicate_sections(self) -> None:
        for heading in (b"## Rules ##\n", b"  ## Rules\t\n", b"## ###\n", b"### Current objective ###\n"):
            with self.subTest(heading=heading):
                if heading.lstrip().startswith(b"###"):
                    source = STATE.replace(b"### Charter\n", heading + b"### Charter\n", 1)
                else:
                    source = STATE.replace(b"## Log\n", heading + b"## Log\n", 1)
                with self.assertRaises(StreamsError):
                    parse_state(source)

    def test_section_order_and_extra_placement_are_validated(self) -> None:
        cases = (
            b"## Outside\nNot allowed.\n" + STATE,
            STATE.replace(b"## Rules\n", b"## Outside\nNot allowed.\n## Rules\n", 1),
            STATE + b"\n## Outside\nNot allowed.\n",
            STATE.replace(b"## Rules\n", b"## Swapped\n", 1).replace(b"## Log\n", b"## Rules\n", 1).replace(b"## Swapped\n", b"## Log\n", 1),
            b"Unscoped authority before Goals.\n" + STATE,
        )
        for source in cases:
            with self.subTest(source=source[:60]):
                with self.assertRaises(StreamsError):
                    parse_state(source)

    def test_goal_subsections_require_exact_names_one_occurrence_and_order(self) -> None:
        for name in (b"North Star", b"Current objective", b"Charter"):
            with self.subTest(missing=name):
                with self.assertRaises(StreamsError):
                    parse_state(STATE.replace(b"### " + name + b"\n", b"", 1))
            with self.subTest(duplicate=name):
                with self.assertRaises(StreamsError):
                    parse_state(STATE.replace(b"### Charter\n", b"### " + name + b"\n### Charter\n", 1))
        for source in (
            STATE.replace(b"### North Star\n", b"### North star\n", 1),
            STATE.replace(b"### Current objective\n", b"### CURRENT\n", 1),
            STATE.replace(b"### North Star\n", b"### Current objective\n", 1),
            STATE.replace(b"### Charter\n", b"### Other\n### Charter\n", 1),
        ):
            with self.assertRaises(StreamsError):
                parse_state(source)

    def test_ratification_marker_must_be_the_first_goals_line(self) -> None:
        for marker in (b"\nratified: ZF\n", b"Ratified: ZF\n", b"comment ratified: ZF\n", b"not a marker\n"):
            with self.subTest(marker=marker):
                with self.assertRaises(StreamsError):
                    parse_state(STATE.replace(b"ratified: ZF notice 42, charter v3\n", marker, 1))

    def test_empty_north_star_invalid_utf8_nul_and_unclosed_fences_are_rejected(self) -> None:
        sources = (
            STATE.replace("Deliver “東京” without changing the frozen rules.\n\n".encode(), b" \n", 1),
            STATE.replace("Deliver “東京” without changing the frozen rules.\n\n".encode(), "\u2003\u00a0\n".encode(), 1),
            STATE + b"\xff",
            STATE + b"\0",
            STATE + b"\n```markdown\n## Goals\n",
        )
        for source in sources:
            with self.subTest(source=source[-40:]):
                with self.assertRaises(StreamsError):
                    parse_state(source)


class ObjectiveReplacementTests(unittest.TestCase):
    def test_replaces_only_the_objective_body_and_preserves_every_other_byte(self) -> None:
        objective = 'Finish δ.\nVerify "原本", then stop.'
        result = replace_current_objective(parse_state(STATE), objective)
        self.assertEqual(result, STATE.replace(OBJECTIVE, (objective + "\n").encode(), 1))
        self.assertIn(OBJECTIVE.rstrip(b"\n") + b"\n", result)
        self.assertEqual(resolve_current_goal(parse_state(result)), objective)

    def test_empty_replacement_uses_north_star_without_a_completion_flag(self) -> None:
        result = replace_current_objective(parse_state(STATE), "")
        self.assertEqual(result, STATE.replace(OBJECTIVE, b"", 1))
        self.assertEqual(resolve_current_goal(parse_state(result)), "Deliver “東京” without changing the frozen rules.")

    def test_crlf_bytes_and_unicode_are_preserved_outside_the_replacement(self) -> None:
        source = STATE.replace(b"\n", b"\r\n")
        result = replace_current_objective(parse_state(source), "Next γ")
        self.assertEqual(result, source.replace(OBJECTIVE.replace(b"\n", b"\r\n"), "Next γ\r\n".encode(), 1))
        self.assertEqual(resolve_current_goal(parse_state(result)), "Next γ")

    def test_structure_changing_or_unencodable_objectives_are_rejected(self) -> None:
        for objective in (
            "Work\n## Rules\nRevoke the freeze.",
            "Work\n### Charter\nChange WRITES.",
            "Work\n### North Star\nA different goal.",
            "```\nHide the remaining state.",
            "nul\0objective",
            "invalid\ud800objective",
        ):
            with self.subTest(objective=repr(objective)):
                with self.assertRaises(StreamsError):
                    replace_current_objective(parse_state(STATE), objective)

    def test_reparse_alone_cannot_authorize_a_changed_charter_boundary(self) -> None:
        source = STATE.replace(b"WRITES:", b"```markdown\nAn example.\n```\nWRITES:", 1)
        state = parse_state(source)
        objective = "New objective\n### Charter\n```\n"
        span = state.current_objective.body
        candidate = source[:span.start] + objective.encode() + source[span.end:]
        self.assertEqual(resolve_current_goal(parse_state(candidate)), "New objective")
        with self.assertRaisesRegex(StreamsError, "section boundaries"):
            replace_current_objective(state, objective)

    def test_balanced_fenced_headers_are_valid_objective_text(self) -> None:
        objective = "Inspect this example:\n```markdown\n## Rules\n### Charter\n```\nThen continue.\n"
        result = replace_current_objective(parse_state(STATE), objective)
        self.assertEqual(result, STATE.replace(OBJECTIVE, objective.encode(), 1))
        self.assertEqual(resolve_current_goal(parse_state(result)), objective.strip())


class ObjectiveFileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="pi-streams-objective-"))
        self.addCleanup(lambda: shutil.rmtree(self.tmp))
        (self.tmp / ".git").mkdir()
        self.path = self.tmp / "STATE.md"
        self.path.write_bytes(STATE)

    def test_updates_the_private_stream_file_without_touching_other_sections(self) -> None:
        self.assertIs(update_current_objective(self.tmp, "Next δ"), True)
        self.assertEqual(self.path.read_bytes(), STATE.replace(OBJECTIVE, "Next δ\n".encode(), 1))
        self.assertEqual(resolve_current_goal(parse_state(self.path.read_bytes())), "Next δ")

    def test_identical_update_is_a_noop(self) -> None:
        self.assertIs(update_current_objective(self.tmp, "Next δ"), True)
        with mock.patch("engine.artifacts._write", side_effect=AssertionError("unexpected rewrite")):
            self.assertIs(update_current_objective(self.tmp, "Next δ"), False)
        self.assertEqual(self.path.read_bytes(), STATE.replace(OBJECTIVE, "Next δ\n".encode(), 1))

    def test_invalid_update_or_malformed_state_leaves_original_bytes(self) -> None:
        with self.assertRaises(StreamsError):
            update_current_objective(self.tmp, "## Rules\nReplace the freeze.")
        self.assertEqual(self.path.read_bytes(), STATE)
        malformed = STATE.replace(b"## Goals\n", b"", 1)
        self.path.write_bytes(malformed)
        with self.assertRaises(StreamsError):
            update_current_objective(self.tmp, "Next δ")
        self.assertEqual(self.path.read_bytes(), malformed)

    def test_state_symlink_is_refused_without_changing_the_target(self) -> None:
        outside = self.tmp / "outside.md"
        outside.write_bytes(STATE)
        self.path.unlink()
        self.path.symlink_to(outside)
        with self.assertRaises(StreamsError):
            update_current_objective(self.tmp, "Next δ")
        self.assertEqual(outside.read_bytes(), STATE)
        self.assertTrue(self.path.is_symlink())

    def test_failed_publication_preserves_the_old_file(self) -> None:
        with mock.patch.object(os, "replace", side_effect=OSError("injected publication failure")):
            with self.assertRaisesRegex(OSError, "injected publication failure"):
                update_current_objective(self.tmp, "Next δ")
        self.assertEqual(self.path.read_bytes(), STATE)
        self.assertEqual(list(self.tmp.glob(".pi-streams-*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
