"""Convert between MTSV sheets and Apache Arrow tables."""

from typing import Any

import pyarrow as pa
import pyarrow.compute as pc

import mtsv

__all__ = ["from_arrow", "to_arrow"]


def from_arrow(
    tables: list[tuple[str | None, pa.Table]], errors: str = "strict"
) -> list[dict[str, Any]]:
    """Create MTSV sheets from (sheet name, Arrow table) pairs.

    With errors="strict", raise ValueError if anything outside MTSV would
    be left behind. With errors="ignore", leave it behind.
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


def to_arrow(
    obj: list[dict[str, Any]],
) -> list[tuple[str | None, pa.Table]]:
    """Create (sheet name, Arrow table) pairs from MTSV sheets."""
    mtsv.dumps(obj)
    return [(sheet["sheet name"], _table(sheet)) for sheet in obj]


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
    if not _string_type(field.type):
        extras.add(f"type {field.type} of column {field.name!r}")
        try:
            column = pc.cast(column, pa.string())
        except (pa.ArrowInvalid, pa.ArrowNotImplementedError) as error:
            raise ValueError(
                f"column {field.name!r} of type {field.type}"
                " cannot be represented in MTSV"
            ) from error
    if column.null_count:
        extras.add(f"missing values in column {field.name!r}")
    return ["" if value is None else value for value in column.to_pylist()]


def _string_type(data_type: pa.DataType) -> bool:
    """Match the Arrow string types: string, large_string, string_view."""
    return (
        pa.types.is_string(data_type)
        or pa.types.is_large_string(data_type)
        or pa.types.is_string_view(data_type)
    )


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
