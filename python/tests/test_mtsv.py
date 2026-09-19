"""Test the mtsv interface: argument types and sheet names."""

import io
import unittest

import mtsv


class TestLoad(unittest.TestCase):
    """load and loads, which follow tomllib."""

    def test_text_mode_file(self):
        """load raises TypeError for a file opened in text mode."""
        with self.assertRaises(TypeError):
            mtsv.load(io.StringIO("a\n"))

    def test_loads_bytes(self):
        """loads raises TypeError for bytes."""
        with self.assertRaises(TypeError):
            mtsv.loads(b"a\n")

    def test_positional_only(self):
        """load and loads take their argument by position only."""
        with self.assertRaises(TypeError):
            mtsv.loads(s="a\n")
        with self.assertRaises(TypeError):
            mtsv.load(fp=io.BytesIO(b"a\n"))


class TestDumps(unittest.TestCase):
    """dumps, which writes the data model (the draft, Data Model)."""

    def test_sheet_name_is_text(self):
        """A sheet name that is not text raises ValueError."""
        sheets = [{"sheet name": None, "header": ["a"], "records": []}]
        with self.assertRaises(ValueError):
            mtsv.dumps(sheets)
