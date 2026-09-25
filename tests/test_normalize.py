from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from icsnorm.normalize import IcsFormatError, normalize

VALID = (
    "BEGIN:VCALENDAR\r\n"
    "VERSION:2.0\r\n"
    "PRODID:-//icsnorm//normalize//EN\r\n"
    "BEGIN:VEVENT\r\n"
    "UID:abc123@example.com\r\n"
    "DTSTART:20240101T090000Z\r\n"
    "END:VEVENT\r\n"
    "END:VCALENDAR\r\n"
)


class ValidInputTests(unittest.TestCase):
    def test_already_valid_document_passes_through_unchanged(self):
        self.assertEqual(normalize(VALID), VALID)

    def test_valid_document_is_unchanged_in_lenient_mode_too(self):
        self.assertEqual(normalize(VALID, lenient=True), VALID)


class LineEndingTests(unittest.TestCase):
    def setUp(self):
        self.bare_lf = VALID.replace("\r\n", "\n")

    def test_strict_rejects_bare_lf(self):
        with self.assertRaises(IcsFormatError) as ctx:
            normalize(self.bare_lf)
        self.assertIn("line endings are not CRLF", ctx.exception.issues)

    def test_lenient_repairs_bare_lf(self):
        self.assertEqual(normalize(self.bare_lf, lenient=True), VALID)


class ByteOrderMarkTests(unittest.TestCase):
    def test_strict_rejects_leading_bom(self):
        with self.assertRaises(IcsFormatError) as ctx:
            normalize("﻿" + VALID)
        self.assertIn("input starts with a UTF-8 byte order mark", ctx.exception.issues)

    def test_lenient_strips_leading_bom(self):
        self.assertEqual(normalize("﻿" + VALID, lenient=True), VALID)


class TrailingWhitespaceTests(unittest.TestCase):
    def setUp(self):
        self.dirty = VALID.replace("UID:abc123@example.com", "UID:abc123@example.com  \t")

    def test_strict_rejects_trailing_whitespace(self):
        with self.assertRaises(IcsFormatError) as ctx:
            normalize(self.dirty)
        self.assertIn("one or more lines have trailing whitespace", ctx.exception.issues)

    def test_lenient_strips_trailing_whitespace(self):
        self.assertEqual(normalize(self.dirty, lenient=True), VALID)


class BlankLineTests(unittest.TestCase):
    def setUp(self):
        self.dirty = VALID.replace("END:VEVENT\r\n", "END:VEVENT\r\n\r\n")

    def test_strict_rejects_blank_lines(self):
        with self.assertRaises(IcsFormatError) as ctx:
            normalize(self.dirty)
        self.assertIn("input contains blank lines", ctx.exception.issues)

    def test_lenient_drops_blank_lines(self):
        self.assertEqual(normalize(self.dirty, lenient=True), VALID)


class CalendarWrapperTests(unittest.TestCase):
    def setUp(self):
        self.no_wrapper = VALID.replace("BEGIN:VCALENDAR\r\n", "").replace(
            "END:VCALENDAR\r\n", ""
        )

    def test_strict_rejects_missing_wrapper(self):
        with self.assertRaises(IcsFormatError) as ctx:
            normalize(self.no_wrapper)
        self.assertIn("does not start with BEGIN:VCALENDAR", ctx.exception.issues)
        self.assertIn("does not end with END:VCALENDAR", ctx.exception.issues)

    def test_lenient_adds_wrapper(self):
        self.assertEqual(normalize(self.no_wrapper, lenient=True), VALID)


class RequiredPropertyTests(unittest.TestCase):
    def setUp(self):
        self.no_prodid = VALID.replace("PRODID:-//icsnorm//normalize//EN\r\n", "")
        self.no_version = VALID.replace("VERSION:2.0\r\n", "")

    def test_strict_rejects_missing_prodid(self):
        with self.assertRaises(IcsFormatError) as ctx:
            normalize(self.no_prodid)
        self.assertIn("missing required property PRODID", ctx.exception.issues)

    def test_lenient_adds_missing_prodid(self):
        # PRODID and VERSION are inserted independently right after
        # BEGIN:VCALENDAR, so a fix-up can reorder them relative to
        # whichever one was already present.
        result = normalize(self.no_prodid, lenient=True)
        self.assertTrue(result.startswith("BEGIN:VCALENDAR\r\n"))
        self.assertIn("PRODID:-//icsnorm//normalize//EN\r\n", result)
        self.assertIn("VERSION:2.0\r\n", result)

    def test_strict_rejects_missing_version(self):
        with self.assertRaises(IcsFormatError) as ctx:
            normalize(self.no_version)
        self.assertIn("missing required property VERSION", ctx.exception.issues)

    def test_lenient_adds_missing_version(self):
        self.assertEqual(normalize(self.no_version, lenient=True), VALID)


