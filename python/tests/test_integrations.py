"""Test mtsv.integrations: formats by extension."""

import importlib
import io
import unittest

try:
    import pyarrow as pa
except ImportError:
    pa = None

import mtsv.integrations

SHEETS = [{"sheet name": "", "header": ["a"], "records": [["b"]]}]

# The extensions whose formats the package holds without an extra.
PLAIN = (mtsv.integrations.MTSV, ".csv", ".json", ".ods", ".sqlite", ".xlsx")

# The extensions whose formats need the arrow extra.
COLUMNAR = (".arrow", ".parquet")


def round_trip(suffix):
    """Return the sheets written in a format and read back."""
    buffer = io.BytesIO()
    mtsv.integrations.dump(suffix, SHEETS, buffer)
    buffer.seek(0)
    return mtsv.integrations.load(suffix, buffer)


class TestFormats(unittest.TestCase):
    """load and dump: the format each file extension names."""

    def test_round_trip(self):
        """Each extension writes a file that it reads back unchanged."""
        for suffix in PLAIN:
            with self.subTest(suffix):
                self.assertEqual(round_trip(suffix), SHEETS)

    def test_unknown_extension(self):
        """An extension that names no format raises LookupError."""
        with self.assertRaises(LookupError):
            mtsv.integrations.dump(".txt", SHEETS, io.BytesIO())
        with self.assertRaises(LookupError):
            mtsv.integrations.load(".txt", io.BytesIO(b"a\n"))


@unittest.skipUnless(pa, "requires pyarrow")
class TestColumnarFormats(unittest.TestCase):
    """load and dump: the formats that need the arrow extra."""

    def test_round_trip(self):
        """Each extension writes a file that it reads back unchanged."""
        for suffix in COLUMNAR:
            with self.subTest(suffix):
                self.assertEqual(round_trip(suffix), SHEETS)


class TestLookup(unittest.TestCase):
    """lookup: the module that reads and writes an extension."""

    def test_module_of_extension(self):
        """Each extension gives the module named after its format."""
        self.assertIs(
            mtsv.integrations.lookup(".csv"),
            importlib.import_module("mtsv.integrations.csv"),
        )

    def test_unknown_extension(self):
        """An extension that names no format raises LookupError."""
        with self.assertRaises(LookupError):
            mtsv.integrations.lookup(".txt")
