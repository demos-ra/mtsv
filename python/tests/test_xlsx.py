"""Test mtsv.integrations.xlsx against ECMA-376."""

import io
import unittest
import zipfile

from mtsv.integrations import xlsx

from support import CONFORMANCE, load_json, paths

MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CONTENT_TYPES = "http://schemas.openxmlformats.org/package/2006/content-types"
RELATIONSHIPS = "http://schemas.openxmlformats.org/package/2006/relationships"
RELATIONSHIP_TYPE = "application/vnd.openxmlformats-package.relationships+xml"
WORKBOOK_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"
)
WORKSHEET_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"
)
OFFICE_DOCUMENT_REL = R + "/officeDocument"
WORKSHEET_REL = R + "/worksheet"
SHARED_STRINGS_REL = R + "/sharedStrings"
MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"

SHEET_A = [{"sheet name": "S", "header": ["a"], "records": []}]
FORBIDDEN = (chr(0x00), chr(0x08), chr(0x0B), chr(0x0E))
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


def content_types(count):
    """Return [Content_Types].xml for a workbook of that many sheets."""
    overrides = "".join(
        f"<Override PartName='/xl/worksheets/sheet{index}.xml'"
        f" ContentType='{WORKSHEET_TYPE}'/>"
        for index in range(1, count + 1)
    )
    return (
        f"<Types xmlns='{CONTENT_TYPES}'>"
        f"<Default Extension='rels' ContentType='{RELATIONSHIP_TYPE}'/>"
        f"<Override PartName='/xl/workbook.xml'"
        f" ContentType='{WORKBOOK_TYPE}'/>"
        f"{overrides}</Types>"
    )


def root_relationships():
    """Return _rels/.rels, which names the workbook part."""
    return (
        f"<Relationships xmlns='{RELATIONSHIPS}'>"
        f"<Relationship Id='rId1' Type='{OFFICE_DOCUMENT_REL}'"
        " Target='xl/workbook.xml'/></Relationships>"
    )


def workbook_relationships(count, table=False, prefix=""):
    """Return xl/_rels/workbook.xml.rels for that many worksheets."""
    entries = "".join(
        f"<Relationship Id='rId{index}' Type='{WORKSHEET_REL}'"
        f" Target='{prefix}worksheets/sheet{index}.xml'/>"
        for index in range(1, count + 1)
    )
    if table:
        entries += (
            f"<Relationship Id='rId{count + 1}' Type='{SHARED_STRINGS_REL}'"
            " Target='sharedStrings.xml'/>"
        )
    return f"<Relationships xmlns='{RELATIONSHIPS}'>{entries}</Relationships>"


def sheet(name="S", index=1, attributes=""):
    """Return one sheet entry of a workbook."""
    return f"<sheet name='{name}' sheetId='{index}' r:id='rId{index}'{attributes}/>"


def workbook(entries=None, children=""):
    """Return xl/workbook.xml holding the given sheet entries."""
    entries = sheet() if entries is None else entries
    return (
        f"<workbook xmlns='{MAIN}' xmlns:r='{R}'>{children}"
        f"<sheets>{entries}</sheets></workbook>"
    )


def worksheet(rows="", children="", attributes=""):
    """Return a worksheet part holding the given rows."""
    return (
        f"<worksheet xmlns='{MAIN}'{attributes}>{children}"
        f"<sheetData>{rows}</sheetData></worksheet>"
    )


def row(cells=None, number=1, attributes=""):
    """Return a row, by default holding cell a at A1."""
    cells = cell() if cells is None else cells
    return f"<row r='{number}'{attributes}>{cells}</row>"


def cell(content="<is><t>a</t></is>", reference="A1", attributes=None):
    """Return a cell, by default carrying the inline text a."""
    if attributes is None:
        attributes = " t='inlineStr'"
    return f"<c r='{reference}'{attributes}>{content}</c>"


def strings(items):
    """Return xl/sharedStrings.xml holding the given si elements."""
    return f"<sst xmlns='{MAIN}'>{items}</sst>"


def package(sheets=None, entries=None, children="", table=None, extra=(), prefix=""):
    """Return an .xlsx file, as bytes, holding the given parts."""
    sheets = [worksheet(row())] if sheets is None else sheets
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as file:
        file.writestr("[Content_Types].xml", content_types(len(sheets)))
        file.writestr("_rels/.rels", root_relationships())
        file.writestr("xl/workbook.xml", workbook(entries, children))
        file.writestr(
            "xl/_rels/workbook.xml.rels",
            workbook_relationships(len(sheets), table is not None, prefix),
        )
        for index, part in enumerate(sheets, 1):
            file.writestr(f"xl/worksheets/sheet{index}.xml", part)
        if table is not None:
            file.writestr("xl/sharedStrings.xml", table)
        for name in extra:
            file.writestr(name, "")
    return buffer.getvalue()


