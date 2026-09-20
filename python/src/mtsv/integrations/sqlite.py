"""Convert between MTSV sheets and SQLite databases, SQLite.

Functions:
dump -- write MTSV sheets to a binary file as a SQLite database
load -- read MTSV sheets from a binary SQLite database file
"""

__all__ = ["dump", "load"]

import sqlite3
from typing import Any, BinaryIO

import mtsv
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

    Raise ValueError if the sheets are not MTSV, if a sheet has no
    lines, if a sheet name begins with "sqlite_", if two sheets share a
    sheet name, if a header repeats a field name, or if a name holds
    U+0000.
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

    Raise ValueError if a sheet has no lines, if a sheet name begins
    with "sqlite_", if two sheets share a sheet name, if a header
    repeats a field name, or if a name holds U+0000. CREATE TABLE, 3
    Column Definitions: a table holds "one or more column definitions";
    2 The CREATE TABLE command: a name beginning "sqlite_" is an error,
    and a name already in the database is an error. A repeated field
    name is refused as observed: SQLite reports "duplicate column
    name". A name holding U+0000 is refused as observed of Python's
    sqlite3, which reports "the query contains a null character".
    """
    names = [sheet["sheet name"] for sheet in obj]
    if len(set(names)) != len(names):
        raise ValueError(
            "each table name in a database is unique, so sheets that"
            " share a sheet name cannot be represented in SQLite"
        )
    for sheet in obj:
        if _internal(sheet["sheet name"]):
            raise ValueError(
                f"a table name beginning {_INTERNAL!r} is reserved, so"
                " such a sheet name cannot be represented in SQLite"
            )
        header = sheet["header"]
        if header is None:
            raise ValueError(
                "a table holds one or more columns, so a sheet with no"
                " lines cannot be represented in SQLite"
            )
        if len(set(header)) != len(header):
            raise ValueError(
                "each column name in a table is unique, so a header that"
                " repeats a field name cannot be represented in SQLite"
            )
        if any(_NUL in name for name in (sheet["sheet name"], *header)):
            raise ValueError(
                "a table or column name cannot hold U+0000, so such a"
                " sheet name or header field cannot be represented in"
                " SQLite"
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
    ValueError for a value that has no text form.
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
        sheet, table_left = _sheet(name, *tables[name])
        sheets.append(sheet)
        left |= table_left
    return sheets, left


def _sheet(
    name: str, header: list[str], rows: list[Any]
) -> tuple[dict[str, Any], set[str]]:
    """Turn one table into a sheet.

    name -- the table name
    header -- the column names
    rows -- the rows of the table

    Return the sheet, and what the table leaves behind. Raise
    ValueError for a value that has no text form.
    """
    left: set[str] = set()
    records = []
    for row in rows:
        fields = []
        for column, value in zip(header, row):
            text, value_left = _value(value, column)
            fields.append(text)
            left |= value_left
        records.append(fields)
    return {"sheet name": name, "header": header, "records": records}, left


def _value(value: Any, column: str) -> tuple[str, set[str]]:
    """Read one stored value as text.

    value -- the value, of any storage class
    column -- the name of its column

    Return the text, and what the value leaves behind, named by its
    storage class. Raise ValueError for a BLOB, which Datatypes In
    SQLite, 2 stores "exactly as it was input" and which has no text
    form.
    """
    if isinstance(value, str):
        return value, set()
    if value is None:
        return "", {f"missing values in column {column!r}"}
    if isinstance(value, bytes):
        raise ValueError(
            f"column {column!r} holds a BLOB, which cannot be represented in MTSV"
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
