"""Test mtsv.integrations._errors: the errors values and the report."""

import logging
import unittest

from mtsv.integrations import _errors


class TestLookupError(unittest.TestCase):
    """lookup_error: the errors values "strict" and "ignore"."""

    def test_known(self):
        """The values "strict" and "ignore" pass."""
        for name in ("strict", "ignore"):
            with self.subTest(name):
                _errors.lookup_error(name)

    def test_unknown(self):
        """Any other name raises LookupError."""
        for name in ("replace", "", "Strict"):
            with self.subTest(name):
                with self.assertRaises(LookupError):
                    _errors.lookup_error(name)


class TestReport(unittest.TestCase):
    """report: refuse or note what would be left behind."""

    def test_nothing_left_behind(self):
        """No names: nothing is raised or logged, in either door."""
        for errors in ("strict", "ignore"):
            with self.subTest(errors):
                with self.assertNoLogs("mtsv.integrations"):
                    _errors.report(set(), errors)

    def test_strict(self):
        """errors="strict" raises ValueError naming what is left."""
        with self.assertRaises(ValueError) as caught:
            _errors.report({"y", "x"}, "strict")
        self.assertIn("x, y", str(caught.exception))

    def test_ignore(self):
        """errors="ignore" logs a warning carrying the sorted names."""
        with self.assertLogs("mtsv.integrations", logging.WARNING) as logs:
            _errors.report({"y", "x"}, "ignore")
        (record,) = logs.records
        self.assertEqual(record.left_behind, ["x", "y"])
        self.assertEqual(record.getMessage(), "left behind: x, y")
