"""Multi-Sheet Tab-Separated Values (MTSV), draft-demos-ra-mtsv-01."""

from typing import Any, BinaryIO

from mtsv import _generator, _parser
from mtsv._parser import MTSVDecodeError

__all__ = ["MTSVDecodeError", "dump", "dumps", "load", "loads"]


def dump(obj: list[dict[str, Any]], fp: BinaryIO) -> None:
    """Generate an MTSV file into a binary file object, encoded as UTF-8."""
    fp.write(dumps(obj).encode("utf-8"))


def dumps(obj: list[dict[str, Any]]) -> str:
    """Generate an MTSV file as a string."""
    return _generator.mtsv_file(obj)


def load(fp: BinaryIO) -> list[dict[str, Any]]:
    """Parse an MTSV file from a binary file object, decoded as UTF-8."""
    return loads(fp.read().decode("utf-8"))


def loads(s: str) -> list[dict[str, Any]]:
    """Parse an MTSV file from a string."""
    _, sheets = _parser.mtsv_file(s, 0)
    return sheets
