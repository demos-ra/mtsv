"""Test mtsv.integrations._sheet against the draft, Data Model."""

import unittest

from mtsv.integrations._sheet import from_lines


class TestFromLines(unittest.TestCase):
    """from_lines: a sheet from the lines of a table."""

    def test_no_lines(self):
        """No lines give an empty sheet."""
        self.assertEqual(
            from_lines("S", []),
            {"sheet name": "S", "header": None, "records": []},
        )

    def test_padded(self):
        """Each line is padded with empty fields to the widest line."""
        self.assertEqual(
            from_lines("S", [["a"], ["b", "c", "d"], []]),
            {
                "sheet name": "S",
                "header": ["a", "", ""],
                "records": [["b", "c", "d"], ["", "", ""]],
            },
        )

    def test_same_width(self):
        """Lines of one width are kept as they are."""
        self.assertEqual(
            from_lines("", [["a", "b"], ["c", "d"]]),
            {"sheet name": "", "header": ["a", "b"], "records": [["c", "d"]]},
        )
