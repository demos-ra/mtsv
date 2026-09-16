"""Test the mtsv interface: argument types and pickling of errors."""

import io
import pickle
import unittest

import mtsv


class TestLoad(unittest.TestCase):
    """load and loads, which follow tomllib."""

    def test_text_mode_file(self):
        """load raises TypeError for a file opened in text mode."""
        with self.assertRaises(TypeError):
            mtsv.load(io.StringIO("a\n"))

    def test_loads_bytes(self):
        """loads raises TypeError for bytes."""
        with self.assertRaises(TypeError):
            mtsv.loads(b"a\n")

    def test_positional_only(self):
        """load and loads take their argument by position only."""
        with self.assertRaises(TypeError):
            mtsv.loads(s="a\n")
        with self.assertRaises(TypeError):
            mtsv.load(fp=io.BytesIO(b"a\n"))


class TestMTSVDecodeError(unittest.TestCase):
    """MTSVDecodeError, which follows json.JSONDecodeError."""

    def test_pickle(self):
        """The error survives pickling with its properties."""
        with self.assertRaises(mtsv.MTSVDecodeError) as caught:
            mtsv.loads("a")
        error = caught.exception
        copy = pickle.loads(pickle.dumps(error))
        self.assertEqual(
            (copy.msg, copy.doc, copy.pos, copy.lineno, copy.colno),
            (error.msg, error.doc, error.pos, error.lineno, error.colno),
        )
