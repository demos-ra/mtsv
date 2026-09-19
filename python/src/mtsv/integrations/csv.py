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
from mtsv.integrations import _errors

# RFC 7111, Section 5.1, which updates RFC 4180: "the charset
# parameter SHOULD be used, and if it is not present, UTF-8 SHOULD be
# assumed as the default".
_ENCODING = "utf-8"

# RFC 4180, Section 2: file = [header CRLF] record *(CRLF record)
# [CRLF].
_DIALECT = "excel"


def dump(obj: list[dict[str, Any]], fp: BinaryIO) -> None:
    """Write MTSV sheets to a binary file as CSV.

    obj -- the MTSV sheets
    fp -- a binary file object open for writing

    Raise ValueError if the sheets are not MTSV, if the file holds no
    sheet or more than one, if its sheet name is not empty, or if its
    sheet has no lines.
    """
    mtsv.dumps(obj)
    _check(obj)
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, dialect=_DIALECT)
    writer.writerow(obj[0]["header"])
    writer.writerows(obj[0]["records"])
    fp.write(buffer.getvalue().encode(_ENCODING))


def load(fp: BinaryIO, /, errors: str = "strict") -> list[dict[str, Any]]:
    """Read MTSV sheets from a binary CSV file.

    fp -- a binary file object open for reading
    errors -- "strict" or "ignore"; CSV leaves nothing behind

    Return one sheet whose sheet name is empty, the first line its
    header. Raise ValueError for a file that is not UTF-8, or whose
    lines MTSV cannot hold, and LookupError for another errors value.
    """
    _errors.lookup_error(errors)
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


def _check(obj: list[dict[str, Any]]) -> None:
    """Refuse sheets that CSV cannot hold.

    obj -- the MTSV sheets

    Raise ValueError if the file holds no sheet or more than one, if
    its sheet name is not empty, or if its sheet has no lines. RFC
    4180, Section 2: a file holds at least one record; the draft,
    Relationship to TSV: a TSV file is one sheet whose sheet name is
    empty.
    """
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
