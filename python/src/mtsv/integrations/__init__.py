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
lookup -- return the integration module of a file extension
report -- refuse or note what an integration would leave behind

Constants:
FORMATS -- deprecated, to be removed in 0.6.0: use lookup
MTSV -- the file extension of MTSV itself
"""

__all__ = ["FORMATS", "MTSV", "dump", "load", "lookup", "report"]

from types import ModuleType
from typing import Any, BinaryIO

import mtsv
from mtsv.integrations import csv, json, ods, xlsx
from mtsv.integrations._errors import report

# The draft, Media Type Registration: the file extension of MTSV.
MTSV = ".mtsv"

# The extension each media type registration declares: "CSV" in RFC
# 7111, Section 5.1, ".json" in RFC 8259, Section 11, "ods" in the IANA
# registration of the OpenDocument spreadsheet type, and "xlsx" in the
# IANA registration of the OOXML spreadsheet type.
FORMATS = {".csv": csv, ".json": json, ".ods": ods, ".xlsx": xlsx}


def load(suffix: str, fp: BinaryIO, /, errors: str = "strict") -> list[dict[str, Any]]:
    """Read MTSV sheets from a file in the format an extension names.

    suffix -- the file extension, such as ".csv"
    fp -- a binary file object
    errors -- "strict" or "ignore", for an integration only

    Raise LookupError for an extension that names no format.
    """
    if suffix == MTSV:
        return mtsv.load(fp)
    return lookup(suffix).load(fp, errors=errors)


def dump(suffix: str, obj: list[dict[str, Any]], fp: BinaryIO, /) -> None:
    """Write MTSV sheets in the format a file extension names.

    suffix -- the file extension, such as ".csv"
    obj -- the MTSV sheets
    fp -- a binary file object

    Raise LookupError for an extension that names no format.
    """
    if suffix == MTSV:
        mtsv.dump(obj, fp)
    else:
        lookup(suffix).dump(obj, fp)


def lookup(suffix: str) -> ModuleType:
    """Return the integration module that reads and writes an extension.

    suffix -- the file extension, such as ".csv"

    Raise LookupError for an extension that names no format. Python
    codecs, codecs.lookup: "If no CodecInfo object is found, a
    LookupError is raised."
    """
    if suffix not in FORMATS:
        raise LookupError(f"no format for {suffix!r}")
    return FORMATS[suffix]
