"""Convert between MTSV sheets and IPC files, Arrow Columnar Format.

Functions:
dump -- write MTSV sheets to a binary file as an Arrow IPC file
load -- read MTSV sheets from a binary Arrow IPC file
"""

__all__ = ["dump", "load"]

from typing import Any, BinaryIO

import pyarrow as pa

import mtsv
from mtsv.integrations import _errors, arrow


def dump(obj: list[dict[str, Any]], fp: BinaryIO) -> None:
    """Write MTSV sheets to a binary file as an Arrow IPC file.

    obj -- the MTSV sheets
    fp -- a binary file object open for writing

    Raise ValueError if the sheets are not MTSV, if the file holds no
    sheet or more than one, or if its sheet name is not empty.
    """
    mtsv.dumps(obj)
    _check(obj)
    _, table = arrow.to_arrow(obj)[0]
    with pa.ipc.new_file(fp, table.schema) as writer:
        writer.write_table(table)


def load(fp: BinaryIO, /, errors: str = "strict") -> list[dict[str, Any]]:
    """Read MTSV sheets from a binary Arrow IPC file.

    fp -- a binary file object open for reading
    errors -- "strict" or "ignore"

    Return one sheet whose sheet name is empty. With errors="strict",
    raise ValueError if anything outside MTSV would be left behind;
    with errors="ignore", leave it behind. Raise ValueError for a file
    that is not an Arrow IPC file, and LookupError for another errors
    value.
    """
    _errors.lookup_error(errors)
    try:
        with pa.ipc.open_file(fp) as reader:
            table = reader.read_all()
    except (pa.ArrowInvalid, OSError) as error:
        raise ValueError("the file is not an Arrow IPC file") from error
    return arrow.from_arrow([("", table)], errors=errors)


def _check(obj: list[dict[str, Any]]) -> None:
    """Refuse sheets that an Arrow IPC file cannot hold.

    obj -- the MTSV sheets

    Raise ValueError if the file holds no sheet or more than one, or if
    its sheet name is not empty. Arrow Columnar Format, IPC Streaming
    Format: one schema serves every record batch of a file.
    """
    if len(obj) != 1:
        raise ValueError(
            "an Arrow IPC file holds one table, so a file of"
            f" {len(obj)} sheets cannot be represented in Arrow IPC"
        )
    if obj[0]["sheet name"] != "":
        raise ValueError(
            "an Arrow IPC file has nowhere to hold a sheet name, so a"
            " sheet whose sheet name is not empty cannot be represented"
            " in Arrow IPC"
        )
