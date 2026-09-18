"""Convert a file from one format to another, through MTSV sheets.

Functions:
run -- convert an input file to an output file, by their extensions
"""

__all__ = ["run"]

import argparse
import io
import logging
import sys
from importlib.metadata import metadata
from pathlib import Path
from typing import Any

import mtsv.integrations

# Guideline 13 of POSIX.1-2017 XBD 12.2: the operand "-" means
# standard input, or standard output where an output file is meant.
_STDIO = Path("-")


def run(
    prog: str,
    description: str,
    suffixes: tuple[str, ...],
    argv: list[str] | None = None,
) -> None:
    """Convert the input file to the output file, by their extensions.

    The suffixes are the file extensions this invocation converts,
    besides MTSV itself.
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
    # Python logging HOWTO, 120-121: WARNING, "The software is still
    # working as expected."
    parser.add_argument(
        "-e", "--errors", choices=["strict", "ignore"], default="ignore"
    )
    parser.add_argument("--version", action="version", version=_notice())
    args = parser.parse_args(argv)
    if args.output is not None and args.operand is not None:
        parser.error("give the output file once, as an operand or with -o")
    output = args.operand if args.output is None else args.output
    if output is None:
        output = _derive(args.input, parser)
    formats = (mtsv.integrations.MTSV, *sorted(suffixes))
    source = _format(args.input)
    target = _format(output)
    if source not in formats or target not in formats:
        names = ", ".join(formats)
        parser.error(f"the file extensions must be two of {names}")
    # Python logging HOWTO, 717-722: the configuration of handlers is
    # the prerogative of the application developer. GNU Coding
    # Standards 4.4 gives the format.
    logging.basicConfig(format=f"{prog}: %(message)s", force=True)
    try:
        sheets = _read(source, args.input, args.errors)
        data = _write(target, sheets)
        _put(output, data)
    except ValueError as error:
        # GNU Coding Standards 4.4: a message from a noninteractive
        # program reads "PROGRAM: MESSAGE" where no source file is
        # relevant, and does not begin with a capital or end with a
        # full stop.
        raise SystemExit(f"{prog}: {error}")
    except OSError as error:
        reason = error.strerror[:1].lower() + error.strerror[1:]
        raise SystemExit(f"{prog}: {error.filename}: {reason}")


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

    Lines 1012-1018: the address for bug reports and the home page.
    Line 1021: other web pages are ok.
    """
    urls = {}
    for entry in metadata("mtsv").get_all("Project-URL", []):
        label, address = entry.split(",", 1)
        urls[label.strip()] = address.strip()
    return (
        f"Report bugs to: <{urls['issues']}>\n"
        f"mtsv home page: <{urls['source']}>"
    )


def _derive(path: Path, parser: argparse.ArgumentParser) -> Path:
    """Return the MTSV file a lone input operand converts to.

    The operand stays required wherever that name cannot be formed.
    """
    if path == _STDIO:
        parser.error("an output file is required to read standard input")
    if path.suffix == mtsv.integrations.MTSV:
        parser.error("an output file is required to convert from MTSV")
    return path.with_suffix(mtsv.integrations.MTSV)


def _format(path: Path) -> str:
    """Return the file extension that names a path's format.

    A stream has the MTSV format. Pandoc manual, 92-94: input from
    stdin is assumed to be Markdown.
    """
    if path == _STDIO:
        return mtsv.integrations.MTSV
    return path.suffix


def _read(source: str, path: Path, errors: str) -> list[dict[str, Any]]:
    """Read sheets from a file, or from standard input.

    The bytes are read whole.
    """
    if path == _STDIO:
        data = sys.stdin.buffer.read()
    else:
        data = path.read_bytes()
    with io.BytesIO(data) as fp:
        return mtsv.integrations.load(source, fp, errors=errors)


def _write(target: str, sheets: list[dict[str, Any]]) -> bytes:
    """Return the sheets written in the format of a file extension."""
    with io.BytesIO() as fp:
        mtsv.integrations.dump(target, sheets, fp)
        return fp.getvalue()


def _put(path: Path, data: bytes) -> None:
    """Write bytes to a file, or to standard output.

    The bytes are written in one call.
    """
    if path == _STDIO:
        sys.stdout.buffer.write(data)
    else:
        path.write_bytes(data)
