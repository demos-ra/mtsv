"""Convert a file from one format to another, through MTSV sheets.

Functions:
run -- convert an input file to an output file, by their extensions
"""

__all__ = ["run"]

import argparse
import io
import sys
from collections.abc import Callable
from importlib.metadata import metadata
from pathlib import Path
from typing import Any

import mtsv

# Every conversion passes through MTSV. Its media type registration
# declares the extension .mtsv, in draft-demosra-mtsv-00, Section 9.1.
_MTSV = ".mtsv"

# Guideline 13 of POSIX.1-2017 XBD 12.2: the operand "-" means
# standard input, or standard output where an output file is meant.
_STDIO = Path("-")


def run(
    prog: str,
    description: str,
    integrations: dict[str, tuple[Callable, Callable]],
    argv: list[str] | None = None,
) -> None:
    """Convert the input file to the output file, by their extensions.

    Each integration is named by the file extension of its format and
    holds that format's load and dump functions. MTSV is a format of
    every conversion, so it is never named in integrations.
    """
    parser = argparse.ArgumentParser(
        prog=prog,
        description=description,
        epilog=_epilog(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("operand", type=Path, nargs="?", metavar="output")
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument(
        "-e", "--errors", choices=["strict", "ignore"], default="strict"
    )
    parser.add_argument("--version", action="version", version=_notice())
    args = parser.parse_args(argv)
    if args.output is not None and args.operand is not None:
        parser.error("give the output file once, as an operand or with -o")
    output = args.operand if args.output is None else args.output
    if output is None:
        parser.error("an output file is required")
    formats = (_MTSV, *sorted(integrations))
    source = _format(args.input)
    target = _format(output)
    if source not in formats or target not in formats:
        names = ", ".join(formats)
        parser.error(f"the file extensions must be two of {names}")
    try:
        sheets = _read(source, args.input, integrations, args.errors)
        data = _write(target, sheets, integrations)
    except ValueError as error:
        raise SystemExit(error)
    _put(output, data)


def _notice() -> str:
    """Return the version notice of GNU Coding Standards 4.8.1.

    The first line is the canonical name of the program, a space, and
    the version; the name is a constant, never taken from argv[0].
    Then a copyright notice, the licence, that the program is free
    software, and that there is no warranty.
    """
    package = metadata("mtsv")
    return (
        f"mtsv {package['Version']}\n"
        "Copyright (c) 2026 Demos Ra\n"
        f"License {package['License-Expression']}\n"
        "This is free software: you are free to change and"
        " redistribute it.\n"
        "There is NO WARRANTY, to the extent permitted by law."
    )


def _epilog() -> str:
    """Return the closing lines of GNU Coding Standards 4.8.2.

    That section asks for the address for bug reports and the home
    page of the package. Line 1021 permits other web pages, which is
    how a tracker stands in for a mailing address.
    """
    urls = {}
    for entry in metadata("mtsv").get_all("Project-URL", []):
        label, address = entry.split(",", 1)
        urls[label.strip()] = address.strip()
    return (
        f"Report bugs at: <{urls['issues']}>\n"
        f"mtsv home page: <{urls['source']}>"
    )


def _format(path: Path) -> str:
    """Return the file extension that names a path's format.

    A stream carries no extension, so it carries the format that
    every conversion passes through. Pandoc reads a stream as its own
    central format for the same reason, in lines 89 to 94 of its
    manual.
    """
    if path == _STDIO:
        return _MTSV
    return path.suffix


def _read(
    source: str,
    path: Path,
    integrations: dict[str, tuple[Callable, Callable]],
    errors: str,
) -> list[dict[str, Any]]:
    """Read sheets from a file, or from standard input.

    The bytes are read whole because a spreadsheet package is a zip
    file, which seeks, and standard input cannot seek.
    """
    if path == _STDIO:
        data = sys.stdin.buffer.read()
    else:
        data = path.read_bytes()
    with io.BytesIO(data) as fp:
        if source == _MTSV:
            return mtsv.load(fp)
        load, _ = integrations[source]
        return load(fp, errors=errors)


def _write(
    target: str,
    sheets: list[dict[str, Any]],
    integrations: dict[str, tuple[Callable, Callable]],
) -> bytes:
    """Return the sheets written in the format of a file extension."""
    with io.BytesIO() as fp:
        if target == _MTSV:
            mtsv.dump(sheets, fp)
        else:
            _, dump = integrations[target]
            dump(sheets, fp)
        return fp.getvalue()


def _put(path: Path, data: bytes) -> None:
    """Write bytes to a file, or to standard output.

    The bytes are written in one call, so that a conversion which
    stops partway leaves no output behind.
    """
    if path == _STDIO:
        sys.stdout.buffer.write(data)
    else:
        path.write_bytes(data)