def one_value(value):
    """Return the sheet a one-cell worksheet comes back as."""
    return [{"sheet name": "S", "header": [value], "records": []}]


def round_trip(value):
    """Dump value to XLSX and load it back strictly."""
    buffer = io.BytesIO()
    xlsx.dump(value, buffer)
    buffer.seek(0)
    return xlsx.load(buffer)


def refused(value):
    """Return whether XLSX cannot hold these sheets.

    No sheets, or a sheet name given twice.
    """
    names = [sheet["sheet name"] for sheet in value]
    return not value or len(set(names)) != len(names)


LEFT_BEHIND = [
    (
        "calcPr",
        package(entries=sheet(), children="<calcPr calcId='1'/>"),
        SHEET_A,
    ),
    (
        "state of a sheet",
        package(entries=sheet(attributes=" state='hidden'")),
        SHEET_A,
    ),
    (
        "dimension",
        package([worksheet(row(), "<dimension ref='A1'/>")]),
        SHEET_A,
    ),
    (
        "attribute of a worksheet",
        package([worksheet(row(), attributes=" x='1'")]),
        SHEET_A,
    ),
    (
        "style of a cell",
        package([worksheet(row(cell(attributes=" t='inlineStr' s='1'")))]),
        SHEET_A,
    ),
    (
        "cell type n",
        package([worksheet(row(cell("<v>23</v>", attributes=" t='n'")))]),
        one_value("23"),
    ),
    (
        "cell type b",
        package([worksheet(row(cell("<v>1</v>", attributes=" t='b'")))]),
        one_value("1"),
    ),
    (
        "cell type e",
        package([worksheet(row(cell("<v>#DIV/0!</v>", attributes=" t='e'")))]),
        one_value("#DIV/0!"),
    ),
    (
        "formula",
        package([worksheet(row(cell("<f>1+1</f><v>2</v>", attributes=" t='str'")))]),
        one_value("2"),
    ),
    (
        "run properties",
        package([worksheet(row(cell("<is><r><rPr/><t>a</t></r></is>")))]),
        SHEET_A,
    ),
    (
        "spans of a row",
        package([worksheet(row(attributes=" spans='1:1'"))]),
        SHEET_A,
    ),
]

MAPPED = [
    (
        "two sheets, in order",
        package(
            [worksheet(row()), worksheet(row(cell("<is><t>b</t></is>")))],
            sheet("S", 1) + sheet("T", 2),
        ),
        [
            {"sheet name": "S", "header": ["a"], "records": []},
            {"sheet name": "T", "header": ["b"], "records": []},
        ],
    ),
    (
        "sheetData without rows",
        package([worksheet()]),
        [{"sheet name": "S", "header": None, "records": []}],
    ),
    (
        "row without r",
        package([worksheet(f"<row>{cell()}</row>")]),
        SHEET_A,
    ),
    (
        "cell at C1",
        package([worksheet(row(cell(reference="C1")))]),
        [{"sheet name": "S", "header": ["", "", "a"], "records": []}],
    ),
    (
        "shared string",
        package(
            [worksheet(row(cell("<v>0</v>", attributes=" t='s'")))],
            table=strings("<si><t>a</t></si>"),
        ),
        SHEET_A,
    ),
    (
        "inline string",
        package([worksheet(row())]),
        SHEET_A,
    ),
    (
        "cell type str",
        package([worksheet(row(cell("<v>a</v>", attributes=" t='str'")))]),
        SHEET_A,
    ),
    (
        "runs of rich text",
        package([worksheet(row(cell("<is><r><t>a</t></r><r><t>b</t></r></is>")))]),
        one_value("ab"),
    ),
    (
        "empty cell kept",
        package([worksheet(row(cell() + cell("", "B1", attributes="")))]),
        [{"sheet name": "S", "header": ["a", ""], "records": []}],
    ),
    ("absolute Target", package(prefix="/xl/"), SHEET_A),
    (
        "mc:Ignorable",
        package([worksheet(row(), attributes=f" xmlns:mc='{MC}' mc:Ignorable=''")]),
        SHEET_A,
    ),
    (
        "cells out of order",
        package([worksheet(row(cell("<is><t>b</t></is>", "B1") + cell()))]),
        [{"sheet name": "S", "header": ["a", "b"], "records": []}],
    ),
]

