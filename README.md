# icsnorm

A small tool that takes a messy `.ics` (iCalendar) file and turns it into
one that follows RFC 5545 properly.

Calendar exports from real software are inconsistent in ways that are
individually minor but that break parsers downstream: bare `\n` line
endings instead of `\r\n`, lines that were never folded and run past 75
octets, trailing whitespace left over from a text editor, blank lines
in the middle of the file, a `VEVENT` with no `UID`, a file missing
`VERSION` or `PRODID` entirely. Most tools either crash on this or
silently guess. `icsnorm` does neither by default: it tells you exactly
what's wrong and refuses to write output until you either fix the
source or opt into repairs.

## Strict by default, lenient on request

Running `icsnorm` with no flags is a validator. If the input has a
problem it can't safely paper over, it lists every problem it found and
exits non-zero without writing anything:

```
$ icsnorm broken.ics
icsnorm: line endings are not CRLF
icsnorm: missing required property PRODID
icsnorm: VEVENT #2 has no UID
icsnorm: rerun with --lenient to fix what can be fixed automatically
```

Pass `--lenient` and it fixes what it safely can (line endings, folding,
whitespace, missing `VERSION`/`PRODID`, missing `UID`) and writes the
repaired file:

```
$ icsnorm --lenient broken.ics -o fixed.ics
```

A few problems are never auto-fixed, even with `--lenient`, because
there's no safe value to invent — an event with no `DTSTART` is one of
these. That case always errors, since guessing a start time would
silently corrupt the calendar rather than clean it up.

## Usage

```
usage: icsnorm [-h] [-o OUTPUT] [--lenient] [--version] [input]

positional arguments:
  input                 path to a .ics file, or - to read from stdin (default: -)

options:
  -o, --output OUTPUT   path to write normalized output to, or - for stdout (default: -)
  --lenient             repair formatting problems instead of rejecting the file
  --version             show program's version number and exit
```

Reading from stdin and writing to stdout both work, so it composes:

```
$ curl -s https://example.com/calendar.ics | icsnorm --lenient > clean.ics
```

It's also usable as a library:

```python
from icsnorm import normalize, IcsFormatError

with open("broken.ics", encoding="utf-8") as f:
    raw = f.read()

try:
    clean = normalize(raw)
except IcsFormatError as exc:
    for issue in exc.issues:
        print(issue)
else:
    print(clean)
```

## Status

Early. The current checks cover line endings, line folding, trailing
whitespace, blank lines, the `VCALENDAR` wrapper, `VERSION`/`PRODID`,
and per-event `UID`/`DTSTART`. `icsnorm.text` handles escaping and
unescaping of TEXT property values (`SUMMARY`, `DESCRIPTION`, and
similar), but `normalize()` does not yet parse into individual
property values on its own, so that module is available as a library
function without being wired into the CLI. See the roadmap in the
project history for what's next — timezone handling in particular is
not covered yet.

## Requirements

Python 3.9+. No third-party dependencies.

## License

MIT, see [LICENSE](LICENSE).
