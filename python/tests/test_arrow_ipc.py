"""Test mtsv.integrations.arrow_ipc against the Arrow Columnar Format."""

import io
import unittest

try:
    import pyarrow as pa

    from mtsv.integrations import arrow_ipc
except ImportError:
    pa = arrow_ipc = None

from support import load_json, paths

SHEET = [{"sheet name": "", "header": ["a", "b"], "records": [["1", "2"]]}]


def refused(sheets):
    """Return whether one table cannot hold these sheets."""
    return len(sheets) != 1 or sheets[0]["sheet name"] != ""


@unittest.skipUnless(pa, "requires pyarrow")
class TestDump(unittest.TestCase):
    """Writing an Arrow IPC file."""

    def test_magic_number(self):
        """IPC File Format: the file starts with the magic ARROW1."""
        buffer = io.BytesIO()
        arrow_ipc.dump(SHEET, buffer)
        self.assertTrue(buffer.getvalue().startswith(b"ARROW1"))

    def test_no_sheets(self):
        """IPC Streaming Format: one schema; no sheets is refused."""
        with self.assertRaises(ValueError):
            arrow_ipc.dump([], io.BytesIO())

    def test_more_than_one_sheet(self):
        """Two sheets are refused."""
        sheets = [
            {"sheet name": "", "header": ["a"], "records": []},
            {"sheet name": "S", "header": ["a"], "records": []},
        ]
        with self.assertRaises(ValueError):
            arrow_ipc.dump(sheets, io.BytesIO())

    def test_named_sheet(self):
        """A sheet name that is not empty is refused."""
        sheets = [{"sheet name": "S", "header": ["a"], "records": []}]
        with self.assertRaises(ValueError):
            arrow_ipc.dump(sheets, io.BytesIO())

    def test_cannot_be_represented(self):
        """Each file that MTSV cannot hold is refused by dump."""
        for path in paths("cannot-be-represented", ".json"):
            with self.subTest(path.name):
                with self.assertRaises(ValueError):
                    arrow_ipc.dump(load_json(path), io.BytesIO())


@unittest.skipUnless(pa, "requires pyarrow")
class TestLoad(unittest.TestCase):
    """Reading an Arrow IPC file."""

    def test_round_trip(self):
        """What dump writes, load reads back unchanged."""
        buffer = io.BytesIO()
        arrow_ipc.dump(SHEET, buffer)
        buffer.seek(0)
        self.assertEqual(arrow_ipc.load(buffer), SHEET)

    def test_conforming_round_trip(self):
        """Each conforming result one table holds comes back."""
        for path in paths("conforming", ".json"):
            with self.subTest(path.name):
                value = load_json(path)
                if refused(value):
                    self.skipTest("one table cannot hold these sheets")
                buffer = io.BytesIO()
                arrow_ipc.dump(value, buffer)
                buffer.seek(0)
                self.assertEqual(arrow_ipc.load(buffer), value)

    def test_empty_sheet(self):
        """A sheet with no lines is a table without columns."""
        sheets = [{"sheet name": "", "header": None, "records": []}]
        buffer = io.BytesIO()
        arrow_ipc.dump(sheets, buffer)
        buffer.seek(0)
        self.assertEqual(arrow_ipc.load(buffer), sheets)

    def test_not_an_arrow_file(self):
        """A file that is not an Arrow IPC file raises ValueError."""
        with self.assertRaises(ValueError):
            arrow_ipc.load(io.BytesIO(b"not arrow"))

    def test_magic_without_a_body(self):
        """A file with the magic number but no footer raises ValueError."""
        with self.assertRaises(ValueError):
            arrow_ipc.load(io.BytesIO(b"ARROW1" + b"\x00" * 40 + b"ARROW1"))

    def test_type_left_behind(self):
        """A column that is not text is left behind, so strict refuses."""
        table = pa.table({"a": pa.array([1, 2], pa.int64())})
        buffer = io.BytesIO()
        with pa.ipc.new_file(buffer, table.schema) as writer:
            writer.write_table(table)
        buffer.seek(0)
        with self.assertRaises(ValueError):
            arrow_ipc.load(buffer)

    def test_unknown_errors_value(self):
        """An errors value that is neither name raises LookupError."""
        buffer = io.BytesIO()
        arrow_ipc.dump(SHEET, buffer)
        buffer.seek(0)
        with self.assertRaises(LookupError):
            arrow_ipc.load(buffer, errors="replace")
