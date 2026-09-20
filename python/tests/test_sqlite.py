"""Test mtsv.integrations.sqlite against SQLite."""

import io
import sqlite3
import unittest

from mtsv.integrations import sqlite

from support import load_json, paths

SHEET = [{"sheet name": "T", "header": ["a", "b"], "records": [["1", "2"]]}]
NUL = chr(0x00)


def refused(sheets):
    """Return whether a database cannot hold these sheets."""
    names = [sheet["sheet name"] for sheet in sheets]
    headers = [sheet["header"] for sheet in sheets]
    return (
        len(set(names)) != len(names)
        or any(name.startswith("sqlite_") for name in names)
        or any(header is None for header in headers)
        or any(len(set(header)) != len(header) for header in headers if header)
        or any(NUL in name for name in names)
        or any(NUL in field for header in headers if header for field in header)
    )


def database(*statements):
    """Return the bytes of a database built by SQL statements."""
    connection = sqlite3.connect(":memory:")
    for statement in statements:
        connection.execute(statement)
    connection.commit()
    data = connection.serialize()
    connection.close()
    return data


class TestDump(unittest.TestCase):
    """Writing a SQLite database."""

    def test_magic_number(self):
        """The IANA registration: the magic is "SQLite format 3\\0"."""
        buffer = io.BytesIO()
        sqlite.dump(SHEET, buffer)
        self.assertTrue(buffer.getvalue().startswith(b"SQLite format 3\x00"))

    def test_empty_sheet_name(self):
        """A sheet name that is empty is a table named "", as observed."""
        sheets = [{"sheet name": "", "header": ["a"], "records": [["x"]]}]
        buffer = io.BytesIO()
        sqlite.dump(sheets, buffer)
        buffer.seek(0)
        self.assertEqual(sqlite.load(buffer), sheets)

    def test_sheet_with_no_lines(self):
        """CREATE TABLE, 3: a table holds one or more columns."""
        sheets = [{"sheet name": "T", "header": None, "records": []}]
        with self.assertRaises(ValueError):
            sqlite.dump(sheets, io.BytesIO())

    def test_reserved_sheet_name(self):
        """CREATE TABLE, 2: a name beginning "sqlite_" is an error."""
        sheets = [{"sheet name": "sqlite_x", "header": ["a"], "records": []}]
        with self.assertRaises(ValueError):
            sqlite.dump(sheets, io.BytesIO())

    def test_duplicate_sheet_names(self):
        """CREATE TABLE, 2: a name already in the database is an error."""
        sheets = [
            {"sheet name": "T", "header": ["a"], "records": []},
            {"sheet name": "T", "header": ["a"], "records": []},
        ]
        with self.assertRaises(ValueError):
            sqlite.dump(sheets, io.BytesIO())

    def test_duplicate_column_names(self):
        """A header that repeats a field name is refused, as observed."""
        sheets = [{"sheet name": "T", "header": ["a", "a"], "records": []}]
        with self.assertRaises(ValueError):
            sqlite.dump(sheets, io.BytesIO())

    def test_null_character_in_a_name(self):
        """A name holding U+0000 is refused, as observed."""
        for sheets in (
            [{"sheet name": NUL, "header": ["a"], "records": []}],
            [{"sheet name": "T", "header": [NUL], "records": []}],
        ):
            with self.subTest(sheets):
                with self.assertRaises(ValueError):
                    sqlite.dump(sheets, io.BytesIO())

    def test_null_character_in_a_value(self):
        """A record value holding U+0000 is carried, as observed."""
        sheets = [{"sheet name": "T", "header": ["a"], "records": [[NUL]]}]
        buffer = io.BytesIO()
        sqlite.dump(sheets, buffer)
        buffer.seek(0)
        self.assertEqual(sqlite.load(buffer), sheets)

    def test_quotation_mark_in_a_name(self):
        """A quotation mark in a name is written twice."""
        sheets = [{"sheet name": 'a"b', "header": ['c"d'], "records": []}]
        buffer = io.BytesIO()
        sqlite.dump(sheets, buffer)
        buffer.seek(0)
        self.assertEqual(sqlite.load(buffer), sheets)

    def test_no_sheets(self):
        """A file of no sheets is a database of no tables."""
        buffer = io.BytesIO()
        sqlite.dump([], buffer)
        buffer.seek(0)
        self.assertEqual(sqlite.load(buffer), [])

    def test_cannot_be_represented(self):
        """Each file that MTSV cannot hold is refused by dump."""
        for path in paths("cannot-be-represented", ".json"):
            with self.subTest(path.name):
                with self.assertRaises(ValueError):
                    sqlite.dump(load_json(path), io.BytesIO())


