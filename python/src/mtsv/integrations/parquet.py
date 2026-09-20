"""Convert between MTSV sheets and Parquet files, Apache Parquet.

Functions:
dump -- write MTSV sheets to a binary file as a Parquet file
load -- read MTSV sheets from a binary Parquet file
"""

__all__ = ["dump", "load"]

from typing import Any, BinaryIO

import pyarrow as pa
import pyarrow.parquet as pq

import mtsv
from mtsv.integrations import _errors, arrow


def dump(obj: list[dict[str, Any]], fp: BinaryIO) -> None:
    """Write MTSV sheets to a binary file as a Parquet file.

    obj -- the MTSV sheets
    fp -- a binary file object open for writing

    Raise ValueError if the sheets are not MTSV, if the file holds no
    sheet or more than one, or if its sheet name is not empty.
    """
    mtsv.dumps(obj)
    _check(obj)
    _, table = arrow.to_arrow(obj)[0]
    pq.write_table(table, fp)


def load(fp: BinaryIO, /, errors: str = "strict") -> list[dict[str, Any]]:
    """Read MTSV sheets from a binary Parquet file.

    fp -- a binary file object open for reading
    errors -- "strict" or "ignore"

    Return one sheet whose sheet name is empty. With errors="strict",
    raise ValueError if anything outside MTSV would be left behind;
    with errors="ignore", leave it behind. Raise ValueError for a file
    that is not a Parquet file, and LookupError for another errors
    value. pyarrow, Parquet Files: ParquetFile is the "Reader interface
    for a single Parquet file".
    """
    _errors.lookup_error(errors)
    try:
        table = pq.ParquetFile(fp).read()
    except (pa.ArrowInvalid, OSError) as error:
        raise ValueError("the file is not a Parquet file") from error
    return arrow.from_arrow([("", table)], errors=errors)


def _check(obj: list[dict[str, Any]]) -> None:
    """Refuse sheets that a Parquet file cannot hold.

    obj -- the MTSV sheets

    Raise ValueError if the file holds no sheet or more than one, or if
    its sheet name is not empty. Apache Parquet, FileMetaData: a file
    holds one schema, "a tree with a single root".
    """
    if len(obj) != 1:
        raise ValueError(
            "a Parquet file holds one table, so a file of"
            f" {len(obj)} sheets cannot be represented in Parquet"
        )
    if obj[0]["sheet name"] != "":
        raise ValueError(
            "a Parquet file has nowhere to hold a sheet name, so a sheet"
            " whose sheet name is not empty cannot be represented in"
            " Parquet"
        )
