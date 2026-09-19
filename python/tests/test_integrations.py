"""Test mtsv.integrations: formats by extension."""

import io
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
        """An extension that names no format raises LookupError."""
        with self.assertRaises(LookupError):
            mtsv.integrations.dump(".txt", SHEETS, io.BytesIO())
        with self.assertRaises(LookupError):
            mtsv.integrations.load(".txt", io.BytesIO(b"a\n"))
