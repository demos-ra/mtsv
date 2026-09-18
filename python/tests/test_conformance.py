"""Run the MTSV conformance files against the mtsv package."""

import io
import unittest

import mtsv

from support import load_json, paths

FF = chr(0x0C)


class TestConforming(unittest.TestCase):
    """Conforming files: parse to their JSON, generate back from it."""

    def test_parse(self):
        """Each .mtsv file parses to its .json result."""
        for path in paths("conforming", ".mtsv"):
            with self.subTest(path.name):
                with path.open("rb") as file:
                    expected = load_json(path.with_suffix(".json"))
                    self.assertEqual(mtsv.load(file), expected)

    def test_generate(self):
        """Each .json result generates a file that parses back to it."""
        for path in paths("conforming", ".json"):
            with self.subTest(path.name):
                value = load_json(path)
                self.assertEqual(mtsv.loads(mtsv.dumps(value)), value)

    def test_generate_writes_ff_lines(self):
        """Each generated file has an FF line before every sheet."""
        for path in paths("conforming", ".json"):
            with self.subTest(path.name):
                value = load_json(path)
                text = mtsv.dumps(value)
                self.assertEqual(text.count(FF), len(value))
                if value:
                    self.assertTrue(text.startswith(FF))

    def test_dump_encodes_utf_8(self):
        """dump writes the dumps string encoded as UTF-8."""
        for path in paths("conforming", ".json"):
            with self.subTest(path.name):
                value = load_json(path)
                buffer = io.BytesIO()
                mtsv.dump(value, buffer)
                expected = mtsv.dumps(value).encode("utf-8")
                self.assertEqual(buffer.getvalue(), expected)


class TestNonConforming(unittest.TestCase):
    """Non-conforming files: parsers may accept or reject them.

    This implementation rejects them, following RFC 9413, 5.1.
    """

    def test_parse_rejects(self):
        """Each non-conforming file raises ValueError."""
        for path in paths("non-conforming", ".mtsv"):
            with self.subTest(path.name):
                with path.open("rb") as file:
                    with self.assertRaises(ValueError):
                        mtsv.load(file)


class TestCannotBeRepresented(unittest.TestCase):
    """Values and sheets that MTSV cannot hold."""

    def test_generate_rejects(self):
        """Each result raises ValueError instead of being written."""
        for path in paths("cannot-be-represented", ".json"):
            with self.subTest(path.name):
                with self.assertRaises(ValueError):
                    mtsv.dumps(load_json(path))
