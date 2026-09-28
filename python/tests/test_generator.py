"""Test mtsv._generator against the draft, Grammar and Generators."""

import unittest

from mtsv import _generator

SEPARATORS = (chr(0x09), chr(0x0A), chr(0x0C), chr(0x0D))


class TestMTSVFile(unittest.TestCase):
    """mtsv_file: mtsv-file = first-sheet *named-sheet."""

    def test_refusal_names_the_position(self):
        """A refusal names the sheet, the line and the field."""
        sheets = [
            {"sheet name": "", "header": ["a"], "records": []},
            {"sheet name": "S", "header": ["a", "b"], "records": [["c", "d\n"]]},
        ]
        with self.assertRaises(ValueError) as caught:
            _generator.mtsv_file(sheets)
        self.assertTrue(str(caught.exception).endswith(": sheet 2, record 1, field 2"))


class TestRecord(unittest.TestCase):
    """record: record = field *(HTAB field) eol."""

    def test_fields(self):
        """Fields are joined by HT and end with LF."""
        self.assertEqual(_generator.record(["a", "", "b"], "L"), "a\t\tb\n")

    def test_no_fields(self):
        """A record of no fields raises ValueError naming the line."""
        with self.assertRaises(ValueError) as caught:
            _generator.record([], "L")
        self.assertTrue(str(caught.exception).endswith(": L"))


class TestField(unittest.TestCase):
    """field: field = *field-char."""

    def test_text(self):
        """A field of field-chars is written as it is."""
        self.assertEqual(_generator.field("a b", "P"), "a b")

    def test_refused(self):
        """A field holding HT, LF, FF or CR raises ValueError naming it."""
        for char in SEPARATORS:
            with self.subTest(hex(ord(char))):
                with self.assertRaises(ValueError) as caught:
                    _generator.field("a" + char, "P")
                self.assertTrue(str(caught.exception).endswith(": P"))


class TestSheetName(unittest.TestCase):
    """sheet_name: sheet-name = *field-char."""

    def test_text(self):
        """A sheet name of field-chars is written as it is."""
        self.assertEqual(_generator.sheet_name("S", 0), "S")

    def test_not_text(self):
        """A sheet name that is not text raises ValueError naming it."""
        with self.assertRaises(ValueError) as caught:
            _generator.sheet_name(None, 0)
        self.assertTrue(str(caught.exception).endswith(": sheet 1, sheet name"))

    def test_refused(self):
        """A sheet name holding HT, LF, FF or CR raises ValueError."""
        for char in SEPARATORS:
            with self.subTest(hex(ord(char))):
                with self.assertRaises(ValueError) as caught:
                    _generator.sheet_name("S" + char, 1)
                self.assertTrue(str(caught.exception).endswith(": sheet 2, sheet name"))


class TestCheckSheet(unittest.TestCase):
    """check_sheet: the lines of a sheet fit the data model."""

    def test_fits(self):
        """An empty sheet, and records as wide as the header, pass."""
        for sheet in (
            {"sheet name": "", "header": None, "records": []},
            {"sheet name": "", "header": ["a"], "records": [["b"]]},
        ):
            with self.subTest(sheet):
                _generator.check_sheet(sheet, 0)

    def test_records_without_a_header(self):
        """Records without a header raise ValueError naming the sheet."""
        sheet = {"sheet name": "", "header": None, "records": [["a"]]}
        with self.assertRaises(ValueError) as caught:
            _generator.check_sheet(sheet, 0)
        self.assertTrue(str(caught.exception).endswith(": sheet 1"))

    def test_other_width(self):
        """A record not as wide as the header raises ValueError naming it."""
        sheet = {"sheet name": "", "header": ["a"], "records": [["b"], ["c", "d"]]}
        with self.assertRaises(ValueError) as caught:
            _generator.check_sheet(sheet, 0)
        self.assertTrue(str(caught.exception).endswith(": sheet 1, record 2"))
