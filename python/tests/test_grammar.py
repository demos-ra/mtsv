"""Test mtsv._grammar against the draft, Grammar."""

import unittest

from mtsv import _grammar


class TestFieldChar(unittest.TestCase):
    """field_char: field-char = %x00-08 / %x0B / %x0E-10FFFF."""

    def test_edges_inside(self):
        """Each edge of each range is a field-char."""
        for code in (0x00, 0x08, 0x0B, 0x0E, 0x10FFFF):
            with self.subTest(hex(code)):
                self.assertTrue(_grammar.field_char(chr(code)))

    def test_separators(self):
        """HTAB, LF, FF and CR are not field-chars."""
        for char in (_grammar.HTAB, _grammar.LF, _grammar.FF, _grammar.CR):
            with self.subTest(hex(ord(char))):
                self.assertFalse(_grammar.field_char(char))
