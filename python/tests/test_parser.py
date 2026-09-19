"""Test mtsv._parser against the draft, Grammar and Parsers."""

import pickle
import unittest

from mtsv import _parser

FF = chr(0x0C)


class TestMTSVFile(unittest.TestCase):
    """mtsv_file: mtsv-file = first-sheet *named-sheet."""

    def test_empty(self):
        """An empty text has no sheets."""
        self.assertEqual(_parser.mtsv_file("", 0), (0, []))

    def test_first_sheet(self):
        """Lines before the first FF are a sheet whose name is empty."""
        self.assertEqual(
            _parser.mtsv_file("a\n", 0),
            (2, [{"sheet name": "", "header": ["a"], "records": []}]),
        )

    def test_named_empty_sheet(self):
        """An FF line with no lines after it is an empty sheet."""
        self.assertEqual(
            _parser.mtsv_file(FF + "S\n", 0),
            (3, [{"sheet name": "S", "header": None, "records": []}]),
        )


class TestSignature(unittest.TestCase):
    """signature: a U+FEFF at the start of the text."""

    def test_skipped_at_the_start(self):
        """A U+FEFF at index 0 is skipped."""
        self.assertEqual(_parser.signature(_parser.SIGNATURE + "a\n", 0), 1)

    def test_none(self):
        """Without a U+FEFF the index is kept."""
        self.assertEqual(_parser.signature("a\n", 0), 0)

    def test_kept_elsewhere(self):
        """A U+FEFF past the start is not a signature."""
        self.assertEqual(_parser.signature("a" + _parser.SIGNATURE, 1), 1)


class TestEol(unittest.TestCase):
    """eol: eol = LF / CRLF."""

    def test_line_breaks(self):
        """LF and CRLF are line breaks."""
        self.assertEqual(_parser.eol("\n", 0), (1, "\n"))
        self.assertEqual(_parser.eol("\r\n", 0), (2, "\r\n"))

    def test_refused(self):
        """A lone CR, or no line break, raises MTSVDecodeError."""
        for src in ("\r", "a", ""):
            with self.subTest(repr(src)):
                with self.assertRaises(_parser.MTSVDecodeError):
                    _parser.eol(src, 0)


class TestCheckWidth(unittest.TestCase):
    """check_width: a record as wide as its header."""

    def test_same_width(self):
        """A record as wide as its header passes."""
        _parser.check_width("", 0, ["a", "b"], ["c", "d"])

    def test_refused_where_the_record_starts(self):
        """A record of another width is refused at its first char."""
        with self.assertRaises(_parser.MTSVDecodeError) as caught:
            _parser.mtsv_file("a\tb\nc\n", 0)
        error = caught.exception
        self.assertEqual((error.pos, error.lineno, error.colno), (4, 2, 1))


class TestMTSVDecodeError(unittest.TestCase):
    """MTSVDecodeError, which follows json.JSONDecodeError."""

    def test_pickle(self):
        """The error survives pickling with its properties."""
        with self.assertRaises(_parser.MTSVDecodeError) as caught:
            _parser.mtsv_file("a", 0)
        error = caught.exception
        copy = pickle.loads(pickle.dumps(error))
        self.assertEqual(
            (copy.msg, copy.doc, copy.pos, copy.lineno, copy.colno),
            (error.msg, error.doc, error.pos, error.lineno, error.colno),
        )
