"""Test mtsv.integrations.parquet against Apache Parquet."""

import io
import unittest

try:
    import pyarrow as pa
    import pyarrow.parquet as pq

    from mtsv.integrations import parquet
except ImportError:
    pa = pq = parquet = None

from support import load_json, paths

SHEET = [{"sheet name": "", "header": ["a", "b"], "records": [["1", "2"]]}]


def refused(sheets):
    """Return whether one table cannot hold these sheets."""
    return len(sheets) != 1 or sheets[0]["sheet name"] != ""


@unittest.skipUnless(pa, "requires pyarrow")
class TestDump(unittest.TestCase):
    """Writing a Parquet file."""

    def test_magic_number(self):
        """The IANA registration: the magic number is PAR1."""
        buffer = io.BytesIO()
        parquet.dump(SHEET, buffer)
        data = buffer.getvalue()
        self.assertTrue(data.startswith(b"PAR1"))
        self.assertTrue(data.endswith(b"PAR1"))

    def test_no_sheets(self):
        """FileMetaData: one schema; no sheets is refused."""
        with self.assertRaises(ValueError):
            parquet.dump([], io.BytesIO())

    def test_more_than_one_sheet(self):
        """Two sheets are refused."""
        sheets = [
            {"sheet name": "", "header": ["a"], "records": []},
            {"sheet name": "S", "header": ["a"], "records": []},
        ]
        with self.assertRaises(ValueError):
            parquet.dump(sheets, io.BytesIO())

    def test_named_sheet(self):
        """A sheet name that is not empty is refused."""
        sheets = [{"sheet name": "S", "header": ["a"], "records": []}]
        with self.assertRaises(ValueError):
            parquet.dump(sheets, io.BytesIO())

    def test_cannot_be_represented(self):
        """Each file that MTSV cannot hold is refused by dump."""
        for path in paths("cannot-be-represented", ".json"):
            with self.subTest(path.name):
                with self.assertRaises(ValueError):
                    parquet.dump(load_json(path), io.BytesIO())


@unittest.skipUnless(pa, "requires pyarrow")
class TestLoad(unittest.TestCase):
    """Reading a Parquet file."""

    def test_round_trip(self):
        """What dump writes, load reads back unchanged."""
        buffer = io.BytesIO()
        parquet.dump(SHEET, buffer)
        buffer.seek(0)
        self.assertEqual(parquet.load(buffer), SHEET)

    def test_conforming_round_trip(self):
        """Each conforming result one table holds comes back."""
        for path in paths("conforming", ".json"):
            with self.subTest(path.name):
                value = load_json(path)
                if refused(value):
                    self.skipTest("one table cannot hold these sheets")
                buffer = io.BytesIO()
                parquet.dump(value, buffer)
                buffer.seek(0)
                self.assertEqual(parquet.load(buffer), value)

    def test_empty_sheet(self):
        """A sheet with no lines is a table without columns."""
        sheets = [{"sheet name": "", "header": None, "records": []}]
        buffer = io.BytesIO()
        parquet.dump(sheets, buffer)
        buffer.seek(0)
        self.assertEqual(parquet.load(buffer), sheets)

    def test_not_a_parquet_file(self):
        """A file that is not a Parquet file raises ValueError."""
        with self.assertRaises(ValueError):
            parquet.load(io.BytesIO(b"not parquet"))

    def test_magic_without_a_body(self):
        """A file with the magic number but no footer raises ValueError."""
        with self.assertRaises(ValueError):
            parquet.load(io.BytesIO(b"PAR1" + b"\x00" * 40 + b"PAR1"))

    def test_type_left_behind(self):
        """A column that is not text is left behind, so strict refuses."""
        table = pa.table({"a": pa.array([1, 2], pa.int64())})
        buffer = io.BytesIO()
        pq.write_table(table, buffer)
        buffer.seek(0)
        with self.assertRaises(ValueError):
            parquet.load(buffer)

    def test_unknown_errors_value(self):
        """An errors value that is neither name raises LookupError."""
        buffer = io.BytesIO()
        parquet.dump(SHEET, buffer)
        buffer.seek(0)
        with self.assertRaises(LookupError):
            parquet.load(buffer, errors="replace")
