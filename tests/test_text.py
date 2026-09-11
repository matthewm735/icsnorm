from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from icsnorm.text import escape_text, unescape_text


class EscapeTextTests(unittest.TestCase):
    def test_plain_text_is_unchanged(self):
        self.assertEqual(escape_text("Lunch with Sam"), "Lunch with Sam")

    def test_backslash_is_escaped(self):
        self.assertEqual(escape_text("C:\\path"), "C:\\\\path")

    def test_semicolon_is_escaped(self):
        self.assertEqual(escape_text("a;b"), "a\\;b")

    def test_comma_is_escaped(self):
        self.assertEqual(escape_text("a,b"), "a\\,b")

    def test_newline_is_escaped(self):
        self.assertEqual(escape_text("line one\nline two"), "line one\\nline two")

    def test_crlf_is_escaped_as_a_single_n(self):
        self.assertEqual(escape_text("line one\r\nline two"), "line one\\nline two")

    def test_bare_cr_is_escaped_as_n(self):
        self.assertEqual(escape_text("line one\rline two"), "line one\\nline two")

    def test_all_special_characters_together(self):
        self.assertEqual(escape_text("a\\b;c,d\ne"), "a\\\\b\\;c\\,d\\ne")


class UnescapeTextTests(unittest.TestCase):
    def test_plain_text_is_unchanged(self):
        self.assertEqual(unescape_text("Lunch with Sam"), "Lunch with Sam")

    def test_escaped_backslash(self):
        self.assertEqual(unescape_text("C:\\\\path"), "C:\\path")

    def test_escaped_semicolon(self):
        self.assertEqual(unescape_text("a\\;b"), "a;b")

    def test_escaped_comma(self):
        self.assertEqual(unescape_text("a\\,b"), "a,b")

    def test_lowercase_n_is_newline(self):
        self.assertEqual(unescape_text("a\\nb"), "a\nb")

    def test_uppercase_n_is_also_newline(self):
        self.assertEqual(unescape_text("a\\Nb"), "a\nb")

    def test_unrecognized_escape_drops_the_backslash(self):
        self.assertEqual(unescape_text("a\\zb"), "azb")

    def test_trailing_lone_backslash_is_kept(self):
        self.assertEqual(unescape_text("a\\"), "a\\")

    def test_round_trips_with_escape_text(self):
        original = "Meeting: room A\\B, floor 2;\nbring \\ printouts"
        self.assertEqual(unescape_text(escape_text(original)), original)


if __name__ == "__main__":
    unittest.main()
