"""Test mtsv.integrations.json against RFC 8259 and the corpus.

The conformance corpus holds the result of every parse as JSON, so
the same sheets must give the same bytes as the file beside them.
"""

import io
import unittest

from mtsv.integrations import json

from support import load_json, paths

SHEET = b'[{"sheet name":null,"header":["a"],"records":[]}]'
EXPECTED = [{"sheet name": None, "header": ["a"], "records": []}]


class TestDump(unittest.TestCase):
    """Writing JSON."""

    def test_conforming_matches_the_corpus(self):
        """Each result gives the bytes of the file beside it."""
        for path in paths("conforming", ".json"):
            with self.subTest(path.name):
                buffer = io.BytesIO()
                json.dump(load_json(path), buffer)
                self.assertEqual(buffer.getvalue(), path.read_bytes())

    def test_cannot_be_represented(self):
        """Each file that MTSV cannot hold is refused by dump."""
        for path in paths("cannot-be-represented", ".json"):
            with self.subTest(path.name):
                with self.assertRaises(ValueError):
                    json.dump(load_json(path), io.BytesIO())


class TestLoad(unittest.TestCase):
    """Reading JSON."""

    def test_conforming(self):
        """Each .json file loads to the result it holds."""
        for path in paths("conforming", ".json"):
            with self.subTest(path.name):
                with path.open("rb") as fp:
                    self.assertEqual(json.load(fp), load_json(path))

    def test_encoding_signature(self):
        """RFC 8259, 8.1: a parser may ignore a byte order mark."""
        data = "﻿".encode("utf-8") + SHEET
        self.assertEqual(json.load(io.BytesIO(data)), EXPECTED)

    def test_not_json(self):
        """A file that is not JSON raises ValueError."""
        with self.assertRaises(ValueError):
            json.load(io.BytesIO(b"not json"))

    def test_member_outside_the_data_model(self):
        """A member outside the three is left behind, not kept."""
        data = b'[{"sheet name":null,"header":["a"],"records":[],"x":1}]'
        with self.assertRaises(ValueError):
            json.load(io.BytesIO(data))
        self.assertEqual(
            json.load(io.BytesIO(data), errors="ignore"), EXPECTED
        )

    def test_a_field_is_a_string(self):
        """A field that is not a JSON string raises ValueError."""
        data = b'[{"sheet name":null,"header":[1],"records":[]}]'
        with self.assertRaises(ValueError):
            json.load(io.BytesIO(data))

    def test_a_sheet_has_every_member(self):
        """A sheet missing one of the three raises ValueError."""
        data = b'[{"sheet name":null,"header":["a"]}]'
        with self.assertRaises(ValueError):
            json.load(io.BytesIO(data))

    def test_sheets_are_an_array(self):
        """A document that is not an array raises ValueError."""
        with self.assertRaises(ValueError):
            json.load(io.BytesIO(b'{"sheet name":null}'))

    def test_unknown_errors_value(self):
        """An errors value that is neither name raises LookupError."""
        with self.assertRaises(LookupError):
            json.load(io.BytesIO(SHEET), errors="replace")
