"""Test mtsv.__main__: the entry point of the mtsv command."""

import unittest
from unittest import mock

from mtsv import __main__


class TestMain(unittest.TestCase):
    """main: the mtsv command."""

    def test_passes_the_arguments(self):
        """main hands its arguments to the command."""
        with mock.patch("mtsv._command.run") as run:
            __main__.main(["a.xlsx"])
        run.assert_called_once_with(["a.xlsx"])
