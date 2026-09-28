"""Test mtsv._data_model against the draft, Data Model."""

import unittest

from mtsv import _data_model


class TestSheet(unittest.TestCase):
    """sheet: a sheet, counted from 1."""

    def test_first(self):
        """Index 0 is sheet 1."""
        self.assertEqual(_data_model.sheet(0), "sheet 1")


class TestSheetName(unittest.TestCase):
    """sheet_name: the sheet name of a sheet."""

    def test_named(self):
        """The sheet name follows its sheet."""
        self.assertEqual(_data_model.sheet_name(1), "sheet 2, sheet name")


class TestHeader(unittest.TestCase):
    """header: the header of a sheet."""

    def test_named(self):
        """The header follows its sheet."""
        self.assertEqual(_data_model.header(1), "sheet 2, header")


class TestRecord(unittest.TestCase):
    """record: a record, counted from 1 after the header."""

    def test_named(self):
        """Index 0 is record 1 of its sheet."""
        self.assertEqual(_data_model.record(1, 0), "sheet 2, record 1")


class TestField(unittest.TestCase):
    """field: a field, counted from 1 in its line."""

    def test_of_a_line(self):
        """A field follows the header or record it is in."""
        for line, expected in (
            (_data_model.header(0), "sheet 1, header, field 3"),
            (_data_model.record(0, 13), "sheet 1, record 14, field 3"),
        ):
            with self.subTest(line):
                self.assertEqual(_data_model.field(line, 2), expected)

    def test_of_a_sheet(self):
        """A field of every line follows its sheet."""
        self.assertEqual(_data_model.field(_data_model.sheet(0), 0), "sheet 1, field 1")