class TestLoad(unittest.TestCase):
    """Reading a SQLite database."""

    def test_round_trip(self):
        """What dump writes, load reads back unchanged."""
        buffer = io.BytesIO()
        sqlite.dump(SHEET, buffer)
        buffer.seek(0)
        self.assertEqual(sqlite.load(buffer), SHEET)

    def test_conforming_round_trip(self):
        """Each conforming result a database holds comes back."""
        for path in paths("conforming", ".json"):
            with self.subTest(path.name):
                value = load_json(path)
                if refused(value):
                    self.skipTest("a database cannot hold these sheets")
                buffer = io.BytesIO()
                sqlite.dump(value, buffer)
                buffer.seek(0)
                self.assertEqual(sqlite.load(buffer), value)

    def test_not_a_database(self):
        """A file that is not a SQLite database raises ValueError."""
        with self.assertRaises(ValueError):
            sqlite.load(io.BytesIO(b"not a database"))

    def test_empty_file(self):
        """An empty file raises ValueError."""
        with self.assertRaises(ValueError):
            sqlite.load(io.BytesIO(b""))

    def test_integer_left_behind(self):
        """A value that is not text is left behind, so strict refuses."""
        data = database("CREATE TABLE t(a)", "INSERT INTO t VALUES (1)")
        with self.assertRaises(ValueError):
            sqlite.load(io.BytesIO(data))

    def test_integer_ignored(self):
        """With errors="ignore" a value that is not text comes as text."""
        data = database("CREATE TABLE t(a)", "INSERT INTO t VALUES (1)")
        sheets = sqlite.load(io.BytesIO(data), errors="ignore")
        self.assertEqual(sheets[0]["records"], [["1"]])

    def test_null_left_behind(self):
        """Datatypes In SQLite, 2: a NULL is a storage class of its own."""
        data = database("CREATE TABLE t(a)", "INSERT INTO t VALUES (NULL)")
        sheets = sqlite.load(io.BytesIO(data), errors="ignore")
        self.assertEqual(sheets[0]["records"], [[""]])

    def test_blob_refused(self):
        """Datatypes In SQLite, 2: a BLOB has no text form."""
        data = database("CREATE TABLE t(a)", "INSERT INTO t VALUES (x'00ff')")
        with self.assertRaises(ValueError):
            sqlite.load(io.BytesIO(data), errors="ignore")

    def test_view_left_behind(self):
        """Database File Format, 2.6: a view is not a table."""
        data = database(
            "CREATE TABLE t(a)",
            "CREATE VIEW v AS SELECT a FROM t",
        )
        with self.assertRaises(ValueError):
            sqlite.load(io.BytesIO(data))

    def test_view_named_in_the_report(self):
        """A view is named by its type and name."""
        data = database(
            "CREATE TABLE t(a TEXT)",
            "CREATE VIEW v AS SELECT a FROM t",
        )
        with self.assertLogs("mtsv.integrations", "WARNING") as caught:
            sqlite.load(io.BytesIO(data), errors="ignore")
        self.assertEqual(caught.records[0].left_behind, ["view 'v'"])

    def test_internal_table_not_left_behind(self):
        """2.6.2: an object named "sqlite_..." is internal, not content."""
        data = database(
            "CREATE TABLE t(a INTEGER PRIMARY KEY AUTOINCREMENT, b TEXT)",
            "INSERT INTO t(b) VALUES ('x')",
        )
        with self.assertLogs("mtsv.integrations", "WARNING") as caught:
            sheets = sqlite.load(io.BytesIO(data), errors="ignore")
        self.assertEqual([sheet["sheet name"] for sheet in sheets], ["t"])
        self.assertEqual(
            caught.records[0].left_behind, ["INTEGER values in column 'a'"]
        )

    def test_internal_index_not_left_behind(self):
        """2.6.2: the index SQLite makes for UNIQUE is its own."""
        data = database(
            "CREATE TABLE t(a TEXT UNIQUE)",
            "INSERT INTO t VALUES ('x')",
        )
        self.assertEqual(
            sqlite.load(io.BytesIO(data)),
            [{"sheet name": "t", "header": ["a"], "records": [["x"]]}],
        )

    def test_storage_class_names_the_value(self):
        """Datatypes In SQLite, 2: the storage classes name the value."""
        data = database(
            "CREATE TABLE t(a, b)",
            "INSERT INTO t VALUES (1, 2.5)",
        )
        with self.assertLogs("mtsv.integrations", "WARNING") as caught:
            sqlite.load(io.BytesIO(data), errors="ignore")
        self.assertEqual(
            caught.records[0].left_behind,
            ["INTEGER values in column 'a'", "REAL values in column 'b'"],
        )

    def test_unknown_errors_value(self):
        """An errors value that is neither name raises LookupError."""
        buffer = io.BytesIO()
        sqlite.dump(SHEET, buffer)
        buffer.seek(0)
        with self.assertRaises(LookupError):
            sqlite.load(buffer, errors="replace")
