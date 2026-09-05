from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from icsnorm.lines import fold_line, unfold


class UnfoldTests(unittest.TestCase):
    def test_single_line(self):
        self.assertEqual(unfold("SUMMARY:Hello\r\n"), ["SUMMARY:Hello"])

    def test_no_trailing_blank_entry(self):
        self.assertEqual(unfold("A:1\r\nB:2\r\n"), ["A:1", "B:2"])

    def test_space_continuation_joins_without_the_leading_space(self):
        # RFC 5545 3.1: the folding whitespace character is not part of
        # the content and is dropped, not replaced with a space.
        text = "SUMMARY:Hello\r\n World\r\n"
        self.assertEqual(unfold(text), ["SUMMARY:HelloWorld"])

    def test_tab_continuation(self):
        text = "SUMMARY:Hello\r\n\tWorld\r\n"
        self.assertEqual(unfold(text), ["SUMMARY:HelloWorld"])

    def test_multiple_continuations(self):
        text = "SUMMARY:A\r\n B\r\n C\r\n"
        self.assertEqual(unfold(text), ["SUMMARY:ABC"])

    def test_unrelated_lines_stay_separate(self):
        text = "BEGIN:VEVENT\r\nSUMMARY:Hi\r\nEND:VEVENT\r\n"
        self.assertEqual(unfold(text), ["BEGIN:VEVENT", "SUMMARY:Hi", "END:VEVENT"])

    def test_empty_input(self):
        self.assertEqual(unfold(""), [])


class FoldLineTests(unittest.TestCase):
    def test_short_line_is_unchanged(self):
        line = "SUMMARY:short"
        self.assertEqual(fold_line(line), line)

    def test_line_exactly_at_limit_is_unchanged(self):
        line = "X" * 75
        self.assertEqual(fold_line(line, limit=75), line)

    def test_long_ascii_line_is_folded_with_crlf_space(self):
        line = "X" * 100
        folded = fold_line(line, limit=75)
        parts = folded.split("\r\n ")
        self.assertEqual("".join(parts), line)
        self.assertLessEqual(len(parts[0].encode("utf-8")), 75)
        for part in parts[1:]:
            self.assertLessEqual(len(part.encode("utf-8")), 74)

    def test_does_not_split_a_multibyte_character(self):
        # 74 ASCII bytes plus one 2-byte character lands the naive cut
        # in the middle of the character; folding must back off instead.
        line = "X" * 74 + "é"
        folded = fold_line(line, limit=75)
        self.assertEqual(folded, "X" * 74 + "\r\n é")
        for part in folded.split("\r\n "):
            part.encode("utf-8").decode("utf-8")  # raises if a char got split

    def test_round_trips_through_unfold(self):
        line = "DESCRIPTION:" + "word " * 30
        folded = fold_line(line, limit=75)
        rejoined = unfold(folded + "\r\n")
        self.assertEqual(rejoined, [line])


if __name__ == "__main__":
    unittest.main()