ALWAYS = [
    ("not a ZIP file", b"not a zip"),
    ("Target with a scheme", package(prefix="http://example.com/")),
    ("truncated package", package(extra=["extra.xml"])[:20]),
    ("column given twice", package([worksheet(row(cell() + cell()))])),
    (
        "shared string index past the table",
        package(
            [worksheet(row(cell("<v>1</v>", attributes=" t='s'")))],
            table=strings("<si><t>a</t></si>"),
        ),
    ),
    (
        "negative shared string index",
        package(
            [worksheet(row(cell("<v>-1</v>", attributes=" t='s'")))],
            table=strings("<si><t>a</t></si>"),
        ),
    ),
    (
        "tab in a sheet name",
        package(entries=sheet(name="S&#9;S")),
    ),
]


class TestDump(unittest.TestCase):
    """Writing XLSX."""

    def test_conforming_round_trip(self):
        """Each conforming file round trips, or is refused."""
        for path in paths("conforming", ".json"):
            with self.subTest(path.name):
                value = load_json(path)
                if path.stem in XML_FORBIDDEN or refused(value):
                    with self.assertRaises(ValueError):
                        xlsx.dump(value, io.BytesIO())
                else:
                    self.assertEqual(round_trip(value), value)

    def test_cannot_be_represented(self):
        """Each file that MTSV cannot hold is refused by dump."""
        for path in paths("cannot-be-represented", ".json"):
            with self.subTest(path.name):
                with self.assertRaises(ValueError):
                    xlsx.dump(load_json(path), io.BytesIO())

    def test_no_sheets(self):
        """A file of no sheets cannot be represented."""
        with self.assertRaises(ValueError):
            xlsx.dump([], io.BytesIO())

    def test_xml_forbidden(self):
        """A character XML 1.0 forbids cannot be represented."""
        for value in FORBIDDEN:
            with self.subTest(repr(value)):
                field = [{"sheet name": "S", "header": [value], "records": []}]
                name = [{"sheet name": value, "header": ["a"], "records": []}]
                for sheets in (field, name):
                    with self.assertRaises(ValueError):
                        xlsx.dump(sheets, io.BytesIO())

    def test_wider_than_the_grid(self):
        """Part 1, 18.17.5.1: a sheet past column XFD is refused."""
        value = [
            {
                "sheet name": "S",
                "header": ["a"] * 16385,
                "records": [],
            }
        ]
        with self.assertRaises(ValueError):
            xlsx.dump(value, io.BytesIO())

    def test_package(self):
        """The package holds the parts the workbook needs."""
        buffer = io.BytesIO()
        value = load_json(CONFORMANCE / "conforming" / "multiple-sheets.json")
        xlsx.dump(value, buffer)
        with zipfile.ZipFile(buffer) as archive:
            self.assertEqual(
                archive.namelist(),
                [
                    "[Content_Types].xml",
                    "_rels/.rels",
                    "xl/workbook.xml",
                    "xl/_rels/workbook.xml.rels",
                    "xl/sharedStrings.xml",
                    "xl/worksheets/sheet1.xml",
                    "xl/worksheets/sheet2.xml",
                ],
            )


class TestLoad(unittest.TestCase):
    """Reading XLSX."""

    def test_left_behind(self):
        """Strict refuses each extra; ignore leaves it behind."""
        for row_id, data, expected in LEFT_BEHIND:
            with self.subTest(row_id):
                with self.assertRaises(ValueError):
                    xlsx.load(io.BytesIO(data))
                result = xlsx.load(io.BytesIO(data), errors="ignore")
                self.assertEqual(result, expected)

    def test_mapped(self):
        """Each mapping is read the same in both doors."""
        for row_id, data, expected in MAPPED:
            for errors in ("strict", "ignore"):
                with self.subTest(row_id, errors=errors):
                    result = xlsx.load(io.BytesIO(data), errors=errors)
                    self.assertEqual(result, expected)

    def test_always_refused(self):
        """Each invalid input is refused in both doors."""
        for row_id, data in ALWAYS:
            for errors in ("strict", "ignore"):
                with self.subTest(row_id, errors=errors):
                    with self.assertRaises(ValueError):
                        xlsx.load(io.BytesIO(data), errors=errors)

    def test_unknown_errors_value(self):
        """An unknown errors value raises LookupError."""
        with self.assertRaises(LookupError):
            xlsx.load(io.BytesIO(package()), errors="replace")
