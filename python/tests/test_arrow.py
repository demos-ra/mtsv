"""Test mtsv.integrations.arrow: the door out to Arrow and the door back in."""

import unittest

from support import CONFORMANCE, load_json, paths

try:
    import pyarrow as pa

    from mtsv.integrations import arrow
except ImportError:
    pa = arrow = None

HTAB = chr(0x09)


@unittest.skipUnless(pa, "requires pyarrow")
class TestToArrow(unittest.TestCase):
    def test_round_trip(self):
        for path in paths("conforming", ".json"):
            with self.subTest(path.name):
                value = load_json(path)
                result = arrow.from_arrow(arrow.to_arrow(value))
                self.assertEqual(result, value)

    def test_cannot_be_represented(self):
        for path in paths("cannot-be-represented", ".json"):
            with self.subTest(path.name):
                with self.assertRaises(ValueError):
                    arrow.to_arrow(load_json(path))

    def test_tables(self):
        value = load_json(CONFORMANCE / "conforming" / "multiple-sheets.json")
        pairs = arrow.to_arrow(value)
        names = [name for name, table in pairs]
        self.assertEqual(names, ["People", "Animals"])
        for name, table in pairs:
            with self.subTest(name):
                self.assertEqual(
                    table.column_names, ["Name", "Age", "Address"]
                )
                for field in table.schema:
                    self.assertEqual(field.type, pa.string())


@unittest.skipUnless(pa, "requires pyarrow")
class TestFromArrow(unittest.TestCase):
    def test_extras_need_confirmation(self):
        table = pa.table(
            {"Age": pa.array([23, 45]), "Name": pa.array(["Paul", None])}
        )
        with self.assertRaises(ValueError):
            arrow.from_arrow([("People", table)])
        self.assertEqual(
            arrow.from_arrow([("People", table)], errors="ignore"),
            [
                {
                    "sheet name": "People",
                    "header": ["Age", "Name"],
                    "records": [["23", "Paul"], ["45", ""]],
                }
            ],
        )

    def test_metadata_needs_confirmation(self):
        column = pa.field("a", pa.string(), metadata={"k": "v"})
        tables = {
            "table metadata": pa.table(
                {"a": pa.array(["x"])}
            ).replace_schema_metadata({"k": "v"}),
            "column metadata": pa.table(
                {"a": pa.array(["x"])}, schema=pa.schema([column])
            ),
        }
        expected = [{"sheet name": "S", "header": ["a"], "records": [["x"]]}]
        for label, table in tables.items():
            with self.subTest(label):
                with self.assertRaises(ValueError):
                    arrow.from_arrow([("S", table)])
                self.assertEqual(
                    arrow.from_arrow([("S", table)], errors="ignore"),
                    expected,
                )

    def test_rows_without_columns_need_confirmation(self):
        table = pa.table({"a": pa.array(["x", "y"])}).drop_columns(["a"])
        with self.assertRaises(ValueError):
            arrow.from_arrow([("S", table)])
        self.assertEqual(
            arrow.from_arrow([("S", table)], errors="ignore"),
            [{"sheet name": "S", "header": None, "records": []}],
        )

    def test_all_string_types_are_text(self):
        expected = [{"sheet name": "S", "header": ["a"], "records": [["x"]]}]
        for data_type in (pa.string(), pa.large_string(), pa.string_view()):
            with self.subTest(str(data_type)):
                table = pa.table({"a": pa.array(["x"], data_type)})
                self.assertEqual(arrow.from_arrow([("S", table)]), expected)

    def test_duplicate_and_empty_column_names(self):
        columns = [pa.array(["1"]), pa.array(["2"]), pa.array(["3"])]
        table = pa.Table.from_arrays(columns, names=["a", "a", ""])
        self.assertEqual(
            arrow.from_arrow([("S", table)]),
            [
                {
                    "sheet name": "S",
                    "header": ["a", "a", ""],
                    "records": [["1", "2", "3"]],
                }
            ],
        )

    def test_values_without_text_stop(self):
        table = pa.table({"a": pa.array([bytes([0xFF])], pa.binary())})
        for errors in ("strict", "ignore"):
            with self.subTest(errors=errors):
                with self.assertRaises(ValueError):
                    arrow.from_arrow([("S", table)], errors=errors)

    def test_tab_in_a_value_always_stops(self):
        table = pa.table({"a": pa.array(["a" + HTAB + "b"])})
        for errors in ("strict", "ignore"):
            with self.subTest(errors=errors):
                with self.assertRaises(ValueError):
                    arrow.from_arrow([("S", table)], errors=errors)

    def test_unnamed_sheet_after_the_first_stops(self):
        table = pa.table({"a": pa.array(["x"])})
        with self.assertRaises(ValueError):
            arrow.from_arrow([("S", table), (None, table)])

    def test_unknown_errors_value(self):
        with self.assertRaises(LookupError):
            arrow.from_arrow([], errors="replace")
