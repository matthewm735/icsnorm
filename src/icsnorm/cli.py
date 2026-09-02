from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .normalize import IcsFormatError, normalize


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="icsnorm",
        description="Normalize a messy .ics file into strict, well-formed iCalendar.",
    )
    parser.add_argument(
        "input",
        nargs="?",
        default="-",
        help="path to a .ics file, or - to read from stdin (default: -)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="-",
        help="path to write normalized output to, or - for stdout (default: -)",
    )
    parser.add_argument(
        "--lenient",
        action="store_true",
        help="repair formatting problems instead of rejecting the file",
    )
    parser.add_argument("--version", action="version", version=f"icsnorm {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.input == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(args.input).read_text(encoding="utf-8")

    try:
        result = normalize(raw, lenient=args.lenient)
    except IcsFormatError as exc:
        for issue in exc.issues:
            print(f"icsnorm: {issue}", file=sys.stderr)
        if not args.lenient:
            print("icsnorm: rerun with --lenient to fix what can be fixed automatically", file=sys.stderr)
        return 1

    if args.output == "-":
        sys.stdout.write(result)
    else:
        Path(args.output).write_text(result, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
