"""Convert between MTSV sheets and Apache Arrow tables.

Functions:
to_arrow -- create (sheet name, table) pairs from MTSV sheets
from_arrow -- create MTSV sheets from (sheet name, table) pairs
"""

__all__ = ["to_arrow", "from_arrow"]

from typing import Any

import pyarrow as pa
import pyarrow.compute as pc

import mtsv

# The types whose slots hold one scalar, and so have a text form.
_SCALAR = (
    pa.types.is_null,
    pa.types.is_boolean,
    pa.types.is_integer,
    pa.types.is_floating,
    pa.types.is_decimal,
    pa.types.is_date,
    pa.types.is_time,
    pa.types.is_timestamp,
    pa.types.is_interval,
    pa.types.is_duration,
)

# The layouts that encode a value type, rather than types of their own.
_ENCODINGS = (pa.types.is_dictionary, pa.types.is_run_end_encoded)


def to_arrow(
    obj: list[dict[str, Any]], /
) -> list[tuple[str | None, pa.Table]]:
    """Create (sheet name, Arrow table) pairs from MTSV sheets."""
    mtsv.dumps(obj)
    return [(sheet["sheet name"], _table(sheet)) for sheet in obj]


def from_arrow(
    tables: list[tuple[str | None, pa.Table]],
    /,
    errors: str = "strict",
) -> list[dict[str, Any]]:
    """Create MTSV sheets from (sheet name, Arrow table) pairs.

    With errors="strict", raise ValueError if anything outside MTSV
    would be left behind. With errors="ignore", leave it behind.
    """
    if errors not in ("strict", "ignore"):
        raise LookupError(f"unknown error handler name {errors!r}")
    extras: set[str] = set()
    sheets = [_sheet(name, table, extras) for name, table in tables]
    if errors == "strict" and extras:
        raise ValueError(
            "these would be left behind: " + ", ".join(sorted(extras))
        )
    mtsv.dumps(sheets)
    return sheets


def _table(sheet: dict[str, Any]) -> pa.Table:
    """Create a table whose columns are the header fields, as strings."""
    header_fields = sheet["header"]
    if header_fields is None:
        return pa.Table.from_arrays([], names=[])
    columns = [
        pa.array([fields[index] for fields in sheet["records"]], pa.string())
        for index in range(len(header_fields))
    ]
    return pa.Table.from_arrays(columns, names=header_fields)


def _sheet(
    name: str | None, table: pa.Table, extras: set[str]
) -> dict[str, Any]:
    """Create a sheet from a table, recording anything outside MTSV."""
    if table.schema.metadata:
        extras.add("table metadata")
    if table.num_columns == 0:
        if table.num_rows:
            extras.add("rows of a table without columns")
        return {"sheet name": name, "header": None, "records": []}
    columns = [
        _values(field, column, extras)
        for field, column in zip(table.schema, table.columns)
    ]
    return {
        "sheet name": name,
        "header": table.column_names,
        "records": [list(fields) for fields in zip(*columns)],
    }


def _values(
    field: pa.Field, column: pa.ChunkedArray, extras: set[str]
) -> list[str]:
    """Read a column as text, recording anything outside MTSV."""
    if field.metadata:
        extras.add(f"metadata of column {field.name!r}")
    if pa.types.is_dictionary(field.type) and field.type.ordered:
        extras.add(f"ordering of column {field.name!r}")
    data_type = _value_type(field.type)
    if not _text_type(data_type):
        if not any(is_scalar(data_type) for is_scalar in _SCALAR):
            raise ValueError(
                f"column {field.name!r} of type {field.type}"
                " cannot be represented in MTSV"
            )
        extras.add(f"type {field.type} of column {field.name!r}")
        column = _cast(column)
    if column.null_count:
        extras.add(f"missing values in column {field.name!r}")
    return ["" if value is None else value for value in column.to_pylist()]


def _value_type(data_type: pa.DataType) -> pa.DataType:
    """Look through the dictionary and run-end encodings.

    Any array can be dictionary-encoded or run-end encoded, so an
    encoding carries the values of its value type.
    """
    while any(is_encoding(data_type) for is_encoding in _ENCODINGS):
        data_type = data_type.value_type
    return data_type


def _text_type(data_type: pa.DataType) -> bool:
    """Match the Arrow text types: Utf8, Large Utf8, Utf8 View."""
    return (
        pa.types.is_string(data_type)
        or pa.types.is_large_string(data_type)
        or pa.types.is_string_view(data_type)
    )


def _cast(column: pa.ChunkedArray) -> pa.ChunkedArray:
    """Cast a column to text, in Python where Arrow has no cast."""
    try:
        return pc.cast(column, pa.string())
    except (pa.ArrowInvalid, pa.ArrowNotImplementedError):
        values = [
            None if value is None else str(value)
            for value in column.to_pylist()
        ]
        return pa.chunked_array([pa.array(values, pa.string())])
