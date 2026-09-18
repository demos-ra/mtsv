"""Test mtsv.integrations: formats by extension, and the report."""

import io
import logging
import unittest

import mtsv.integrations

SHEETS = [{"sheet name": "", "header": ["a"], "records": [["b"]]}]


class TestFormats(unittest.TestCase):
    """load and dump: the format each file extension names."""

    def test_round_trip(self):
        """Each extension writes a file that it reads back unchanged."""
        for suffix in (mtsv.integrations.MTSV, *mtsv.integrations.FORMATS):
            with self.subTest(suffix):
                buffer = io.BytesIO()
                mtsv.integrations.dump(suffix, SHEETS, buffer)
                buffer.seek(0)
                result = mtsv.integrations.load(suffix, buffer)
                self.assertEqual(result, SHEETS)

    def test_unknown_extension(self):
        """An extension that names no format raises ValueError."""
        with self.assertRaises(ValueError):
            mtsv.integrations.dump(".txt", SHEETS, io.BytesIO())
        with self.assertRaises(ValueError):
            mtsv.integrations.load(".txt", io.BytesIO(b"a\n"))


class TestReport(unittest.TestCase):
    """report: refuse or note what would be left behind."""

    def test_nothing_left_behind(self):
        """No names: nothing is raised or logged, in either door."""
        for errors in ("strict", "ignore"):
            with self.subTest(errors):
                with self.assertNoLogs("mtsv.integrations"):
                    mtsv.integrations.report(set(), errors)

    def test_strict(self):
        """errors="strict" raises ValueError naming what is left."""
        with self.assertRaises(ValueError) as caught:
            mtsv.integrations.report({"y", "x"}, "strict")
        self.assertIn("x, y", str(caught.exception))

    def test_ignore(self):
        """errors="ignore" logs a warning carrying the sorted names."""
        with self.assertLogs("mtsv.integrations", logging.WARNING) as logs:
            mtsv.integrations.report({"y", "x"}, "ignore")
        record, = logs.records
        self.assertEqual(record.left_behind, ["x", "y"])
        self.assertEqual(record.getMessage(), "left behind: x, y")
