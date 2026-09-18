"""Test mtsv.integrations.ods against ODF 1.3."""

import io
import logging
import tempfile
import unittest
import zipfile
from pathlib import Path

from mtsv.integrations import ods

from support import CONFORMANCE, load_json, paths

MEDIA_TYPE = "application/vnd.oasis.opendocument.spreadsheet"
NAMESPACES = (
    " xmlns:office='urn:oasis:names:tc:opendocument:xmlns:office:1.0'"
    " xmlns:table='urn:oasis:names:tc:opendocument:xmlns:table:1.0'"
    " xmlns:text='urn:oasis:names:tc:opendocument:xmlns:text:1.0'"
)
MANIFEST = (
    "<manifest:manifest"
    " xmlns:manifest='urn:oasis:names:tc:opendocument:xmlns:manifest:1.0'"
    " manifest:version='1.3'>"
    "<manifest:file-entry manifest:full-path='/'"
    f" manifest:media-type='{MEDIA_TYPE}'/>"
    "<manifest:file-entry manifest:full-path='content.xml'"
    " manifest:media-type='text/xml'/>"
    "</manifest:manifest>"
)
COLUMN = "<table:table-column/>"
STRING = " office:value-type='string'"
SHEET_A = [{"sheet name": "S", "header": ["a"], "records": []}]
XML_FORBIDDEN = {
    "field-u0000",
    "field-u0008",
    "field-u000b",
    "field-u000e",
    "sheet-name-u0000",
    "sheet-name-u0008",
    "sheet-name-u000b",
    "sheet-name-u000e",
}
TRIMMED = {
    "empty-first-field": [
        {"sheet name": "", "header": None, "records": []},
    ],
    "empty-later-field": [
        {"sheet name": "", "header": ["a"], "records": []},
    ],
}


def cell(content="<text:p>a</text:p>", attributes=STRING):
    """Return a table:table-cell."""
    return f"<table:table-cell{attributes}>{content}</table:table-cell>"


def row(cells=None, attributes=""):
    """Return a table:table-row, by default holding cell a."""
    cells = cell() if cells is None else cells
    return f"<table:table-row{attributes}>{cells}</table:table-row>"


def table(inner=None, attributes=" table:name='S'"):
    """Return table:table S, by default with a column and row a."""
    inner = COLUMN + row() if inner is None else inner
    return f"<table:table{attributes}>{inner}</table:table>"


def wrap(tag, inner):
    """Return inner wrapped in the element tag."""
    return f"<{tag}>{inner}</{tag}>"


