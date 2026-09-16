"""Multi-Sheet Tab-Separated Values (MTSV), draft-demosra-mtsv-00.

Functions:
dump -- write MTSV sheets to a binary file, encoded as UTF-8
dumps -- return MTSV sheets as a string
load -- read MTSV sheets from a binary file, decoded as UTF-8
loads -- read MTSV sheets from a string

Exceptions:
MTSVDecodeError -- raised for text that is not an MTSV file

Subpackages:
integrations -- conversions between MTSV and other standards
"""

__all__ = ["dump", "dumps", "load", "loads", "MTSVDecodeError"]

from typing import Any, BinaryIO

from mtsv import _generator, _parser
from mtsv._parser import MTSVDecodeError


def dump(obj: list[dict[str, Any]], fp: BinaryIO) -> None:
    """Write MTSV sheets to a binary file object, encoded as UTF-8."""
    fp.write(dumps(obj).encode("utf-8"))


def dumps(obj: list[dict[str, Any]]) -> str:
    """Return MTSV sheets as an MTSV string."""
    return _generator.mtsv_file(obj)


def load(fp: BinaryIO, /) -> list[dict[str, Any]]:
    """Read MTSV sheets from a binary file object, decoded as UTF-8."""
    b = fp.read()
    try:
        s = b.decode("utf-8")
    except AttributeError:
        raise TypeError(
            "File must be opened in binary mode,"
            " e.g. use `open('foo.mtsv', 'rb')`"
        ) from None
    return loads(s)


def loads(s: str, /) -> list[dict[str, Any]]:
    """Read MTSV sheets from an MTSV string."""
    if not isinstance(s, str):
        raise TypeError(f"Expected str object, not '{type(s).__qualname__}'")
    _, sheets = _parser.mtsv_file(s, 0)
    return sheets
