"""Low-level RFC 5545 content line handling: unfolding and folding.

An .ics file is a sequence of "content lines" that may be split across
several physical lines by inserting CRLF followed by a single space or
tab (a "fold"). Everything above this module works on unfolded content
lines; this module is the only place that knows about the fold format.
"""

from __future__ import annotations

FOLD_LIMIT = 75


def unfold(text: str) -> list[str]:
    """Join folded physical lines back into logical content lines.

    `text` must already use CRLF line endings. A physical line that
    starts with a space or tab is a continuation of the previous line;
    the leading whitespace character itself is not part of the content
    and is dropped.
    """
    raw_lines = text.split("\r\n")
    if raw_lines and raw_lines[-1] == "":
        raw_lines.pop()

    lines: list[str] = []
    for raw in raw_lines:
        if raw and raw[0] in (" ", "\t") and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return lines


def fold_line(line: str, limit: int = FOLD_LIMIT) -> str:
    """Fold a single content line to `limit` octets per physical line.

    Splitting is done on UTF-8 byte boundaries, backing off from the
    limit if it would land inside a multi-byte character, per RFC 5545
    section 3.1 ("lines of text SHOULD NOT exceed 75 octets").
    """
    data = line.encode("utf-8")
    if len(data) <= limit:
        return line

    parts: list[bytes] = []
    start = 0
    n = len(data)
    first = True
    while start < n:
        chunk_limit = limit if first else limit - 1
        end = min(start + chunk_limit, n)
        while end > start and end < n and (data[end] & 0xC0) == 0x80:
            end -= 1
        parts.append(data[start:end])
        start = end
        first = False
    return "\r\n ".join(part.decode("utf-8") for part in parts)
