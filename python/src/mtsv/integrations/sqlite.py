"""Convert between MTSV sheets and SQLite databases, SQLite.

Functions:
dump -- write MTSV sheets to a binary file as a SQLite database
load -- read MTSV sheets from a binary SQLite database file
"""

__all__ = ["dump", "load"]

import sqlite3
from typing import Any, BinaryIO

import mtsv
from mtsv import _data_model
from mtsv.integrations import _errors

# Database File Format, 2.6.2 Internal Schema Objects: the names of
# internal schema objects always begin with "sqlite_".
_INTERNAL = "sqlite_"

# Database File Format, 2.6: the schema table holds one row per object,
# whose type is 'table', 'index', 'view' or 'trigger'.
_SCHEMA = "SELECT type, name FROM sqlite_schema"
_TABLE = "table"

# Datatypes In SQLite, 3 Type Affinity: a column with TEXT affinity
# stores all data using storage classes NULL, TEXT or BLOB.
_COLUMN_TYPE = "TEXT"

# Datatypes In SQLite, 2 Storage Classes and Datatypes: the storage
# classes named here; the keys are what Python's sqlite3 returns for
# them.
_STORAGE_CLASSES = {int: "INTEGER", float: "REAL"}

# A name is written into the statement text, which Python's sqlite3
# refuses to build from a string holding U+0000: it reports "the query
# contains a null character".
_NUL = chr(0x00)


def dump(obj: list[dict[str, Any]], fp: BinaryIO) -> None:
    """Write MTSV sheets to a binary file as a SQLite database.

    obj -- the MTSV sheets
    fp -- a binary file object open for writing

    Raise ValueError, naming the position, if the sheets are not MTSV,
    if a sheet has no lines, if a sheet name begins with "sqlite_", if
    two sheets share a sheet name, if a header repeats a field name, or
    if a name holds U+0000.
    """
    mtsv.dumps(obj)
    _check(obj)
    connection = sqlite3.connect(":memory:")
    try:
        for create, insert, records in _statements(obj):
            connection.execute(create)
            connection.executemany(insert, records)
        connection.commit()
        fp.write(connection.serialize())
    finally:
        connection.close()


def load(fp: BinaryIO, /, errors: str = "strict") -> list[dict[str, Any]]:
    """Read MTSV sheets from a binary SQLite database file.

    fp -- a binary file object open for reading
    errors -- "strict" or "ignore"

    Return one sheet per table, in schema order. With errors="strict",
    raise ValueError if anything outside MTSV would be left behind;
    with errors="ignore", leave it behind. Raise ValueError for a file
    that is not a SQLite database, and LookupError for another errors
    value.
    """
    _errors.lookup_error(errors)
    connection = sqlite3.connect(":memory:")
    try:
        try:
            connection.deserialize(fp.read())
            objects = connection.execute(_SCHEMA).fetchall()
        except (sqlite3.DatabaseError, MemoryError) as error:
            raise ValueError("the file is not a SQLite database") from error
        tables = {}
        for kind, name in objects:
            if kind != _TABLE:
                continue
            cursor = connection.execute(f"SELECT * FROM {_quote(name)}")
            header = [column[0] for column in cursor.description]
            tables[name] = (header, cursor.fetchall())
    finally:
        connection.close()
    sheets, extras = _sheets(objects, tables)
    _errors.report(extras, errors)
    mtsv.dumps(sheets)
    return sheets


def _check(obj: list[dict[str, Any]]) -> None:
    """Refuse sheets that a SQLite database cannot hold.

    obj -- the MTSV sheets

    Raise ValueError, naming the position, if a sheet has no lines, if
    a sheet name begins with "sqlite_", if two sheets share a sheet
    name, if a header repeats a field name, or if a name holds U+0000.
    CREATE TABLE, 3 Column Definitions: a table holds "one or more
    column definitions"; 2 The CREATE TABLE command: a name beginning
    "sqlite_" is an error, and a name already in the database is an
    error. A repeated field name is refused as observed: SQLite reports
    "duplicate column name". A name holding U+0000 is refused as
    observed of Python's sqlite3, which reports "the query contains a
    null character".
    """
    names = set()
    for index, sheet in enumerate(obj):
        name = sheet["sheet name"]
        if name in names:
            raise ValueError(
                "each table name in a database is unique, so sheets that"
                " share a sheet name cannot be represented in SQLite:"
                f" {_data_model.sheet_name(index)}"
            )
        names.add(name)
        if _internal(name):
            raise ValueError(
                f"a table name beginning {_INTERNAL!r} is reserved, so"
                " such a sheet name cannot be represented in SQLite:"
                f" {_data_model.sheet_name(index)}"
            )
        if _NUL in name:
            raise ValueError(
                "a table or column name cannot hold U+0000, so such a"
                " sheet name or header field cannot be represented in"
                f" SQLite: {_data_model.sheet_name(index)}"
            )
        header = sheet["header"]
        if header is None:
            raise ValueError(
                "a table holds one or more columns, so a sheet with no"
                " lines cannot be represented in SQLite:"
                f" {_data_model.sheet(index)}"
            )
        _check_header(header, index)


