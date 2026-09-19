"""Test the mtsv command against the guidelines that govern it.

Each case that confirms a guideline names it: G-n is guideline n of
POSIX.1-2017 XBD 12.2, Utility Syntax Guidelines.
"""

import contextlib
import io
import logging
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mtsv._command import run

from support import CONFORMANCE

ORIGINAL = CONFORMANCE / "conforming" / "multiple-sheets.mtsv"


class Stream:
    """A stand-in for sys.stdin or sys.stdout, holding bytes."""

    def __init__(self, data=b""):
        """Hold the bytes to be read, or collect the ones written."""
        self.buffer = io.BytesIO(data)


class TestRun(unittest.TestCase):
    """The command line: mtsv."""

    def test_converts_each_format(self):
        """Each file format converts from MTSV and back to it."""
        for suffix in (".ods", ".xlsx"):
            with self.subTest(suffix):
                with tempfile.TemporaryDirectory() as directory:
                    book = Path(directory, "book" + suffix)
                    back = Path(directory, "back.mtsv")
                    run([str(ORIGINAL), str(book)])
                    run([str(book), str(back)])
                    self.assertEqual(back.read_bytes(), ORIGINAL.read_bytes())

    def test_converts_between_two_formats(self):
        """A conversion between two formats passes through MTSV."""
        with tempfile.TemporaryDirectory() as directory:
            spreadsheet = Path(directory, "book.ods")
            workbook = Path(directory, "book.xlsx")
            back = Path(directory, "back.mtsv")
            run([str(ORIGINAL), str(spreadsheet)])
            run([str(spreadsheet), str(workbook)])
            run([str(workbook), str(back)])
            self.assertEqual(back.read_bytes(), ORIGINAL.read_bytes())

    def test_extension_without_a_format_stops(self):
        """An extension that names no format stops the conversion."""
        with tempfile.TemporaryDirectory() as directory:
            other = Path(directory, "book.txt")
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    run([str(ORIGINAL), str(other)])

    def test_missing_file_stops(self):
        """GNU 4.4: a missing file is named, not traced."""
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory, "missing.ods")
            with self.assertRaises(SystemExit) as caught:
                run([str(missing), str(Path(directory, "back.mtsv"))])
            self.assertTrue(str(caught.exception.code).startswith(f"mtsv: {missing}: "))

    def test_left_behind(self):
        """-e ignore logs what is left behind; -e strict stops."""
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory, "book.json")
            result = Path(directory, "book.mtsv")
            source.write_text(
                '[{"sheet name":"S","header":["a"],"records":[],"x":1}]',
                encoding="utf-8",
            )
            with self.assertLogs("mtsv.integrations", logging.WARNING) as logs:
                run([str(source), str(result)])
            (record,) = logs.records
            self.assertEqual(record.left_behind, ["x"])
            with self.assertRaises(SystemExit):
                run(["-e", "strict", str(source), str(result)])

    def test_errors_option_has_a_single_character_name(self):
        """G-3, G-9: -e names the option, and options come first."""
        with tempfile.TemporaryDirectory() as directory:
            book = Path(directory, "book.ods")
            back = Path(directory, "back.mtsv")
            run([str(ORIGINAL), str(book)])
            run(["-e", "ignore", str(book), str(back)])
            self.assertEqual(back.read_bytes(), ORIGINAL.read_bytes())

    def test_output_option(self):
        """GNU 4.8: -o names the output file as well."""
        with tempfile.TemporaryDirectory() as directory:
            book = Path(directory, "book.ods")
            back = Path(directory, "back.mtsv")
            run(["-o", str(book), str(ORIGINAL)])
            run(["-o", str(back), str(book)])
            self.assertEqual(back.read_bytes(), ORIGINAL.read_bytes())

    def test_output_given_twice_stops(self):
        """An output file given both ways is refused, not guessed."""
        with tempfile.TemporaryDirectory() as directory:
            book = Path(directory, "book.ods")
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    run(["-o", str(book), str(ORIGINAL), str(book)])

    def test_output_derived_from_the_input(self):
        """A lone input operand converts to MTSV beside it."""
        with tempfile.TemporaryDirectory() as directory:
            book = Path(directory, "book.ods")
            run([str(ORIGINAL), str(book)])
            run([str(book)])
            self.assertEqual(
                Path(directory, "book.mtsv").read_bytes(),
                ORIGINAL.read_bytes(),
            )

    def test_mtsv_input_needs_an_output(self):
        """An MTSV input with no output is refused."""
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                run([str(ORIGINAL)])

    def test_standard_input_needs_an_output(self):
        """G-13: "-" carries no name to derive an output from."""
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                run(["-"])

    def test_version_names_the_program(self):
        """GNU 4.8.1: the first line is name then version."""
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            with self.assertRaises(SystemExit) as caught:
                run(["--version"])
        self.assertEqual(caught.exception.code, 0)
        first = stream.getvalue().splitlines()[0]
        self.assertRegex(first, r"^mtsv [0-9]+\.[0-9]+\.[0-9]+$")

    def test_help_says_where_to_report(self):
        """GNU 4.8.2: --help ends with where to report."""
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            with self.assertRaises(SystemExit) as caught:
                run(["--help"])
        self.assertEqual(caught.exception.code, 0)
        self.assertIn("Report bugs to:", stream.getvalue())

    def test_standard_output(self):
        """G-13: an output operand of "-" is standard output."""
        with tempfile.TemporaryDirectory() as directory:
            book = Path(directory, "book.xlsx")
            run([str(ORIGINAL), str(book)])
            stream = Stream()
            with mock.patch.object(sys, "stdout", stream):
                run([str(book), "-"])
            self.assertEqual(stream.buffer.getvalue(), ORIGINAL.read_bytes())

    def test_standard_input(self):
        """G-13: an input operand of "-" is standard input."""
        with tempfile.TemporaryDirectory() as directory:
            book = Path(directory, "book.xlsx")
            back = Path(directory, "back.mtsv")
            stream = Stream(ORIGINAL.read_bytes())
            with mock.patch.object(sys, "stdin", stream):
                run(["-", str(book)])
            run([str(book), str(back)])
            self.assertEqual(back.read_bytes(), ORIGINAL.read_bytes())
