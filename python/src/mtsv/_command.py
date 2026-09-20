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
from typing import Any, NoReturn

import mtsv
import mtsv.integrations

# POSIX.1-2017 XBD 12.2, Guideline 13: the operand "-" means standard
# input, or standard output where an output file is meant.
_STDIO = Path("-")

# GNU Coding Standards 4.8.1: "The program's name should be a constant
# string".
_PROG = "mtsv"


class _Parser(argparse.ArgumentParser):
    """An argument parser whose errors read "PROGRAM: MESSAGE".

    GNU Coding Standards 4.4: error messages from noninteractive
    programs read "PROGRAM: MESSAGE" when there is no relevant source
    file.
    """

    def error(self, message: str) -> NoReturn:
        """Print the usage and "PROGRAM: MESSAGE", and exit with 2."""
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: {message}\n")


def run(argv: list[str] | None = None) -> None:
    """Convert the input file to the output file, by their extensions.

    argv -- the arguments, or None for those of the process

    Raise SystemExit with a GNU Coding Standards 4.4 message for a
    usage error, a file that cannot be read or written, or sheets that
    cannot be converted.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    output = _output(args, parser)
    source = _format(args.input)
    target = _format(output)
    _check(source, target, parser)
    # Logging HOWTO, Configuring Logging for a Library: the
    # configuration of handlers is the prerogative of the application
    # developer.
    logging.basicConfig(format=f"{_PROG}: %(message)s", force=True)
    _convert(args.input, output, source, target, args.errors)


def _build_parser() -> _Parser:
    """Return the parser of the command's arguments."""
    parser = _Parser(
        prog=_PROG,
        description="Convert a file to another format, by their file extensions.",
        epilog=_epilog(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("operand", type=Path, nargs="?", metavar="output")
    parser.add_argument("-o", "--output", type=Path)
    # Logging HOWTO, When to use logging: WARNING, "The software is
    # still working as expected."
    parser.add_argument(
        "-e", "--errors", choices=["strict", "ignore"], default="ignore"
    )
    parser.add_argument("--version", action="version", version=_notice())
    return parser


def _epilog() -> str:
    """Return the closing lines of GNU Coding Standards 4.8.2.

    The address for bug reports and the home page, from the project's
    metadata.
    """
    urls = {}
    for entry in metadata("mtsv").get_all("Project-URL", []):
        label, address = entry.split(",", 1)
        urls[label.strip()] = address.strip()
    return f"Report bugs to: <{urls['issues']}>\nmtsv home page: <{urls['source']}>"


def _notice() -> str:
    """Return the version notice of GNU Coding Standards 4.8.1.

    The first line is the canonical name of the program, a space, and
    the version; then a copyright notice, the licence, that the program
    is free software, and that there is no warranty.
    """
    package = metadata("mtsv")
    return (
        f"{_PROG} {package['Version']}\n"
        "Copyright (C) 2026 Demos Ra\n"
        f"License {package['License-Expression']}\n"
        "This is free software: you are free to change and"
        " redistribute it.\n"
        "There is NO WARRANTY, to the extent permitted by law."
    )


def _output(args: argparse.Namespace, parser: _Parser) -> Path:
    """Return the output operand, given or derived from the input.

    args -- the parsed arguments
    parser -- the parser that reports a usage error

    Exit with a usage error where the output is given twice, or where
    no name can be derived.
    """
    if args.output is not None and args.operand is not None:
        parser.error("give the output file once, as an operand or with -o")
    output = args.operand if args.output is None else args.output
    if output is None:
        output = _derive(args.input, parser)
    return output


def _derive(path: Path, parser: _Parser) -> Path:
    """Return the MTSV file a lone input operand converts to.

    path -- the input operand
    parser -- the parser that reports a usage error

    Exit with a usage error where no name can be formed: a stream, or
    an input that is MTSV already.
    """
    if path == _STDIO:
        parser.error("an output file is required to read standard input")
    if path.suffix == mtsv.integrations.MTSV:
        parser.error("an output file is required to convert from MTSV")
    return path.with_suffix(mtsv.integrations.MTSV)


def _format(path: Path) -> str:
    """Return the file extension that names a path's format.

    path -- an operand

    A stream has the MTSV format. Pandoc User's Guide, Specifying
    formats: "If no input file is specified (so that input comes from
    stdin) ... the input format will be assumed to be Markdown."
    """
    if path == _STDIO:
        return mtsv.integrations.MTSV
    return path.suffix


def _check(source: str, target: str, parser: _Parser) -> None:
    """Refuse a file extension that names no format.

    source -- the input's file extension
    target -- the output's file extension
    parser -- the parser that reports a usage error

    Exit with a usage error for an extension with no format, or for one
    whose format needs a package that is not installed.
    """
    for suffix in (source, target):
        if suffix != mtsv.integrations.MTSV:
            try:
                mtsv.integrations.lookup(suffix)
            except LookupError as error:
                parser.error(str(error))
            except ModuleNotFoundError as error:
                parser.error(f"the {suffix} format needs the {error.name} package")


def _convert(path: Path, output: Path, source: str, target: str, errors: str) -> None:
    """Convert the input file to the output file.

    path -- the input operand
    output -- the output operand
    source -- the input's file extension
    target -- the output's file extension
    errors -- "strict" or "ignore"

    Raise SystemExit with a GNU Coding Standards 4.4 message for a file
    that cannot be read or written, or sheets that cannot be converted.
    """
    try:
        sheets = _read(source, path, errors)
        data = _write(target, sheets)
        _put(output, data)
    except mtsv.MTSVDecodeError as error:
        # GNU Coding Standards 4.4: "PROGRAM:SOURCEFILE:LINENO:COLUMN:
        # MESSAGE".
        if path == _STDIO:
            raise SystemExit(f"{_PROG}: {error}")
        raise SystemExit(f"{_PROG}:{path}:{error.lineno}:{error.colno}: {error.msg}")
    except ValueError as error:
        # GNU Coding Standards 4.4: "PROGRAM: MESSAGE" when there is no
        # relevant source file, not beginning with a capital letter.
        raise SystemExit(f"{_PROG}: {error}")
    except OSError as error:
        reason = error.strerror[:1].lower() + error.strerror[1:]
        raise SystemExit(f"{_PROG}: {error.filename}: {reason}")


def _read(source: str, path: Path, errors: str) -> list[dict[str, Any]]:
    """Read sheets from a file, or from standard input, read whole.

    source -- the file extension that names the format
    path -- the input operand
    errors -- "strict" or "ignore"

    Return the sheets. Raise OSError for a file that cannot be read,
    and ValueError for one that cannot be converted.
    """
    if path == _STDIO:
        data = sys.stdin.buffer.read()
    else:
        data = path.read_bytes()
    with io.BytesIO(data) as fp:
        return mtsv.integrations.load(source, fp, errors=errors)


def _write(target: str, sheets: list[dict[str, Any]]) -> bytes:
    """Return the sheets written in the format of a file extension.

    target -- the file extension that names the format
    sheets -- the MTSV sheets

    Raise ValueError for sheets the format cannot hold.
    """
    with io.BytesIO() as fp:
        mtsv.integrations.dump(target, sheets, fp)
        return fp.getvalue()


def _put(path: Path, data: bytes) -> None:
    """Write bytes to a file, or to standard output, in one call.

    path -- the output operand
    data -- the bytes

    Raise OSError for a file that cannot be written.
    """
    if path == _STDIO:
        sys.stdout.buffer.write(data)
    else:
        path.write_bytes(data)
