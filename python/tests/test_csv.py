"""Test mtsv.integrations.csv against RFC 4180 and RFC 7111."""

import io
import unittest

from mtsv.integrations import csv

from support import load_json, paths

SHEET = [{"sheet name": "", "header": ["a", "b"], "records": [["1", "2"]]}]
BYTES = b"a,b\r\n1,2\r\n"


class TestDump(unittest.TestCase):
    """Writing CSV."""

    def test_empty_name(self):
        """RFC 4180, 2: a line ends with CRLF, the header first."""
        buffer = io.BytesIO()
        csv.dump(SHEET, buffer)
        self.assertEqual(buffer.getvalue(), BYTES)

    def test_no_sheets(self):
        """RFC 4180, 2: a file holds a record; no sheets is refused."""
        with self.assertRaises(ValueError):
            csv.dump([], io.BytesIO())

    def test_more_than_one_sheet(self):
        """Two sheets are refused."""
        sheets = [
            {"sheet name": "", "header": ["a"], "records": []},
            {"sheet name": "S", "header": ["a"], "records": []},
        ]
        with self.assertRaises(ValueError):
            csv.dump(sheets, io.BytesIO())

    def test_named_sheet(self):
        """A sheet name that is not empty is refused."""
        sheets = [{"sheet name": "S", "header": ["a"], "records": []}]
        with self.assertRaises(ValueError):
            csv.dump(sheets, io.BytesIO())

    def test_empty_sheet(self):
        """RFC 4180, 2: a file holds a record; no lines is refused."""
        sheets = [{"sheet name": "", "header": None, "records": []}]
        with self.assertRaises(ValueError):
            csv.dump(sheets, io.BytesIO())

    def test_quoting(self):
        """RFC 4180, 6 and 7: quote a comma, double a quotation mark."""
        sheets = [{"sheet name": "", "header": ["a,b", 'c"d'], "records": []}]
        buffer = io.BytesIO()
        csv.dump(sheets, buffer)
        self.assertEqual(buffer.getvalue(), b'"a,b","c""d"\r\n')

    def test_cannot_be_represented(self):
        """Each file that MTSV cannot hold is refused by dump."""
        for path in paths("cannot-be-represented", ".json"):
            with self.subTest(path.name):
                with self.assertRaises(ValueError):
                    csv.dump(load_json(path), io.BytesIO())


class TestLoad(unittest.TestCase):
    """Reading CSV."""

    def test_round_trip(self):
        """What dump writes, load reads back unchanged."""
        self.assertEqual(csv.load(io.BytesIO(BYTES)), SHEET)

    def test_line_feed_alone(self):
        """RFC 7111, 5.1: an implementation may use other values."""
        self.assertEqual(csv.load(io.BytesIO(b"a,b\n1,2\n")), SHEET)

    def test_empty_file(self):
        """RFC 4180, 2: an empty file is a record of an empty field."""
        self.assertEqual(
            csv.load(io.BytesIO(b"")),
            [{"sheet name": "", "header": [""], "records": []}],
        )

    def test_blank_line(self):
        """RFC 4180, 2: a blank line is a record of an empty field."""
        self.assertEqual(
            csv.load(io.BytesIO(b"a\r\n\r\n")),
            [{"sheet name": "", "header": ["a"], "records": [[""]]}],
        )

    def test_line_break_in_a_field(self):
        """A field holding a line break cannot be held by MTSV."""
        with self.assertRaises(ValueError):
            csv.load(io.BytesIO(b'a\r\n"b\r\nc"\r\n'))

    def test_field_count_must_match(self):
        """A line with a different field count is refused."""
        with self.assertRaises(ValueError):
            csv.load(io.BytesIO(b"a,b\r\n1\r\n"))

    def test_not_utf_8(self):
        """A file that is not UTF-8 raises ValueError."""
        with self.assertRaises(ValueError):
            csv.load(io.BytesIO(b"\xff\xfe"))

    def test_unknown_errors_value(self):
        """An errors value that is neither name raises LookupError."""
        with self.assertRaises(LookupError):
            csv.load(io.BytesIO(BYTES), errors="replace")
