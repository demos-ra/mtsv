"""Test mtsv.integrations._odf against ODF 1.3."""

import unittest
from xml.etree import ElementTree

from mtsv.integrations import _odf

from support import (
    COLUMN,
    NAMESPACES,
    SHEET_A,
    STRING,
    TRIMMED,
    XML_FORBIDDEN,
    cell,
    document_content,
    load_json,
    paths,
    row,
    table,
    wrap,
)


def one_cell(content="<text:p>a</text:p>", attributes=STRING):
    """Return a document of table S with one column and one cell."""
    return document_content(table(COLUMN + row(cell(content, attributes))))


def one_value(value):
    """Return the sheet a one-cell table of that value comes back as."""
    return [{"sheet name": "S", "header": [value], "records": []}]


def read(data):
    """Return the sheets and what is left behind in a document."""
    return _odf.read_body(ElementTree.fromstring(data))


LEFT_BEHIND = [
    (
        "office:automatic-styles",
        document_content(table(), document="<office:automatic-styles/>"),
        SHEET_A,
    ),
    (
        "table:structure-protected",
        document_content(table(), spreadsheet=" table:structure-protected='true'"),
        SHEET_A,
    ),
    (
        "table:style-name of a table",
        document_content(table(attributes=" table:name='S' table:style-name='ta1'")),
        SHEET_A,
    ),
    (
        "table:title",
        document_content(table("<table:title>t</table:title>" + COLUMN + row())),
        SHEET_A,
    ),
    (
        "table:style-name of a row",
        document_content(table(COLUMN + row(attributes=" table:style-name='ro1'"))),
        SHEET_A,
    ),
    (
        "table:table-header-rows",
        document_content(table(COLUMN + wrap("table:table-header-rows", row()))),
        SHEET_A,
    ),
    (
        "table:table-row-group",
        document_content(table(COLUMN + wrap("table:table-row-group", row()))),
        SHEET_A,
    ),
    (
        "text:soft-page-break",
        document_content(table(COLUMN + "<text:soft-page-break/>" + row())),
        SHEET_A,
    ),
    (
        "table:style-name of a column",
        document_content(table("<table:table-column table:style-name='co1'/>" + row())),
        SHEET_A,
    ),
    (
        "table:table-column-group",
        document_content(table(wrap("table:table-column-group", COLUMN) + row())),
        SHEET_A,
    ),
    (
        "table:covered-table-cell",
        document_content(table(COLUMN + row("<table:covered-table-cell/>" + cell()))),
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
        one_cell("<text:p>a</text:p>" + table(COLUMN + row(cell("", "")), "")),
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
        document_content(table() + table(attributes="")),
        [
            {"sheet name": "S", "header": ["a"], "records": []},
            {"sheet name": "", "header": ["a"], "records": []},
        ],
    ),
    (
        "empty table without table:name",
        document_content(table(COLUMN + row(cell("", "")), "")),
        [{"sheet name": "", "header": None, "records": []}],
    ),
    (
        "table:number-rows-repeated",
        document_content(
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
        document_content(table(COLUMN + wrap("table:table-rows", row()))),
        SHEET_A,
    ),
    (
        "trailing empty rows",
        document_content(
            table(COLUMN + row() + row(cell("", ""), " table:number-rows-repeated='3'"))
        ),
        SHEET_A,
    ),
    (
        "table:number-columns-repeated of a column",
        document_content(
            table("<table:table-column table:number-columns-repeated='3'/>" + row())
        ),
        SHEET_A,
    ),
    (
        "table:table-columns",
        document_content(table(wrap("table:table-columns", COLUMN) + row())),
        SHEET_A,
    ),
    (
        "table:number-columns-repeated of a cell",
        one_cell(attributes=STRING + " table:number-columns-repeated='2'"),
        [{"sheet name": "S", "header": ["a", "a"], "records": []}],
    ),
    (
        "trailing empty cells",
        document_content(
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
        document_content(table(COLUMN + row(cell("<text:p>&#xFEFF;a</text:p>")), "")),
        [{"sheet name": "", "header": [chr(0xFEFF) + "a"], "records": []}],
    ),
    (
        "office:value-type void",
        one_cell("", " office:value-type='void'"),
        [{"sheet name": "S", "header": None, "records": []}],
    ),
]

ALWAYS = [
    (
        "not office:spreadsheet",
        f"<office:document-content{NAMESPACES} office:version='1.3'>"
        "<office:body><office:text/></office:body>"
        "</office:document-content>",
    ),
    (
        "table:number-rows-repeated 0",
        document_content(
            table(COLUMN + row(attributes=" table:number-rows-repeated='0'"))
        ),
    ),
    (
        "table:number-columns-repeated 0",
        one_cell(attributes=STRING + " table:number-columns-repeated='0'"),
    ),
    ("text:c of -1", one_cell("<text:p>a<text:s text:c='-1'/>b</text:p>")),
]


class TestBody(unittest.TestCase):
    """Writing the tables of an ODF document."""

    def test_conforming_round_trip(self):
        """Each conforming file body writes, read_body reads back."""
        for path in paths("conforming", ".json"):
            name = path.stem
            if name in XML_FORBIDDEN:
                continue
            with self.subTest(path.name):
                value = load_json(path)
                sheets, left = read(
                    f"<office:document-content{NAMESPACES} office:version='1.3'>"
                    f"{_odf.body(value)}</office:document-content>"
                )
                self.assertEqual(left, set())
                self.assertEqual(sheets, TRIMMED.get(name, value))


class TestReadBody(unittest.TestCase):
    """Reading the tables of an ODF document."""

    def test_left_behind(self):
        """Each extra is read past and named as left behind."""
        for row_id, data, expected in LEFT_BEHIND:
            with self.subTest(row_id):
                sheets, left = read(data)
                self.assertTrue(left)
                self.assertEqual(sheets, expected)

    def test_mapped(self):
        """Each mapping is read with nothing left behind."""
        for row_id, data, expected in MAPPED:
            with self.subTest(row_id):
                sheets, left = read(data)
                self.assertEqual(left, set())
                self.assertEqual(sheets, expected)

    def test_always_refused(self):
        """Each invalid input is refused."""
        for row_id, data in ALWAYS:
            with self.subTest(row_id):
                with self.assertRaises(ValueError):
                    read(data)
