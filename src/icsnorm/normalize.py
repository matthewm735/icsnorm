"""Normalize a messy iCalendar document into strict, well-formed output.

The philosophy: by default `normalize()` refuses to guess. If the input
is malformed it raises `IcsFormatError` describing exactly what is
wrong, rather than silently reinterpreting the file. Passing
`lenient=True` allows a fixed set of formatting problems to be repaired
instead of rejected. A smaller set of problems (currently: an event
missing DTSTART) can never be auto-fixed, because there is no safe
value to invent, and always raise regardless of `lenient`.

Single-value TEXT properties (SUMMARY, DESCRIPTION, and the like) are
checked against the escaping rules in `text.py`: a backslash that
isn't part of a recognized escape sequence is a formatting problem
like any other, fixed in lenient mode by decoding and re-encoding the
value.
"""

from __future__ import annotations

import uuid

from .lines import fold_line, unfold
from .text import escape_text, unescape_text

_REQUIRED_TOP_LEVEL = (
    ("VERSION", "VERSION:2.0"),
    ("PRODID", "PRODID:-//icsnorm//normalize//EN"),
)

# Single-value TEXT properties (RFC 5545 3.8.1.*). CATEGORIES is left out
# on purpose: it's a comma-separated *list* of TEXT values, where the
# commas are unescaped separators rather than part of one value, and
# escape_text()/unescape_text() don't know how to split a list.
_TEXT_PROPERTIES = {"SUMMARY", "DESCRIPTION", "LOCATION", "COMMENT", "CONTACT", "TZNAME"}

_VALID_ESCAPES = {"\\", ";", ",", "n", "N"}


class IcsFormatError(ValueError):
    """Raised when input is not well-formed and could not be repaired."""

    def __init__(self, issues: list[str]):
        super().__init__("; ".join(issues))
        self.issues = issues


def normalize(text: str, lenient: bool = False) -> str:
    """Return a strict, well-formed version of an iCalendar document.

    Raises IcsFormatError if the input has problems and either
    `lenient` is False, or the problem is one that can't be fixed
    without inventing data (see module docstring).
    """
    issues: list[str] = []
    hard_errors: list[str] = []

    if text.startswith("﻿"):
        if not lenient:
            issues.append("input starts with a UTF-8 byte order mark")
        text = text[1:]

    text, ending_issue = _normalize_line_endings(text, lenient)
    if ending_issue:
        issues.append(ending_issue)

    text, whitespace_issues = _strip_trailing_whitespace(text, lenient)
    issues.extend(whitespace_issues)

    text, blank_issue = _drop_blank_lines(text, lenient)
    if blank_issue:
        issues.append(blank_issue)

    content_lines = unfold(text)

    content_lines, escaping_issues = _check_text_escaping(content_lines, lenient)
    issues.extend(escaping_issues)

    content_lines, wrapper_issues = _ensure_calendar_wrapper(content_lines, lenient)
    issues.extend(wrapper_issues)

    content_lines, required_issues = _ensure_required_properties(content_lines, lenient)
    issues.extend(required_issues)

    content_lines, event_issues, event_hard_errors = _check_events(content_lines, lenient)
    issues.extend(event_issues)
    hard_errors.extend(event_hard_errors)

    if hard_errors:
        raise IcsFormatError(hard_errors + issues)
    if issues and not lenient:
        raise IcsFormatError(issues)

    folded = [fold_line(line) for line in content_lines]
    return "\r\n".join(folded) + "\r\n" if folded else ""


def _normalize_line_endings(text: str, lenient: bool) -> tuple[str, str | None]:
    bad = False
    for idx, ch in enumerate(text):
        if ch == "\n" and (idx == 0 or text[idx - 1] != "\r"):
            bad = True
            break
        if ch == "\r" and (idx + 1 >= len(text) or text[idx + 1] != "\n"):
            bad = True
            break
    if not bad:
        return text, None
    fixed = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n")
    return fixed, "line endings are not CRLF" if not lenient else None


def _strip_trailing_whitespace(text: str, lenient: bool) -> tuple[str, list[str]]:
    raw_lines = text.split("\r\n")
    body = raw_lines[:-1] if raw_lines and raw_lines[-1] == "" else raw_lines
    if not any(line != line.rstrip(" \t") for line in body):
        return text, []
    issues = [] if lenient else ["one or more lines have trailing whitespace"]
    stripped = [line.rstrip(" \t") for line in raw_lines]
    return "\r\n".join(stripped), issues


