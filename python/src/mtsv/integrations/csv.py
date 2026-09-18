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
import mtsv.integrations

# RFC 7111, Section 5.1, which updates RFC 4180: "the charset
# parameter SHOULD be used, and if it is not present, UTF-8 SHOULD be
# assumed as the default".
_ENCODING = "utf-8"

# RFC 4180, Section 2: file = [header CRLF] record *(CRLF record)
# [CRLF].
_DIALECT = "excel"


def dump(obj: list[dict[str, Any]], fp: BinaryIO) -> None:
    """Write MTSV sheets to a binary file as CSV.

    Raise ValueError if the sheets are not MTSV, if the file holds no
    sheet or more than one, if its sheet name is not empty, or if its
    sheet has no lines.
    """
    mtsv.dumps(obj)
    if not obj:
        raise ValueError(
            "a CSV file holds at least one record, so a file of no sheets"
            " cannot be represented in CSV"
        )
    if len(obj) > 1:
        raise ValueError(
            "CSV holds one table, so a file of"
            f" {len(obj)} sheets cannot be represented in CSV"
        )
    if obj[0]["sheet name"] != "":
        raise ValueError(
            "CSV has nowhere to hold a sheet name, so a sheet whose sheet"
            " name is not empty cannot be represented in CSV"
        )
    if obj[0]["header"] is None:
        raise ValueError(
            "a CSV file holds at least one record, so a sheet with no"
            " lines cannot be represented in CSV"
        )
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, dialect=_DIALECT)
    for sheet in obj:
        writer.writerow(sheet["header"])
        writer.writerows(sheet["records"])
    fp.write(buffer.getvalue().encode(_ENCODING))


def load(fp: BinaryIO, /, errors: str = "strict") -> list[dict[str, Any]]:
    """Read MTSV sheets from a binary CSV file.

    The first line is the header. The error handler never applies. A
    field holding a line break is refused.
    """
    mtsv.integrations._errors(errors)
    try:
        text = fp.read().decode(_ENCODING)
    except UnicodeDecodeError as error:
        raise ValueError("the file is not encoded as UTF-8") from error
    source = io.StringIO(text, newline="")
    # RFC 4180, Section 2: a file holds at least one record, and a
    # record at least one field, which may be empty.
    lines = list(csv.reader(source, dialect=_DIALECT)) or [[]]
    lines = [line or [""] for line in lines]
    sheets = [{"sheet name": "", "header": lines[0], "records": lines[1:]}]
    mtsv.dumps(sheets)
    return sheets
