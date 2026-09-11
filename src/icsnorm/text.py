"""Escaping and unescaping of TEXT property values, per RFC 5545 3.3.11.

Content line folding (see `lines.py`) operates on whole lines and knows
nothing about property values. This module is the layer above it: once
a line has been unfolded and split into name/value, a TEXT value (used
by SUMMARY, DESCRIPTION, LOCATION, CATEGORIES, and others) may contain
backslash-escaped characters that need decoding before use, and any
value being written out needs the reverse treatment so that literal
backslashes, commas, semicolons, or embedded newlines don't corrupt the
line structure.
"""

from __future__ import annotations

_ESCAPE_MAP = {
    "\\": "\\\\",
    ";": "\\;",
    ",": "\\,",
}


def escape_text(value: str) -> str:
    """Escape a raw string for use as a TEXT property value.

    Backslashes, semicolons, and commas are escaped so they aren't
    mistaken for structural characters, and embedded newlines are
    encoded as the two-character sequence "\\n" since a literal
    newline is not allowed inside a content line.
    """
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    return "".join(_ESCAPE_MAP.get(ch, "\\n" if ch == "\n" else ch) for ch in value)


def unescape_text(value: str) -> str:
    """Decode a TEXT property value into the raw string it represents.

    RFC 5545 only defines \\\\, \\;, \\,, \\n, and \\N as escape
    sequences. Real-world producers occasionally emit a backslash
    before some other character; rather than raising over it (this
    function has no way to report an error to the caller and isn't
    part of the strict/lenient validation path), the backslash is
    dropped and the following character is kept literally, which is
    what most other iCalendar implementations do.
    """
    out: list[str] = []
    i = 0
    n = len(value)
    while i < n:
        ch = value[i]
        if ch == "\\" and i + 1 < n:
            nxt = value[i + 1]
            out.append("\n" if nxt in ("n", "N") else nxt)
            i += 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)
