"""Test mtsv.integrations._xml against XML 1.0, 2.2, production [2]."""

import unittest
from xml.etree import ElementTree

from mtsv.integrations import _xml

NAMESPACE = "urn:example"


class TestChar(unittest.TestCase):
    """char: XML 1.0 Char, the ranges of production [2]."""

    def test_edges_inside(self):
        """Each edge of each range is a Char."""
        for code in (
            0x09,
            0x0A,
            0x0D,
            0x20,
            0xD7FF,
            0xE000,
            0xFFFD,
            0x10000,
            0x10FFFF,
        ):
            with self.subTest(hex(code)):
                self.assertTrue(_xml.char(chr(code)))

    def test_edges_outside(self):
        """Each code point just outside a range is not a Char."""
        for code in (0x00, 0x08, 0x0B, 0x0C, 0x0E, 0x1F, 0xD800, 0xFFFE):
            with self.subTest(hex(code)):
                self.assertFalse(_xml.char(chr(code)))


class TestCheckChars(unittest.TestCase):
    """check_chars: every sheet name and field is made of Chars."""

    def test_allowed(self):
        """Sheets of Chars, and an empty sheet, pass."""
        sheets = [
            {"sheet name": "S", "header": ["a"], "records": [["b"]]},
            {"sheet name": "", "header": None, "records": []},
        ]
        _xml.check_chars(sheets, "XML")

    def test_refused(self):
        """A sheet name or field with a non-Char raises ValueError."""
        bad = chr(0x0B)
        for sheets in (
            [{"sheet name": bad, "header": ["a"], "records": []}],
            [{"sheet name": "S", "header": [bad], "records": []}],
            [{"sheet name": "S", "header": ["a"], "records": [[bad]]}],
        ):
            with self.subTest(sheets):
                with self.assertRaises(ValueError):
                    _xml.check_chars(sheets, "XML")


class TestPrefixed(unittest.TestCase):
    """prefixed: {namespace}local written with a known prefix."""

    def test_known_prefix(self):
        """A known namespace is written with its prefix."""
        name = "{" + NAMESPACE + "}a"
        self.assertEqual(_xml.prefixed(name, {NAMESPACE: "p"}), "p:a")

    def test_empty_prefix(self):
        """A namespace with an empty prefix gives the local name."""
        name = "{" + NAMESPACE + "}a"
        self.assertEqual(_xml.prefixed(name, {NAMESPACE: ""}), "a")

    def test_unknown_namespace(self):
        """An unknown namespace is kept as it is."""
        name = "{" + NAMESPACE + "}a"
        self.assertEqual(_xml.prefixed(name, {}), name)

    def test_no_namespace(self):
        """A name in no namespace is kept as it is."""
        self.assertEqual(_xml.prefixed("a", {NAMESPACE: "p"}), "a")


class TestAttributesLeftBehind(unittest.TestCase):
    """attributes_left_behind: attributes outside the mapping."""

    def test_returns_others(self):
        """Only the attributes not allowed are returned."""
        element = ElementTree.fromstring(f"<e xmlns:p='{NAMESPACE}' a='1' p:b='2'/>")
        left = _xml.attributes_left_behind(element, ("a",), {NAMESPACE: "p"})
        self.assertEqual(left, {"p:b"})
