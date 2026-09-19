"""Test mtsv._generator against the draft, Grammar and Generators."""

import unittest

from mtsv import _generator

SEPARATORS = (chr(0x09), chr(0x0A), chr(0x0C), chr(0x0D))


class TestRecord(unittest.TestCase):
    """record: record = field *(HTAB field) eol."""

    def test_fields(self):
        """Fields are joined by HT and end with LF."""
        self.assertEqual(_generator.record(["a", "", "b"]), "a\t\tb\n")

    def test_no_fields(self):
        """A record of no fields raises ValueError."""
        with self.assertRaises(ValueError):
            _generator.record([])


class TestField(unittest.TestCase):
    """field: field = *field-char."""

    def test_text(self):
        """A field of field-chars is written as it is."""
        self.assertEqual(_generator.field("a b"), "a b")

    def test_refused(self):
        """A field holding HT, LF, FF or CR raises ValueError."""
        for char in SEPARATORS:
            with self.subTest(hex(ord(char))):
                with self.assertRaises(ValueError):
                    _generator.field("a" + char)


class TestSheetName(unittest.TestCase):
    """sheet_name: sheet-name = *field-char."""

    def test_text(self):
        """A sheet name of field-chars is written as it is."""
        self.assertEqual(_generator.sheet_name("S"), "S")

    def test_not_text(self):
        """A sheet name that is not text raises ValueError."""
        with self.assertRaises(ValueError):
            _generator.sheet_name(None)

    def test_refused(self):
        """A sheet name holding HT, LF, FF or CR raises ValueError."""
        for char in SEPARATORS:
            with self.subTest(hex(ord(char))):
                with self.assertRaises(ValueError):
                    _generator.sheet_name("S" + char)


class TestCheckSheet(unittest.TestCase):
    """check_sheet: the lines of a sheet fit the data model."""

    def test_fits(self):
        """An empty sheet, and records as wide as the header, pass."""
        for sheet in (
            {"sheet name": "", "header": None, "records": []},
            {"sheet name": "", "header": ["a"], "records": [["b"]]},
        ):
            with self.subTest(sheet):
                _generator.check_sheet(sheet)

    def test_records_without_a_header(self):
        """Records without a header raise ValueError."""
        sheet = {"sheet name": "", "header": None, "records": [["a"]]}
        with self.assertRaises(ValueError):
            _generator.check_sheet(sheet)

    def test_other_width(self):
        """A record not as wide as the header raises ValueError."""
        sheet = {"sheet name": "", "header": ["a"], "records": [["b", "c"]]}
        with self.assertRaises(ValueError):
            _generator.check_sheet(sheet)
