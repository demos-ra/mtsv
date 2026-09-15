"""Run the MTSV conformance files against the mtsv package."""

import io
import json
import unittest
from pathlib import Path

import mtsv

CONFORMANCE = Path(__file__).resolve().parents[2] / "conformance"


def paths(folder, suffix):
    found = sorted((CONFORMANCE / folder).glob("*" + suffix))
    if not found:
        raise FileNotFoundError(CONFORMANCE / folder)
    return found


def load_json(path):
    with path.open(encoding="utf-8") as file:
        return json.load(file)


class TestConforming(unittest.TestCase):
    def test_parse(self):
        for path in paths("conforming", ".mtsv"):
            with self.subTest(path.name):
                with path.open("rb") as file:
                    expected = load_json(path.with_suffix(".json"))
                    self.assertEqual(mtsv.load(file), expected)

    def test_generate(self):
        for path in paths("conforming", ".json"):
            with self.subTest(path.name):
                value = load_json(path)
                self.assertEqual(mtsv.loads(mtsv.dumps(value)), value)

    def test_dump_encodes_utf_8(self):
        for path in paths("conforming", ".json"):
            with self.subTest(path.name):
                value = load_json(path)
                buffer = io.BytesIO()
                mtsv.dump(value, buffer)
                expected = mtsv.dumps(value).encode("utf-8")
                self.assertEqual(buffer.getvalue(), expected)


class TestNonConforming(unittest.TestCase):
    """The specification allows parsers to accept these files.

    This implementation rejects them, following RFC 9413.
    """

    def test_parse_rejects(self):
        for path in paths("non-conforming", ".mtsv"):
            with self.subTest(path.name):
                with path.open("rb") as file:
                    with self.assertRaises(ValueError):
                        mtsv.load(file)


class TestCannotBeRepresented(unittest.TestCase):
    def test_generate_rejects(self):
        for path in paths("cannot-be-represented", ".json"):
            with self.subTest(path.name):
                with self.assertRaises(ValueError):
                    mtsv.dumps(load_json(path))
