"""Convert between MTSV sheets and JSON, RFC 8259.

Functions:
dump -- write MTSV sheets to a binary file as JSON
load -- read MTSV sheets from a binary JSON file
"""

__all__ = ["dump", "load"]

import json
from typing import Any, BinaryIO

import mtsv
import mtsv.integrations

# RFC 8259, Section 8.1: JSON text exchanged between systems that are
# not part of a closed ecosystem MUST be encoded using UTF-8; an
# implementation MUST NOT add a byte order mark, and a parser MAY
# ignore one.
_WRITE = "utf-8"
_READ = "utf-8-sig"

# conformance/README.md: each result is written with no white space
# except one final line feed.
_SEPARATORS = (",", ":")

# The members of a sheet, draft-demosra-mtsv-00, Section 3.
_KEYS = ("sheet name", "header", "records")


def dump(obj: list[dict[str, Any]], fp: BinaryIO) -> None:
    """Write MTSV sheets to a binary file as JSON.

    Raise ValueError if the sheets are not MTSV.
    """
    mtsv.dumps(obj)
    text = json.dumps(obj, separators=_SEPARATORS) + "\n"
    fp.write(text.encode(_WRITE))


def load(fp: BinaryIO, /, errors: str = "strict") -> list[dict[str, Any]]:
    """Read MTSV sheets from a binary JSON file.

    With errors="strict", raise ValueError if anything outside MTSV
    would be left behind. With errors="ignore", leave it behind. Raise
    ValueError for a file that is not JSON in the shape of sheets.
    """
    mtsv.integrations._errors(errors)
    extras: set[str] = set()
    try:
        value = json.loads(fp.read().decode(_READ))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("the file is not JSON") from error
    sheets = [_sheet(entry, extras) for entry in _array(value)]
    mtsv.integrations.report(extras, errors)
    mtsv.dumps(sheets)
    return sheets


def _sheet(entry: Any, extras: set[str]) -> dict[str, Any]:
    """Read one sheet, recording each member outside the data model."""
    if not isinstance(entry, dict):
        raise ValueError("each sheet is a JSON object")
    for key in entry:
        if key not in _KEYS:
            extras.add(key)
    for key in _KEYS:
        if key not in entry:
            raise ValueError(f"a sheet has no {key!r} member")
    name = entry["sheet name"]
    header = entry["header"]
    return {
        "sheet name": _text(name),
        "header": None if header is None else _fields(header),
        "records": [_fields(line) for line in _array(entry["records"])],
    }


def _array(value: Any) -> list[Any]:
    """Return a JSON array, which sheets, records and lines are."""
    if not isinstance(value, list):
        raise ValueError(f"a JSON array is expected, not {value!r}")
    return value


def _fields(value: Any) -> list[str]:
    """Return an array of strings, which a header and a record are."""
    return [_text(field) for field in _array(value)]


def _text(value: Any) -> str:
    """Return a JSON string, which a field and a sheet name are."""
    if not isinstance(value, str):
        raise ValueError(f"a JSON string is expected, not {value!r}")
    return value