def _drop_blank_lines(text: str, lenient: bool) -> tuple[str, str | None]:
    raw_lines = text.split("\r\n")
    body = raw_lines[:-1] if raw_lines and raw_lines[-1] == "" else raw_lines
    if not any(line == "" for line in body):
        return text, None
    issue = None if lenient else "input contains blank lines"
    kept = [line for line in body if line != ""]
    return ("\r\n".join(kept) + "\r\n" if kept else ""), issue


def _ensure_calendar_wrapper(lines: list[str], lenient: bool) -> tuple[list[str], list[str]]:
    issues = []
    lines = list(lines)
    if not lines or lines[0].upper() != "BEGIN:VCALENDAR":
        issues.append("does not start with BEGIN:VCALENDAR")
        if lenient:
            lines.insert(0, "BEGIN:VCALENDAR")
    if not lines or lines[-1].upper() != "END:VCALENDAR":
        issues.append("does not end with END:VCALENDAR")
        if lenient:
            lines.append("END:VCALENDAR")
    return lines, ([] if lenient else issues)


def _ensure_required_properties(lines: list[str], lenient: bool) -> tuple[list[str], list[str]]:
    issues = []
    lines = list(lines)
    insert_at = 1 if lines and lines[0].upper() == "BEGIN:VCALENDAR" else 0
    for name, default_line in _REQUIRED_TOP_LEVEL:
        if not any(_prop_name(line) == name for line in lines):
            issues.append(f"missing required property {name}")
            if lenient:
                lines.insert(insert_at, default_line)
    return lines, ([] if lenient else issues)


def _check_events(lines: list[str], lenient: bool) -> tuple[list[str], list[str], list[str]]:
    issues: list[str] = []
    hard_errors: list[str] = []
    output: list[str] = []
    in_event = False
    event_props: set[str] = set()
    event_index = 0

    for line in lines:
        upper = line.upper()
        if upper == "BEGIN:VEVENT":
            in_event = True
            event_index += 1
            event_props = set()
            output.append(line)
            continue
        if upper == "END:VEVENT":
            if "UID" not in event_props:
                issues.append(f"VEVENT #{event_index} has no UID")
                if lenient:
                    output.append(f"UID:{uuid.uuid4()}@icsnorm.local")
            if "DTSTART" not in event_props:
                hard_errors.append(f"VEVENT #{event_index} has no DTSTART")
            in_event = False
            output.append(line)
            continue
        if in_event:
            event_props.add(_prop_name(line))
        output.append(line)

    return output, ([] if lenient else issues), hard_errors


def _prop_name(line: str) -> str:
    candidates = [i for i in (line.find(":"), line.find(";")) if i != -1]
    if not candidates:
        return line.upper()
    return line[: min(candidates)].upper()


def _split_name_and_value(line: str) -> tuple[str, str] | None:
    """Split a content line into its "NAME[;params]" head and its value.

    The split happens on the first colon that isn't inside a quoted
    parameter value (RFC 5545 allows a ':' inside a DQUOTE-delimited
    param-value, e.g. `TZID="/some:weird/zone"`). Returns None if the
    line has no unquoted colon at all.
    """
    in_quotes = False
    for i, ch in enumerate(line):
        if ch == '"':
            in_quotes = not in_quotes
        elif ch == ":" and not in_quotes:
            return line[:i], line[i + 1 :]
    return None


def _has_invalid_text_escaping(value: str) -> bool:
    i = 0
    n = len(value)
    while i < n:
        if value[i] == "\\":
            if i + 1 >= n or value[i + 1] not in _VALID_ESCAPES:
                return True
            i += 2
        else:
            i += 1
    return False


def _check_text_escaping(lines: list[str], lenient: bool) -> tuple[list[str], list[str]]:
    issues: list[str] = []
    output: list[str] = []
    for line in lines:
        split = _split_name_and_value(line)
        if split is None:
            output.append(line)
            continue
        head, value = split
        if _prop_name(line) not in _TEXT_PROPERTIES or not _has_invalid_text_escaping(value):
            output.append(line)
            continue
        issues.append(f"{_prop_name(line)} has an invalid backslash escape sequence")
        if lenient:
            output.append(f"{head}:{escape_text(unescape_text(value))}")
        else:
            output.append(line)
    return output, ([] if lenient else issues)
