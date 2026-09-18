"""Conversions between MTSV and other standards.

Modules:
arrow -- convert between MTSV sheets and Apache Arrow tables
csv -- convert between MTSV sheets and CSV
json -- convert between MTSV sheets and JSON
ods -- convert between MTSV sheets and OpenDocument spreadsheets
xlsx -- convert between MTSV sheets and OOXML workbooks

Functions:
dump -- write MTSV sheets in the format a file extension names
load -- read MTSV sheets from a file in the format an extension names
report -- refuse or note what an integration would leave behind

Constants:
FORMATS -- the integration module that reads and writes each extension
MTSV -- the file extension of MTSV itself
"""

__all__ = ["FORMATS", "MTSV", "dump", "load", "report"]

import logging
from typing import Any, BinaryIO

import mtsv
from mtsv.integrations import csv, json, ods, xlsx

_logger = logging.getLogger(__name__)

# The draft, Media Type Registration: the file extension of MTSV.
MTSV = ".mtsv"

# The extension each media type registration declares: "CSV" in
# Section 5.1 of RFC 7111, ".json" in Section 11 of RFC 8259, "ods" in
# the IANA registration of the OpenDocument spreadsheet type, and
# "xlsx" in the IANA registration of the OOXML spreadsheet type.
FORMATS = {".csv": csv, ".json": json, ".ods": ods, ".xlsx": xlsx}


def load(
    suffix: str, fp: BinaryIO, /, errors: str = "strict"
) -> list[dict[str, Any]]:
    """Read MTSV sheets from a file in the format an extension names.

    Raise ValueError for an extension that names no format. The error
    handler applies only to an integration.
    """
    if suffix == MTSV:
        return mtsv.load(fp)
    if suffix not in FORMATS:
        raise ValueError(f"no format reads {suffix!r}")
    return FORMATS[suffix].load(fp, errors=errors)


def dump(suffix: str, obj: list[dict[str, Any]], fp: BinaryIO, /) -> None:
    """Write MTSV sheets in the format a file extension names.

    Raise ValueError for an extension that names no format.
    """
    if suffix == MTSV:
        mtsv.dump(obj, fp)
    elif suffix not in FORMATS:
        raise ValueError(f"no format writes {suffix!r}")
    else:
        FORMATS[suffix].dump(obj, fp)


def report(extras: set[str], errors: str) -> None:
    """Refuse or note what an integration would leave behind.

    Raise ValueError with errors="strict". Otherwise log a warning
    whose record carries the sorted names in its left_behind attribute.

    Python logging HOWTO, 100-102: a logger's warning() "if there is
    nothing the client application can do about the situation, but
    the event should still be noted". logging, 323-326: extra
    populates the LogRecord "with user-defined attributes".
    """
    if not extras:
        return
    names = sorted(extras)
    joined = ", ".join(names)
    if errors == "strict":
        raise ValueError(f"these would be left behind: {joined}")
    _logger.warning("left behind: %s", joined, extra={"left_behind": names})


def _errors(errors: str) -> None:
    """Refuse an error handler name other than strict or ignore."""
    if errors not in ("strict", "ignore"):
        raise LookupError(f"unknown error handler name {errors!r}")


def _sheet(name: str, lines: list[list[str]]) -> dict[str, Any]:
    """Return a sheet whose lines are padded to the widest line.

    The draft, Data Model: every record in a sheet has as many fields
    as the header of that sheet.
    """
    if not lines:
        return {"sheet name": name, "header": None, "records": []}
    width = max(len(values) for values in lines)
    padded = [values + [""] * (width - len(values)) for values in lines]
    return {"sheet name": name, "header": padded[0], "records": padded[1:]}