class EventUidTests(unittest.TestCase):
    def setUp(self):
        self.no_uid = VALID.replace("UID:abc123@example.com\r\n", "")

    def test_strict_rejects_missing_uid(self):
        with self.assertRaises(IcsFormatError) as ctx:
            normalize(self.no_uid)
        self.assertIn("VEVENT #1 has no UID", ctx.exception.issues)

    def test_lenient_generates_a_uid(self):
        result = normalize(self.no_uid, lenient=True)
        lines = result.split("\r\n")
        uid_lines = [line for line in lines if line.startswith("UID:")]
        self.assertEqual(len(uid_lines), 1)
        self.assertTrue(uid_lines[0].endswith("@icsnorm.local"))


class EventDtstartTests(unittest.TestCase):
    def setUp(self):
        self.no_dtstart = VALID.replace("DTSTART:20240101T090000Z\r\n", "")

    def test_strict_rejects_missing_dtstart(self):
        with self.assertRaises(IcsFormatError) as ctx:
            normalize(self.no_dtstart)
        self.assertIn("VEVENT #1 has no DTSTART", ctx.exception.issues)

    def test_lenient_still_rejects_missing_dtstart(self):
        # There is no safe value to invent for a start time, so this is
        # a hard error regardless of --lenient.
        with self.assertRaises(IcsFormatError) as ctx:
            normalize(self.no_dtstart, lenient=True)
        self.assertIn("VEVENT #1 has no DTSTART", ctx.exception.issues)


class TextEscapingTests(unittest.TestCase):
    def setUp(self):
        self.bad_escape = VALID.replace(
            "UID:abc123@example.com\r\n",
            "UID:abc123@example.com\r\nSUMMARY:Room A\\B, unannounced\r\n",
        )

    def test_strict_rejects_invalid_escape_sequence(self):
        with self.assertRaises(IcsFormatError) as ctx:
            normalize(self.bad_escape)
        self.assertIn("SUMMARY has an invalid backslash escape sequence", ctx.exception.issues)

    def test_lenient_repairs_invalid_escape_sequence(self):
        result = normalize(self.bad_escape, lenient=True)
        # The stray backslash before "B" isn't a recognized escape, so it's
        # dropped; the comma is a real separator character and gets a
        # proper escape added.
        self.assertIn("SUMMARY:Room AB\\, unannounced\r\n", result)

    def test_strict_accepts_properly_escaped_text(self):
        clean = VALID.replace(
            "UID:abc123@example.com\r\n",
            "UID:abc123@example.com\r\nSUMMARY:Room A\\, B\\; C\r\n",
        )
        self.assertEqual(normalize(clean), clean)

    def test_trailing_lone_backslash_is_flagged_and_repaired(self):
        dirty = VALID.replace(
            "UID:abc123@example.com\r\n",
            "UID:abc123@example.com\r\nLOCATION:Room A\\\r\n",
        )
        with self.assertRaises(IcsFormatError) as ctx:
            normalize(dirty)
        self.assertIn("LOCATION has an invalid backslash escape sequence", ctx.exception.issues)
        result = normalize(dirty, lenient=True)
        self.assertIn("LOCATION:Room A\\\\\r\n", result)


class CategoriesEscapingTests(unittest.TestCase):
    def setUp(self):
        self.bad_escape = VALID.replace(
            "UID:abc123@example.com\r\n",
            "UID:abc123@example.com\r\nCATEGORIES:Work,Room A\\B,Travel\r\n",
        )

    def test_strict_rejects_invalid_escape_in_a_list_item(self):
        with self.assertRaises(IcsFormatError) as ctx:
            normalize(self.bad_escape)
        self.assertIn("CATEGORIES has an invalid backslash escape sequence", ctx.exception.issues)

    def test_lenient_repairs_only_the_bad_item(self):
        result = normalize(self.bad_escape, lenient=True)
        self.assertIn("CATEGORIES:Work,Room AB,Travel\r\n", result)

    def test_strict_accepts_properly_escaped_list(self):
        clean = VALID.replace(
            "UID:abc123@example.com\r\n",
            "UID:abc123@example.com\r\nCATEGORIES:Work,Room A\\, B\r\n",
        )
        self.assertEqual(normalize(clean), clean)


class EmptyInputTests(unittest.TestCase):
    def test_empty_input_is_all_missing_pieces_in_lenient_mode(self):
        result = normalize("", lenient=True)
        self.assertTrue(result.startswith("BEGIN:VCALENDAR\r\n"))
        self.assertTrue(result.endswith("END:VCALENDAR\r\n"))
        self.assertIn("VERSION:2.0\r\n", result)
        self.assertIn("PRODID:-//icsnorm//normalize//EN\r\n", result)


if __name__ == "__main__":
    unittest.main()