def archive(content=None, entries=()):
    """Return a package, as bytes, with content.xml if it is given."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as package_file:
        package_file.writestr(
            zipfile.ZipInfo("mimetype"), MEDIA_TYPE, zipfile.ZIP_STORED
        )
        package_file.writestr("META-INF/manifest.xml", MANIFEST)
        if content is not None:
            package_file.writestr("content.xml", content)
        for name in entries:
            package_file.writestr(name, "")
    return buffer.getvalue()


def package(tables="", document="", spreadsheet="", entries=()):
    """Return an .ods file, as bytes, whose spreadsheet holds tables."""
    return archive(
        f"<office:document-content{NAMESPACES} office:version='1.3'>"
        f"{document}<office:body><office:spreadsheet{spreadsheet}>"
        f"{tables}</office:spreadsheet></office:body>"
        "</office:document-content>",
        entries,
    )


def one_cell(content="<text:p>a</text:p>", attributes=STRING):
    """Return an .ods file of table S with one column and one cell."""
    return package(table(COLUMN + row(cell(content, attributes))))


def one_value(value):
    """Return the sheet a one-cell table of that value comes back as."""
    return [{"sheet name": "S", "header": [value], "records": []}]


def round_trip(value):
    """Dump value to ODS and load it back strictly."""
    buffer = io.BytesIO()
    ods.dump(value, buffer)
    buffer.seek(0)
    return ods.load(buffer)


LEFT_BEHIND = [
    ("styles.xml", package(table(), entries=["styles.xml"]), SHEET_A),
    (
        "office:automatic-styles",
        package(table(), document="<office:automatic-styles/>"),
        SHEET_A,
    ),
    (
        "table:structure-protected",
        package(table(), spreadsheet=" table:structure-protected='true'"),
        SHEET_A,
    ),
    (
        "table:style-name of a table",
        package(table(attributes=" table:name='S' table:style-name='ta1'")),
        SHEET_A,
    ),
    (
        "table:title",
        package(table("<table:title>t</table:title>" + COLUMN + row())),
        SHEET_A,
    ),
    (
        "table:style-name of a row",
        package(table(COLUMN + row(attributes=" table:style-name='ro1'"))),
        SHEET_A,
    ),
    (
        "table:table-header-rows",
        package(table(COLUMN + wrap("table:table-header-rows", row()))),
        SHEET_A,
    ),
    (
        "table:table-row-group",
        package(table(COLUMN + wrap("table:table-row-group", row()))),
        SHEET_A,
    ),
    (
        "text:soft-page-break",
        package(table(COLUMN + "<text:soft-page-break/>" + row())),
        SHEET_A,
    ),
    (
        "table:style-name of a column",
        package(
            table("<table:table-column table:style-name='co1'/>" + row())
        ),
        SHEET_A,
    ),
    (
        "table:table-column-group",
        package(table(wrap("table:table-column-group", COLUMN) + row())),
        SHEET_A,
    ),
    (
        "table:covered-table-cell",
        package(table(COLUMN + row("<table:covered-table-cell/>" + cell()))),
        [{"sheet name": "S", "header": ["", "a"], "records": []}],
    ),
    (
        "table:number-columns-spanned",
        one_cell(attributes=STRING + " table:number-columns-spanned='1'"),
        SHEET_A,
    ),
    (
        "office:string-value",
        one_cell(attributes=STRING + " office:string-value='b'"),
        one_value("b"),
    ),
    (
        "office:value-type float",
        one_cell(
            "<text:p>3</text:p>",
            " office:value-type='float' office:value='3'",
        ),
        one_value("3"),
    ),
    ("text:h", one_cell("<text:h>a</text:h>"), SHEET_A),
    (
        "table:table in a cell",
        one_cell(
            "<text:p>a</text:p>" + table(COLUMN + row(cell("", "")), "")
        ),
        SHEET_A,
    ),
    (
        "text:style-name of a paragraph",
        one_cell("<text:p text:style-name='P1'>a</text:p>"),
        SHEET_A,
    ),
    (
        "text:span",
        one_cell("<text:p><text:span>a</text:span></text:p>"),
        SHEET_A,
    ),
    (
        "text:ruby",
        one_cell(
            "<text:p><text:ruby><text:ruby-base>a</text:ruby-base>"
            "<text:ruby-text>x</text:ruby-text></text:ruby></text:p>"
        ),
        SHEET_A,
    ),
    (
        "text:bookmark",
        one_cell("<text:p>a<text:bookmark text:name='m'/></text:p>"),
        SHEET_A,
    ),
    (
        "office:value-type float, displayed formatted",
        one_cell(
            "<text:p>2,500</text:p>",
            " office:value-type='float' office:value='2500'",
        ),
        one_value("2500"),
    ),
    (
        "office:value-type date",
        one_cell(
            "<text:p>Jan-23</text:p>",
            " office:value-type='date' office:date-value='2023-01-15'",
        ),
        one_value("2023-01-15"),
    ),
    (
        "office:value-type time",
        one_cell(
            "<text:p>12:30 PM</text:p>",
            " office:value-type='time' office:time-value='PT12H30M00S'",
        ),
        one_value("PT12H30M00S"),
    ),
    (
        "office:value-type boolean",
        one_cell(
            "<text:p>TRUE</text:p>",
            " office:value-type='boolean' office:boolean-value='true'",
        ),
        one_value("true"),
    ),
    (
        "office:value-type percentage",
        one_cell(
            "<text:p>25%</text:p>",
            " office:value-type='percentage' office:value='0.25'",
        ),
        one_value("0.25"),
    ),
    (
        "office:value-type currency",
        one_cell(
            "<text:p>$550,000</text:p>",
            " office:value-type='currency' office:value='550000'"
            " office:currency='USD'",
        ),
        one_value("550000"),
    ),
]

MAPPED = [
    (
        "empty cell",
        one_cell("", ""),
        [{"sheet name": "S", "header": None, "records": []}],
    ),
    (
        "later table without table:name",
        package(table() + table(attributes="")),
        [
            {"sheet name": "S", "header": ["a"], "records": []},
            {"sheet name": "", "header": ["a"], "records": []},
        ],
    ),
    (
        "empty table without table:name",
        package(table(COLUMN + row(cell("", "")), "")),
        [{"sheet name": "", "header": None, "records": []}],
    ),
    (
        "table:number-rows-repeated",
        package(
            table(
                COLUMN
                + row()
                + row(
                    cell("<text:p>b</text:p>"),
                    " table:number-rows-repeated='2'",
                )
            )
        ),
        [{"sheet name": "S", "header": ["a"], "records": [["b"], ["b"]]}],
    ),
    (
        "table:table-rows",
        package(table(COLUMN + wrap("table:table-rows", row()))),
        SHEET_A,
    ),
    (
        "trailing empty rows",
        package(
            table(
                COLUMN
                + row()
                + row(cell("", ""), " table:number-rows-repeated='3'")
            )
        ),
        SHEET_A,
    ),
    (
        "table:number-columns-repeated of a column",
        package(
            table(
                "<table:table-column table:number-columns-repeated='3'/>"
                + row()
            )
        ),
        SHEET_A,
    ),
    (
        "table:table-columns",
        package(table(wrap("table:table-columns", COLUMN) + row())),
        SHEET_A,
    ),
    (
        "table:number-columns-repeated of a cell",
        one_cell(attributes=STRING + " table:number-columns-repeated='2'"),
        [{"sheet name": "S", "header": ["a", "a"], "records": []}],
    ),
    (
        "trailing empty cells",
        package(
            table(
                COLUMN
                + row(cell() + cell("<text:p>c</text:p>"))
                + row(
                    cell("<text:p>b</text:p>")
                    + cell("", " table:number-columns-repeated='3'")
                )
            )
        ),
        [
            {
                "sheet name": "S",
                "header": ["a", "c"],
                "records": [["b", ""]],
            }
        ],
    ),
    ("cell without office:value-type", one_cell(attributes=""), SHEET_A),
    (
        "white space collapsed",
        one_cell("<text:p>  a <text:s/> b  </text:p>"),
        one_value("a   b"),
    ),
    (
        "text:s with text:c",
        one_cell("<text:p>a<text:s text:c='2'/>b</text:p>"),
        one_value("a  b"),
    ),
    (
        "U+FEFF in a field",
        package(table(COLUMN + row(cell("<text:p>&#xFEFF;a</text:p>")), "")),
        [{"sheet name": "", "header": [chr(0xFEFF) + "a"], "records": []}],
    ),
    (
        "office:value-type void",
        one_cell("", " office:value-type='void'"),
        [{"sheet name": "S", "header": None, "records": []}],
    ),
]

ALWAYS = [
    ("not a ZIP file", b"not a zip"),
    ("no content.xml", archive()),
    (
        "not office:document-content",
        archive(
            f"<office:document-styles{NAMESPACES} office:version='1.3'/>"
        ),
    ),
    (
        "not office:spreadsheet",
        archive(
            f"<office:document-content{NAMESPACES} office:version='1.3'>"
            "<office:body><office:text/></office:body>"
            "</office:document-content>"
        ),
    ),
    (
        "table:number-rows-repeated 0",
        package(
            table(COLUMN + row(attributes=" table:number-rows-repeated='0'"))
        ),
    ),
    (
        "table:number-columns-repeated 0",
        one_cell(attributes=STRING + " table:number-columns-repeated='0'"),
    ),
    ("two paragraphs", one_cell("<text:p>a</text:p><text:p>b</text:p>")),
    ("text:c of -1", one_cell("<text:p>a<text:s text:c='-1'/>b</text:p>")),
    ("text:tab", one_cell("<text:p>a<text:tab/>b</text:p>")),
    ("text:line-break", one_cell("<text:p>a<text:line-break/>b</text:p>")),
    ("tab in table:name", package(table(attributes=" table:name='S&#9;S'"))),
]


class TestDump(unittest.TestCase):
    """Writing ODS."""

    def test_conforming_round_trip(self):
        """Each conforming file survives dump then strict load."""
        for path in paths("conforming", ".json"):
            with self.subTest(path.name):
                value = load_json(path)
                name = path.stem
                if name in XML_FORBIDDEN:
                    with self.assertRaises(ValueError):
                        ods.dump(value, io.BytesIO())
                else:
                    expected = TRIMMED.get(name, value)
                    self.assertEqual(round_trip(value), expected)

    def test_cannot_be_represented(self):
        """Each file that MTSV cannot hold is refused by dump."""
        for path in paths("cannot-be-represented", ".json"):
            with self.subTest(path.name):
                with self.assertRaises(ValueError):
                    ods.dump(load_json(path), io.BytesIO())

    def test_package(self):
        """The package holds mimetype first, then two files."""
        buffer = io.BytesIO()
        value = load_json(CONFORMANCE / "conforming" / "multiple-sheets.json")
        ods.dump(value, buffer)
        with zipfile.ZipFile(buffer) as archive_file:
            first = archive_file.infolist()[0]
            self.assertEqual(first.filename, "mimetype")
            self.assertEqual(first.compress_type, zipfile.ZIP_STORED)
            self.assertEqual(
                archive_file.read("mimetype"), MEDIA_TYPE.encode("ascii")
            )
            self.assertEqual(
                archive_file.namelist(),
                ["mimetype", "META-INF/manifest.xml", "content.xml"],
            )


class TestLoad(unittest.TestCase):
    """Reading ODS."""

    def test_left_behind(self):
        """Strict refuses each extra; ignore leaves it behind."""
        for row_id, data, expected in LEFT_BEHIND:
            with self.subTest(row_id):
                with self.assertRaises(ValueError):
                    ods.load(io.BytesIO(data))
                result = ods.load(io.BytesIO(data), errors="ignore")
                self.assertEqual(result, expected)

    def test_mapped(self):
        """Each mapping is read the same in both doors."""
        for row_id, data, expected in MAPPED:
            for errors in ("strict", "ignore"):
                with self.subTest(row_id, errors=errors):
                    result = ods.load(io.BytesIO(data), errors=errors)
                    self.assertEqual(result, expected)

    def test_always_refused(self):
        """Each invalid input is refused in both doors."""
        for row_id, data in ALWAYS:
            for errors in ("strict", "ignore"):
                with self.subTest(row_id, errors=errors):
                    with self.assertRaises(ValueError):
                        ods.load(io.BytesIO(data), errors=errors)

    def test_unknown_errors_value(self):
        """An unknown errors value raises LookupError."""
        with self.assertRaises(LookupError):
            ods.load(io.BytesIO(package(table())), errors="replace")


class TestMain(unittest.TestCase):
    """The command line: python -m mtsv.integrations.ods."""

    def test_converts_both_ways(self):
        """.mtsv to .ods and back gives the same bytes."""
        original = CONFORMANCE / "conforming" / "multiple-sheets.mtsv"
        with tempfile.TemporaryDirectory() as directory:
            spreadsheet = Path(directory, "multiple-sheets.ods")
            back = Path(directory, "multiple-sheets.mtsv")
            ods.main([str(original), str(spreadsheet)])
            ods.main([str(spreadsheet), str(back)])
            self.assertEqual(back.read_bytes(), original.read_bytes())

    def test_extras_are_reported_not_refused(self):
        """Extras are noted, and --errors strict refuses them."""
        data = package(
            table(attributes=" table:name='S' table:style-name='ta1'")
        )
        expected = bytes([0x0C]) + b"S" + bytes([0x0A]) + b"a" + bytes([0x0A])
        with tempfile.TemporaryDirectory() as directory:
            spreadsheet = Path(directory, "styled.ods")
            result = Path(directory, "styled.mtsv")
            spreadsheet.write_bytes(data)
            with self.assertLogs("mtsv.integrations", logging.WARNING) as logs:
                ods.main([str(spreadsheet), str(result)])
            self.assertEqual(result.read_bytes(), expected)
            record, = logs.records
            self.assertEqual(record.left_behind, ["table:style-name"])
            with self.assertRaises(SystemExit):
                ods.main([str(spreadsheet), str(result), "--errors", "strict"])