def _check_header(header: list[str], index: int) -> None:
    """Refuse a header whose field names a table cannot hold.

    header -- the header fields
    index -- the index of the sheet in the file

    Raise ValueError, naming the position, if the header repeats a
    field name, or if a field name holds U+0000.
    """
    names = set()
    for field_index, name in enumerate(header):
        position = _data_model.field(_data_model.header(index), field_index)
        if name in names:
            raise ValueError(
                "each column name in a table is unique, so a header that"
                " repeats a field name cannot be represented in SQLite:"
                f" {position}"
            )
        names.add(name)
        if _NUL in name:
            raise ValueError(
                "a table or column name cannot hold U+0000, so such a"
                " sheet name or header field cannot be represented in"
                f" SQLite: {position}"
            )


def _statements(sheets: list[dict[str, Any]]) -> list[tuple[str, str, list[Any]]]:
    """Return the statements that build a table from each sheet.

    sheets -- the MTSV sheets

    Return one (create, insert, records) triple per sheet. CREATE
    TABLE, 3 Column Definitions: a column definition is a name and a
    declared type.
    """
    statements = []
    for sheet in sheets:
        name = _quote(sheet["sheet name"])
        header = sheet["header"]
        columns = ", ".join(f"{_quote(f)} {_COLUMN_TYPE}" for f in header)
        places = ", ".join("?" * len(header))
        statements.append(
            (
                f"CREATE TABLE {name} ({columns})",
                f"INSERT INTO {name} VALUES ({places})",
                sheet["records"],
            )
        )
    return statements


def _sheets(
    objects: list[tuple[str, str]], tables: dict[str, tuple[list[str], list[Any]]]
) -> tuple[list[dict[str, Any]], set[str]]:
    """Turn the objects of a schema into sheets.

    objects -- the type and name of every object in the schema
    tables -- the header and rows of every table, by name

    Return the sheets, and what the database leaves behind: every
    object that is not a table. An internal object is SQLite's own and
    is not content, so it is neither a sheet nor left behind. Raise
    ValueError, naming the position, for a value that has no text form.
    """
    left = {
        f"{kind} {name!r}"
        for kind, name in objects
        if kind != _TABLE and not _internal(name)
    }
    sheets = []
    for kind, name in objects:
        if kind != _TABLE or _internal(name):
            continue
        sheet, table_left = _sheet(name, *tables[name], len(sheets))
        sheets.append(sheet)
        left |= table_left
    return sheets, left


def _sheet(
    name: str, header: list[str], rows: list[Any], index: int
) -> tuple[dict[str, Any], set[str]]:
    """Turn one table into a sheet.

    name -- the table name
    header -- the column names
    rows -- the rows of the table
    index -- the index of the sheet in the file

    Return the sheet, and what the table leaves behind. Raise
    ValueError, naming the position, for a value that has no text form.
    """
    left: set[str] = set()
    records = []
    for record_index, row in enumerate(rows):
        line = _data_model.record(index, record_index)
        fields = []
        for field_index, (column, value) in enumerate(zip(header, row)):
            position = _data_model.field(line, field_index)
            text, value_left = _value(value, column, position)
            fields.append(text)
            left |= value_left
        records.append(fields)
    return {"sheet name": name, "header": header, "records": records}, left


def _value(value: Any, column: str, position: str) -> tuple[str, set[str]]:
    """Read one stored value as text.

    value -- the value, of any storage class
    column -- the name of its column
    position -- the position of its field, as named

    Return the text, and what the value leaves behind, named by its
    storage class. Raise ValueError, naming the position, for a BLOB,
    which Datatypes In SQLite, 2 stores "exactly as it was input" and
    which has no text form.
    """
    if isinstance(value, str):
        return value, set()
    if value is None:
        return "", {f"missing values in column {column!r}"}
    if isinstance(value, bytes):
        raise ValueError(
            f"column {column!r} holds a BLOB, which cannot be represented"
            f" in MTSV: {position}"
        )
    storage = _STORAGE_CLASSES[type(value)]
    return str(value), {f"{storage} values in column {column!r}"}


def _internal(name: str) -> bool:
    """Return whether a name is one SQLite keeps for itself.

    name -- an object name from the schema

    Database File Format, 2.6.2: "any table, index, view, or trigger
    whose name begins with "sqlite_" is an internal schema object".
    """
    return name.startswith(_INTERNAL)


def _quote(name: str) -> str:
    """Return a name as a quoted SQL identifier.

    name -- a table or column name

    A quotation mark in the name is written twice.
    """
    doubled = name.replace('"', '""')
    return f'"{doubled}"'
