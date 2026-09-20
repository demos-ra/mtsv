"""Test mtsv.integrations.arrow against the Arrow Columnar Format."""

import datetime
import logging
import unittest

try:
    import pyarrow as pa

    from mtsv.integrations import arrow
except ImportError:
    pa = arrow = None

from support import load_json, paths

# Cases outside MTSV that an Arrow table cannot hold in the first place.
ARROW_CANNOT_HOLD = {
    "fewer-fields": "columns of a table have one length",
    "more-fields": "columns of a table have one length",
    "header-without-fields": "a table without columns is the empty sheet",
}

# Cases outside MTSV that a table holds, and that come back left behind.
ARROW_LEAVES_BEHIND = {
    "records-without-header": "rows of a table without columns",
}


def scalar_types():
    """Types whose slots hold one scalar."""
    return {
        "null": pa.null(),
        "boolean": pa.bool_(),
        "int": pa.int64(),
        "floating point": pa.float64(),
        "decimal": pa.decimal128(5, 2),
        "date": pa.date32(),
        "time": pa.time64("us"),
        "timestamp": pa.timestamp("s"),
        "interval": pa.month_day_nano_interval(),
        "duration": pa.duration("s"),
    }


def types_without_text():
    """The types whose slots hold bytes, or values of child types."""
    return {
        "fixed-size binary": pa.binary(2),
        "binary": pa.binary(),
        "large binary": pa.large_binary(),
        "binary view": pa.binary_view(),
        "fixed-size list": pa.list_(pa.string(), 2),
        "list": pa.list_(pa.string()),
        "large list": pa.large_list(pa.string()),
        "list view": pa.list_view(pa.string()),
        "large list view": pa.large_list_view(pa.string()),
        "struct": pa.struct([("x", pa.string())]),
        "map": pa.map_(pa.string(), pa.string()),
        "union": pa.dense_union([pa.field("x", pa.string())]),
    }


def as_table(header, records):
    """Build a table of text columns, one per header field."""
    if header is None:
        return pa.Table.from_arrays([], names=[])
    columns = [
        pa.array([record[index] for record in records], pa.string())
        for index in range(len(header))
    ]
    return pa.Table.from_arrays(columns, names=header)


def as_pairs(value):
    """Build (sheet name, table) pairs from sheets, without to_arrow."""
    return [
        (sheet["sheet name"], as_table(sheet["header"], sheet["records"]))
        for sheet in value
    ]


def column(values, data_type=None, metadata=None):
    """Build a table of one column called a."""
    field = pa.field("a", data_type or pa.string(), metadata=metadata)
    return pa.Table.from_arrays(
        [pa.array(values, field.type)], schema=pa.schema([field])
    )


def empty_column(data_type):
    """Build a table of one column of the given type, without rows.

    A union column holds one row.
    """
    if pa.types.is_union(data_type):
        values = pa.UnionArray.from_dense(
            pa.array([0], pa.int8()),
            pa.array([0], pa.int32()),
            [pa.array(["x"])],
        )
        return pa.Table.from_arrays([values], names=["a"])
    return pa.schema([pa.field("a", data_type)]).empty_table()


def one_cell(value):
    """The sheet that a one-column, one-row table comes back as."""
    return [{"sheet name": "S", "header": ["a"], "records": [[value]]}]


@unittest.skipUnless(pa, "requires pyarrow")
class TestToArrow(unittest.TestCase):
    """The door out: MTSV sheets to Arrow tables."""

    def test_round_trip(self):
        """Every conforming case comes back unchanged."""
        for path in paths("conforming", ".json"):
            with self.subTest(path.name):
                value = load_json(path)
                result = arrow.from_arrow(arrow.to_arrow(value))
                self.assertEqual(result, value)

    def test_cannot_be_represented(self):
        """No case outside MTSV reaches Arrow."""
        for path in paths("cannot-be-represented", ".json"):
            with self.subTest(path.name):
                with self.assertRaises(ValueError):
                    arrow.to_arrow(load_json(path))

    def test_sheet_names(self):
        """Each sheet gives one pair, under its own name, in order."""
        for path in paths("conforming", ".json"):
            with self.subTest(path.name):
                value = load_json(path)
                self.assertEqual(
                    [name for name, table in arrow.to_arrow(value)],
                    [sheet["sheet name"] for sheet in value],
                )

    def test_column_names(self):
        """Header fields become field names, in order."""
        for path in paths("conforming", ".json"):
            with self.subTest(path.name):
                value = load_json(path)
                for sheet, (name, table) in zip(value, arrow.to_arrow(value)):
                    self.assertEqual(table.column_names, sheet["header"] or [])

    def test_columns_are_text(self):
        """Every column has the Utf8 type."""
        for path in paths("conforming", ".json"):
            with self.subTest(path.name):
                for name, table in arrow.to_arrow(load_json(path)):
                    for field in table.schema:
                        self.assertEqual(field.type, pa.string())

    def test_row_count(self):
        """A table holds one row per record."""
        for path in paths("conforming", ".json"):
            with self.subTest(path.name):
                value = load_json(path)
                for sheet, (name, table) in zip(value, arrow.to_arrow(value)):
                    self.assertEqual(table.num_rows, len(sheet["records"]))

    def test_empty_sheet_has_no_columns(self):
        """An empty sheet gives a table without columns."""
        value = [{"sheet name": "S", "header": None, "records": []}]
        ((name, table),) = arrow.to_arrow(value)
        self.assertEqual((table.num_columns, table.num_rows), (0, 0))


