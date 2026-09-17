"""Convert between MTSV sheets and CSV, RFC 4180 and RFC 7111.

Functions:
dump -- write MTSV sheets to a binary file as CSV
load -- read MTSV sheets from a binary CSV file
"""

__all__ = ["dump", "load"]

import csv
import io
from typing import Any, BinaryIO

import mtsv

# RFC 7111, Section 5.1, whose registration replaced the one in RFC
# 4180: "the charset parameter SHOULD be used, and if it is not
# present, UTF-8 SHOULD be assumed as the default". A file on disk
# carries no parameter, so UTF-8 is what it is read and written as.
_ENCODING = "utf-8"

# RFC 4180, Section 2: file = [header CRLF] record *(CRLF record)
# [CRLF]. The excel dialect separates fields with a comma, ends a line
# with CRLF, and encloses a field in quotation marks only where the
# grammar requires it, doubling a quotation mark inside a field.
_DIALECT = "excel"


def dump(obj: list[dict[str, Any]], fp: BinaryIO) -> None:
    """Write MTSV sheets to a binary file as CSV.

    Raise ValueError if the sheets are not MTSV, if the file holds
    more than one sheet, or if its sheet has a name. CSV holds one
    table and has nowhere to record which sheet it came from.
    """
    mtsv.dumps(obj)
    if len(obj) > 1:
        raise ValueError(
            "CSV holds one table, so a file of"
            f" {len(obj)} sheets cannot be represented in CSV"
        )
    if obj and obj[0]["sheet name"] is not None:
        raise ValueError(
            "CSV has nowhere to hold a sheet name, so a named sheet"
            " cannot be represented in CSV"
        )
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, dialect=_DIALECT)
    for sheet in obj:
        writer.writerow(sheet["header"])
        writer.writerows(sheet["records"])
    fp.write(buffer.getvalue().encode(_ENCODING))


def load(fp: BinaryIO, /, errors: str = "strict") -> list[dict[str, Any]]:
    """Read MTSV sheets from a binary CSV file.

    The first line is the header, because a sheet is a header and its
    records. A CSV file holds nothing that MTSV leaves behind, so the
    error handler never applies; a field holding a line break is
    refused, as it is everywhere else.
    """
    if errors not in ("strict", "ignore"):
        raise LookupError(f"unknown error handler name {errors!r}")
    try:
        text = fp.read().decode(_ENCODING)
    except UnicodeDecodeError as error:
        raise ValueError("the file is not encoded as UTF-8") from error
    source = io.StringIO(text, newline="")
    lines = list(csv.reader(source, dialect=_DIALECT))
    if not lines:
        sheets = []
    else:
        sheets = [
            {"sheet name": None, "header": lines[0], "records": lines[1:]}
        ]
    mtsv.dumps(sheets)
    return sheets
