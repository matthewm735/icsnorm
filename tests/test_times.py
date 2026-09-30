from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from icsnorm.normalize import IcsFormatError, normalize
from icsnorm.times import check_event_times


def event(*lines: str) -> str:
    body = "".join(line + "\r\n" for line in lines)
    return (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//icsnorm//normalize//EN\r\n"
        "BEGIN:VEVENT\r\n"
        "UID:abc123@example.com\r\n" + body + "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )


def props(*lines: str) -> dict:
    result = {}
    for line in lines:
        head, _, value = line.partition(":")
        result.setdefault(head.split(";")[0], (head, value))
    return result


class CheckEventTimesTests(unittest.TestCase):
    def test_consistent_utc_pair_is_clean(self):
        p = props("DTSTART:20240101T090000Z", "DTEND:20240101T100000Z")
        self.assertEqual(check_event_times(p, "VEVENT #1"), [])

    def test_equal_start_and_end_is_allowed(self):
        p = props("DTSTART:20240101T090000Z", "DTEND:20240101T090000Z")
        self.assertEqual(check_event_times(p, "VEVENT #1"), [])

    def test_end_before_start(self):
        p = props("DTSTART:20240101T100000Z", "DTEND:20240101T090000Z")
        self.assertEqual(check_event_times(p, "VEVENT #1"), ["VEVENT #1 DTEND is before DTSTART"])

    def test_end_before_start_in_same_tzid(self):
        p = props(
            "DTSTART;TZID=Europe/Paris:20240101T100000",
            "DTEND;TZID=Europe/Paris:20240101T090000",
        )
        self.assertEqual(len(check_event_times(p, "VEVENT #1")), 1)

    def test_different_frames_are_not_compared(self):
        p = props("DTSTART:20240101T100000Z", "DTEND;TZID=Asia/Tokyo:20240101T090000")
        self.assertEqual(check_event_times(p, "VEVENT #1"), [])

    def test_date_start_with_datetime_end(self):
        p = props("DTSTART;VALUE=DATE:20240101", "DTEND:20240101T100000Z")
        self.assertEqual(
            check_event_times(p, "VEVENT #1"),
            ["VEVENT #1 DTSTART is a DATE but DTEND is a DATE-TIME"],
        )

    def test_quoted_tzid_with_semicolon_is_read_whole(self):
        p = props('DTSTART;TZID="Custom;Zone":20240101T090000', "DTEND;TZID=\"Custom;Zone\":20240101T080000")
        self.assertEqual(len(check_event_times(p, "VEVENT #1")), 1)

    def test_dtend_and_duration_together(self):
        p = props("DTSTART:20240101T090000Z", "DTEND:20240101T100000Z", "DURATION:PT1H")
        self.assertEqual(check_event_times(p, "VEVENT #1"), ["VEVENT #1 has both DTEND and DURATION"])

    def test_tzid_with_utc_suffix(self):
        p = props("DTSTART;TZID=Europe/Paris:20240101T090000Z")
        self.assertEqual(
            check_event_times(p, "VEVENT #1"),
            ["VEVENT #1 DTSTART has both a TZID and a UTC time"],
        )

    def test_unparseable_value(self):
        p = props("DTSTART:20241301T090000Z")
        errors = check_event_times(p, "VEVENT #1")
        self.assertEqual(len(errors), 1)
        self.assertIn("unparseable", errors[0])


class NormalizeTimeTests(unittest.TestCase):
    def test_valid_all_day_event_passes(self):
        doc = event("DTSTART;VALUE=DATE:20240101", "DTEND;VALUE=DATE:20240102")
        self.assertEqual(normalize(doc), doc)

    def test_end_before_start_is_rejected_even_when_lenient(self):
        doc = event("DTSTART:20240101T100000Z", "DTEND:20240101T090000Z")
        for lenient in (False, True):
            with self.assertRaises(IcsFormatError) as ctx:
                normalize(doc, lenient=lenient)
            self.assertIn("VEVENT #1 DTEND is before DTSTART", ctx.exception.issues)

    def test_second_event_is_numbered_correctly(self):
        good = event("DTSTART:20240101T090000Z")
        second = (
            "BEGIN:VEVENT\r\nUID:two@example.com\r\n"
            "DTSTART:20240102T100000Z\r\nDTEND:20240102T090000Z\r\nEND:VEVENT\r\n"
        )
        doc = good.replace("END:VCALENDAR\r\n", second + "END:VCALENDAR\r\n")
        with self.assertRaises(IcsFormatError) as ctx:
            normalize(doc)
        self.assertEqual(ctx.exception.issues, ["VEVENT #2 DTEND is before DTSTART"])

    def test_alarm_duration_does_not_count_as_event_duration(self):
        doc = event(
            "DTSTART:20240101T090000Z",
            "DTEND:20240101T100000Z",
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            "DESCRIPTION:soon",
            "TRIGGER:-PT15M",
            "DURATION:PT5M",
            "REPEAT:2",
            "END:VALARM",
        )
        self.assertEqual(normalize(doc), doc)


if __name__ == "__main__":
    unittest.main()
