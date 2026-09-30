"""Consistency checks between an event's DTSTART, DTEND and DURATION.

None of these problems can be repaired without guessing which value the
author meant, so the caller treats every message returned here as a hard
error, lenient mode or not.

Only what can be decided from the event alone is checked. Whether a TZID
names a real zone needs the calendar's VTIMEZONE blocks and is not
handled here.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import NamedTuple, Optional, Union


class _Moment(NamedTuple):
    # "date", "floating", "utc" or "tzid"
    kind: str
    tzid: Optional[str]
    value: Union[date, datetime]


def _split_params(head: str) -> list[str]:
    """Split "NAME;A=1;B=\"x;y\"" on semicolons outside double quotes."""
    parts: list[str] = []
    current: list[str] = []
    in_quotes = False
    for ch in head:
        if ch == '"':
            in_quotes = not in_quotes
        if ch == ";" and not in_quotes:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    parts.append("".join(current))
    return parts


def _parse_moment(name: str, head: str, value: str) -> tuple[Optional[_Moment], Optional[str]]:
    params: dict[str, str] = {}
    for param in _split_params(head)[1:]:
        key, sep, val = param.partition("=")
        if sep:
            params[key.upper()] = val.strip('"')

    # Only the first value matters; RFC 5545 allows a single one here.
    value = value.strip()
    declared = params.get("VALUE", "").upper()
    is_date = declared == "DATE" or (declared == "" and "T" not in value.upper())

    try:
        if is_date:
            return _Moment("date", None, datetime.strptime(value, "%Y%m%d").date()), None
        utc = value.endswith(("Z", "z"))
        parsed = datetime.strptime(value.rstrip("Zz"), "%Y%m%dT%H%M%S")
    except ValueError:
        return None, f"{name} has an unparseable value {value!r}"

    tzid = params.get("TZID")
    if utc and tzid:
        return None, f"{name} has both a TZID and a UTC time"
    if utc:
        return _Moment("utc", None, parsed), None
    if tzid:
        return _Moment("tzid", tzid, parsed), None
    return _Moment("floating", None, parsed), None


def check_event_times(props: dict[str, tuple[str, str]], label: str) -> list[str]:
    """Check the time properties of one VEVENT.

    `props` maps an upper-case property name to its (head, value) pair,
    where head is the text before the value's colon. `label` is how the
    event is named in messages, e.g. "VEVENT #2".
    """
    errors: list[str] = []
    moments: dict[str, _Moment] = {}
    for name in ("DTSTART", "DTEND"):
        if name not in props:
            continue
        moment, error = _parse_moment(name, *props[name])
        if error:
            errors.append(f"{label} {error}")
        elif moment is not None:
            moments[name] = moment

    if "DTEND" in props and "DURATION" in props:
        errors.append(f"{label} has both DTEND and DURATION")

    start = moments.get("DTSTART")
    end = moments.get("DTEND")
    if start is None or end is None:
        return errors

    if (start.kind == "date") != (end.kind == "date"):
        start_type = "DATE" if start.kind == "date" else "DATE-TIME"
        end_type = "DATE" if end.kind == "date" else "DATE-TIME"
        errors.append(f"{label} DTSTART is a {start_type} but DTEND is a {end_type}")
    elif (start.kind, start.tzid) == (end.kind, end.tzid) and end.value < start.value:
        # Different zone kinds can't be ordered without zone data, so the
        # comparison only runs when both sides are in the same frame.
        errors.append(f"{label} DTEND is before DTSTART")
    return errors
