"""Convert between MTSV sheets and Arrow tables, Arrow Columnar Format.

Functions:
to_arrow -- create (sheet name, table) pairs from MTSV sheets
from_arrow -- create MTSV sheets from (sheet name, table) pairs
"""

__all__ = ["to_arrow", "from_arrow"]

from typing import Any

import pyarrow as pa
import pyarrow.compute as pc

import mtsv
from mtsv.integrations import _errors

# Arrow Columnar Format 1.5, Data Types: Null to Duration, whose
# layout is Null or Fixed-size Primitive.
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

# Arrow Columnar Format 1.5, Dictionary-encoded Layout and Run-End
# Encoded Layout: any array can be dictionary-encoded or run-end
# encoded.
_ENCODINGS = (pa.types.is_dictionary, pa.types.is_run_end_encoded)


def to_arrow(obj: list[dict[str, Any]], /) -> list[tuple[str, pa.Table]]:
    """Create (sheet name, Arrow table) pairs from MTSV sheets.

    obj -- the MTSV sheets, by position only

    Return one pair per sheet, in order. Raise ValueError if the
    sheets are not MTSV.
    """
    mtsv.dumps(obj)
    return [(sheet["sheet name"], _table(sheet)) for sheet in obj]


def from_arrow(
    tables: list[tuple[str, pa.Table]],
    /,
    errors: str = "strict",
) -> list[dict[str, Any]]:
    """Create MTSV sheets from (sheet name, Arrow table) pairs.

    tables -- the pairs, by position only
    errors -- "strict" or "ignore"

    Return the sheets. With errors="strict", raise ValueError if
    anything outside MTSV would be left behind; with errors="ignore",
    leave it behind. Raise ValueError for a column with no text form,
    and LookupError for another errors value.
    """
    _errors.lookup_error(errors)
    sheets = []
    extras: set[str] = set()
    for name, table in tables:
        sheet, left = _sheet(name, table)
        sheets.append(sheet)
        extras |= left
    _errors.report(extras, errors)
    mtsv.dumps(sheets)
    return sheets


def _table(sheet: dict[str, Any]) -> pa.Table:
    """Create a table of string columns named by the header fields.

    sheet -- one MTSV sheet

    Return the table; an empty sheet gives a table without columns.
    """
    header_fields = sheet["header"]
    if header_fields is None:
        return pa.Table.from_arrays([], names=[])
    columns = [
        pa.array([fields[index] for fields in sheet["records"]], pa.string())
        for index in range(len(header_fields))
    ]
    return pa.Table.from_arrays(columns, names=header_fields)


def _sheet(name: str, table: pa.Table) -> tuple[dict[str, Any], set[str]]:
    """Create a sheet from a table.

    name -- the sheet name
    table -- the Arrow table

    Return the sheet, and what it leaves behind. Raise ValueError for
    a column with no text form.
    """
    left = {"table metadata"} if table.schema.metadata else set()
    if table.num_columns == 0:
        if table.num_rows:
            left.add("rows of a table without columns")
        return {"sheet name": name, "header": None, "records": []}, left
    columns = []
    for field, column in zip(table.schema, table.columns):
        values, column_left = _values(field, column)
        columns.append(values)
        left |= column_left
    sheet = {
        "sheet name": name,
        "header": table.column_names,
        "records": [list(fields) for fields in zip(*columns)],
    }
    return sheet, left


def _values(field: pa.Field, column: pa.ChunkedArray) -> tuple[list[str], set[str]]:
    """Read a column as text.

    field -- the column's field
    column -- the column

    Return its values as text, and what it leaves behind. Raise
    ValueError for a column with no text form.
    """
    left = set()
    if field.metadata:
        left.add(f"metadata of column {field.name!r}")
    if pa.types.is_dictionary(field.type) and field.type.ordered:
        left.add(f"ordering of column {field.name!r}")
    data_type = _value_type(field.type)
    if not _text_type(data_type):
        if not any(is_scalar(data_type) for is_scalar in _SCALAR):
            raise ValueError(
                f"column {field.name!r} of type {field.type}"
                " cannot be represented in MTSV"
            )
        left.add(f"type {field.type} of column {field.name!r}")
        column = _cast(column)
    if column.null_count:
        left.add(f"missing values in column {field.name!r}")
    values = ["" if value is None else value for value in column.to_pylist()]
    return values, left


def _value_type(data_type: pa.DataType) -> pa.DataType:
    """Look through the dictionary and run-end encodings.

    data_type -- an Arrow data type

    Return the type of the values.
    """
    while any(is_encoding(data_type) for is_encoding in _ENCODINGS):
        data_type = data_type.value_type
    return data_type


def _text_type(data_type: pa.DataType) -> bool:
    """Return whether a type is Utf8, Large Utf8 or Utf8 View.

    data_type -- an Arrow data type
    """
    return (
        pa.types.is_string(data_type)
        or pa.types.is_large_string(data_type)
        or pa.types.is_string_view(data_type)
    )


def _cast(column: pa.ChunkedArray) -> pa.ChunkedArray:
    """Cast a column to text, in Python where Arrow has no cast.

    column -- the column

    Return the column as Utf8. pyarrow, compute.cast: "Cast array
    values to another data type."
    """
    try:
        return pc.cast(column, pa.string())
    except (pa.ArrowInvalid, pa.ArrowNotImplementedError):
        values = [None if value is None else str(value) for value in column.to_pylist()]
        return pa.chunked_array([pa.array(values, pa.string())])