@unittest.skipUnless(pa, "requires pyarrow")
class TestFromArrow(unittest.TestCase):
    """The door in: Arrow tables to MTSV sheets."""

    def test_cannot_be_represented(self):
        """A table holding a case outside MTSV is always refused."""
        for path in paths("cannot-be-represented", ".json"):
            with self.subTest(path.name):
                if path.stem in ARROW_CANNOT_HOLD:
                    self.skipTest(ARROW_CANNOT_HOLD[path.stem])
                if path.stem in ARROW_LEAVES_BEHIND:
                    self.skipTest(ARROW_LEAVES_BEHIND[path.stem])
                pairs = as_pairs(load_json(path))
                for errors in ("strict", "ignore"):
                    with self.subTest(errors=errors):
                        with self.assertRaises(ValueError):
                            arrow.from_arrow(pairs, errors=errors)

    def test_empty_name(self):
        """An empty name gives a sheet whose sheet name is empty."""
        self.assertEqual(
            arrow.from_arrow([("", column(["x"]))]),
            [{"sheet name": "", "header": ["a"], "records": [["x"]]}],
        )

    def test_name_is_text(self):
        """A pair named None is refused."""
        with self.assertRaises(ValueError):
            arrow.from_arrow([(None, column(["x"]))])

    def test_table_without_columns(self):
        """A table without columns gives an empty sheet."""
        self.assertEqual(
            arrow.from_arrow([("S", pa.Table.from_arrays([], names=[]))]),
            [{"sheet name": "S", "header": None, "records": []}],
        )

    def test_rows_without_columns_need_confirmation(self):
        """Rows of a table without columns are left behind."""
        table = pa.table({"a": pa.array(["x", "y"])}).drop_columns(["a"])
        with self.assertRaises(ValueError):
            arrow.from_arrow([("S", table)])
        self.assertEqual(
            arrow.from_arrow([("S", table)], errors="ignore"),
            [{"sheet name": "S", "header": None, "records": []}],
        )

    def test_table_metadata_needs_confirmation(self):
        """Metadata of a schema is left behind."""
        table = column(["x"]).replace_schema_metadata({"k": "v"})
        with self.assertRaises(ValueError):
            arrow.from_arrow([("S", table)])
        with self.assertLogs("mtsv.integrations", logging.WARNING) as logs:
            result = arrow.from_arrow([("S", table)], errors="ignore")
        self.assertEqual(result, one_cell("x"))
        (record,) = logs.records
        names = record.left_behind
        self.assertTrue(names)
        self.assertEqual(names, sorted(names))
        self.assertEqual(record.getMessage(), "left behind: " + ", ".join(names))

    def test_column_metadata_needs_confirmation(self):
        """Metadata of a field is left behind."""
        table = column(["x"], metadata={"k": "v"})
        with self.assertRaises(ValueError):
            arrow.from_arrow([("S", table)])
        self.assertEqual(
            arrow.from_arrow([("S", table)], errors="ignore"), one_cell("x")
        )

    def test_extension_type_needs_confirmation(self):
        """An extension type is left behind."""
        table = column(["x"], metadata={"ARROW:extension:name": "uuid"})
        with self.assertRaises(ValueError):
            arrow.from_arrow([("S", table)])
        self.assertEqual(
            arrow.from_arrow([("S", table)], errors="ignore"), one_cell("x")
        )

    def test_duplicate_and_empty_column_names(self):
        """Field names repeat and may be empty, as header fields do."""
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

    def test_nullable_is_not_left_behind(self):
        """A nullable field describes the field, not a value."""
        field = pa.field("a", pa.string(), nullable=True)
        table = pa.Table.from_arrays([pa.array(["x"])], schema=pa.schema([field]))
        self.assertEqual(arrow.from_arrow([("S", table)]), one_cell("x"))

    def test_text_types_are_text(self):
        """Utf8, Large Utf8 and Utf8 View all come back as text."""
        for data_type in (pa.string(), pa.large_string(), pa.string_view()):
            with self.subTest(str(data_type)):
                table = column(["x"], data_type)
                self.assertEqual(arrow.from_arrow([("S", table)]), one_cell("x"))

    def test_encodings_are_transparent(self):
        """A dictionary or run-end encoding of text holds text."""
        dictionary = pa.array(["x"]).dictionary_encode()
        run_end = pa.RunEndEncodedArray.from_arrays(
            pa.array([1], pa.int32()), pa.array(["x"])
        )
        for label, values in (
            ("dictionary", dictionary),
            ("run-end encoded", run_end),
        ):
            with self.subTest(label):
                table = pa.Table.from_arrays([values], names=["a"])
                self.assertEqual(arrow.from_arrow([("S", table)]), one_cell("x"))

    def test_ordering_needs_confirmation(self):
        """The orderedness of a dictionary is left behind."""
        values = pa.DictionaryArray.from_arrays(
            pa.array([0], pa.int32()), pa.array(["x"]), ordered=True
        )
        table = pa.Table.from_arrays([values], names=["a"])
        with self.assertRaises(ValueError):
            arrow.from_arrow([("S", table)])
        self.assertEqual(
            arrow.from_arrow([("S", table)], errors="ignore"), one_cell("x")
        )

    def test_encoding_follows_its_value_type(self):
        """An encoding of a scalar type is left behind as that type."""
        values = pa.array([23], pa.int64()).dictionary_encode()
        table = pa.Table.from_arrays([values], names=["a"])
        with self.assertRaises(ValueError):
            arrow.from_arrow([("S", table)])
        self.assertEqual(
            arrow.from_arrow([("S", table)], errors="ignore"), one_cell("23")
        )

    def test_scalar_types_need_confirmation(self):
        """A type with a text form is left behind, not refused."""
        empty = [{"sheet name": "S", "header": ["a"], "records": []}]
        for label, data_type in scalar_types().items():
            with self.subTest(label):
                table = empty_column(data_type)
                with self.assertRaises(ValueError):
                    arrow.from_arrow([("S", table)])
                self.assertEqual(
                    arrow.from_arrow([("S", table)], errors="ignore"), empty
                )

    def test_text_form(self):
        """A value keeps its text; a missing one comes back empty."""
        table = column([23, None], pa.int64())
        self.assertEqual(
            arrow.from_arrow([("S", table)], errors="ignore"),
            [
                {
                    "sheet name": "S",
                    "header": ["a"],
                    "records": [["23"], [""]],
                }
            ],
        )

    def test_text_form_of_a_duration(self):
        """A type Arrow may not cast still comes back as text."""
        table = column([datetime.timedelta(seconds=1)], pa.duration("s"))
        (sheet,) = arrow.from_arrow([("S", table)], errors="ignore")
        value = sheet["records"][0][0]
        self.assertIsInstance(value, str)
        self.assertTrue(value)

    def test_types_without_text_stop(self):
        """A type with no text form is refused, whatever the setting."""
        for label, data_type in types_without_text().items():
            with self.subTest(label):
                table = empty_column(data_type)
                for errors in ("strict", "ignore"):
                    with self.subTest(errors=errors):
                        with self.assertRaises(ValueError):
                            arrow.from_arrow([("S", table)], errors=errors)

    def test_missing_values_need_confirmation(self):
        """A missing value is left behind, and comes back empty."""
        table = column(["x", None])
        with self.assertRaises(ValueError):
            arrow.from_arrow([("S", table)])
        self.assertEqual(
            arrow.from_arrow([("S", table)], errors="ignore"),
            [
                {
                    "sheet name": "S",
                    "header": ["a"],
                    "records": [["x"], [""]],
                }
            ],
        )

    def test_unknown_errors_value(self):
        """An errors name that is neither strict nor ignore stops."""
        with self.assertRaises(LookupError):
            arrow.from_arrow([], errors="replace")
