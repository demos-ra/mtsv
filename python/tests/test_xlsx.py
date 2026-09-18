"""Test mtsv.integrations.xlsx against its mapping to ISO/IEC 29500.

Each case names the mapping row it confirms: O-n for writing an XLSX
file, I-n for reading one.
"""

import io
import logging
import tempfile
import unittest
import zipfile
from pathlib import Path

from mtsv.integrations import xlsx

from support import CONFORMANCE, load_json, paths

MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CONTENT_TYPES = "http://schemas.openxmlformats.org/package/2006/content-types"
RELATIONSHIPS = "http://schemas.openxmlformats.org/package/2006/relationships"
RELATIONSHIP_TYPE = "application/vnd.openxmlformats-package.relationships+xml"
WORKBOOK_TYPE = (
    "application/vnd.openxmlformats-officedocument"
    ".spreadsheetml.sheet.main+xml"
)
WORKSHEET_TYPE = (
    "application/vnd.openxmlformats-officedocument"
    ".spreadsheetml.worksheet+xml"
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
    return (
        f"<sheet name='{name}' sheetId='{index}'"
        f" r:id='rId{index}'{attributes}/>"
    )


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


def package(
    sheets=None, entries=None, children="", table=None, extra=(), prefix=""
):
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
    """Return whether XLSX cannot hold these sheets, per O-4."""
    return not value


LEFT_BEHIND = [
    (
        "I-4",
        package(entries=sheet(), children="<calcPr calcId='1'/>"),
        SHEET_A,
    ),
    (
        "I-5",
        package(entries=sheet(attributes=" state='hidden'")),
        SHEET_A,
    ),
    (
        "I-6",
        package([worksheet(row(), "<dimension ref='A1'/>")]),
        SHEET_A,
    ),
    (
        "I-6 root attribute",
        package([worksheet(row(), attributes=" x='1'")]),
        SHEET_A,
    ),
    (
        "I-10",
        package([worksheet(row(cell(attributes=" t='inlineStr' s='1'")))]),
        SHEET_A,
    ),
    (
        "I-14",
        package([worksheet(row(cell("<v>23</v>", attributes=" t='n'")))]),
        one_value("23"),
    ),
    (
        "I-15",
        package([worksheet(row(cell("<v>1</v>", attributes=" t='b'")))]),
        one_value("1"),
    ),
    (
        "I-16",
        package(
            [worksheet(row(cell("<v>#DIV/0!</v>", attributes=" t='e'")))]
        ),
        one_value("#DIV/0!"),
    ),
    (
        "I-17",
        package(
            [
                worksheet(
                    row(
                        cell(
                            "<f>1+1</f><v>2</v>", attributes=" t='str'"
                        )
                    )
                )
            ]
        ),
        one_value("2"),
    ),
    (
        "I-18",
        package(
            [worksheet(row(cell("<is><r><rPr/><t>a</t></r></is>")))]
        ),
        SHEET_A,
    ),
    (
        "I-8 spans",
        package([worksheet(row(attributes=" spans='1:1'"))]),
        SHEET_A,
    ),
]

MAPPED = [
    (
        "I-3",
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
        "I-7",
        package([worksheet()]),
        [{"sheet name": "S", "header": None, "records": []}],
    ),
    (
        "I-8",
        package([worksheet(f"<row>{cell()}</row>")]),
        SHEET_A,
    ),
    (
        "I-9",
        package(
            [worksheet(row(cell(reference="C1")))]
        ),
        [{"sheet name": "S", "header": ["", "", "a"], "records": []}],
    ),
    (
        "I-11",
        package(
            [worksheet(row(cell("<v>0</v>", attributes=" t='s'")))],
            table=strings("<si><t>a</t></si>"),
        ),
        SHEET_A,
    ),
    (
        "I-12",
        package([worksheet(row())]),
        SHEET_A,
    ),
    (
        "I-13",
        package([worksheet(row(cell("<v>a</v>", attributes=" t='str'")))]),
        SHEET_A,
    ),
    (
        "I-18 runs",
        package(
            [worksheet(row(cell("<is><r><t>a</t></r><r><t>b</t></r></is>")))]
        ),
        one_value("ab"),
    ),
    (
        "I-9 no trimming",
        package(
            [
                worksheet(
                    row(cell() + cell("", "B1", attributes=""))
                )
            ]
        ),
        [{"sheet name": "S", "header": ["a", ""], "records": []}],
    ),
    ("I-1 absolute target", package(prefix="/xl/"), SHEET_A),
    (
        "I-6 compatibility attribute",
        package(
            [
                worksheet(
                    row(), attributes=f" xmlns:mc='{MC}' mc:Ignorable=''"
                )
            ]
        ),
        SHEET_A,
    ),
    (
        "I-9 reversed",
        package([worksheet(row(cell("<is><t>b</t></is>", "B1") + cell()))]),
        [{"sheet name": "S", "header": ["a", "b"], "records": []}],
    ),
]

ALWAYS = [
    ("I-2 not a zip", b"not a zip"),
    ("I-1 target with a scheme", package(prefix="http://example.com/")),
    ("I-2 no workbook", package(extra=["extra.xml"])[:20]),
    ("I-9 column twice", package([worksheet(row(cell() + cell()))])),
    (
        "I-11 index past the table",
        package(
            [worksheet(row(cell("<v>1</v>", attributes=" t='s'")))],
            table=strings("<si><t>a</t></si>"),
        ),
    ),
    (
        "I-11 negative index",
        package(
            [worksheet(row(cell("<v>-1</v>", attributes=" t='s'")))],
            table=strings("<si><t>a</t></si>"),
        ),
    ),
    (
        "I-44 sheet name",
        package(entries=sheet(name="S&#9;S")),
    ),
]


class TestDump(unittest.TestCase):
    """Writing XLSX: rows O-1 to O-7."""

    def test_conforming_round_trip(self):
        """R1: each conforming file round trips, or is refused."""
        for path in paths("conforming", ".json"):
            with self.subTest(path.name):
                value = load_json(path)
                if path.stem in XML_FORBIDDEN or refused(value):
                    with self.assertRaises(ValueError):
                        xlsx.dump(value, io.BytesIO())
                else:
                    self.assertEqual(round_trip(value), value)

    def test_cannot_be_represented(self):
        """R2: each file that MTSV cannot hold is refused by dump."""
        for path in paths("cannot-be-represented", ".json"):
            with self.subTest(path.name):
                with self.assertRaises(ValueError):
                    xlsx.dump(load_json(path), io.BytesIO())

    def test_no_sheets(self):
        """O-4: a file of no sheets cannot be represented."""
        with self.assertRaises(ValueError):
            xlsx.dump([], io.BytesIO())

    def test_xml_forbidden(self):
        """O-6: a character XML 1.0 forbids cannot be represented."""
        for value in FORBIDDEN:
            with self.subTest(repr(value)):
                field = [{"sheet name": "S", "header": [value],
                          "records": []}]
                name = [{"sheet name": value, "header": ["a"],
                         "records": []}]
                for sheets in (field, name):
                    with self.assertRaises(ValueError):
                        xlsx.dump(sheets, io.BytesIO())

    def test_wider_than_the_grid(self):
        """O-5: a sheet wider than column XFD is refused."""
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
        """R6, O-1: the package holds the parts the mapping names."""
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
    """Reading XLSX: rows I-1 to I-18."""

    def test_left_behind(self):
        """R3: strict refuses each extra; ignore leaves it behind."""
        for row_id, data, expected in LEFT_BEHIND:
            with self.subTest(row_id):
                with self.assertRaises(ValueError):
                    xlsx.load(io.BytesIO(data))
                result = xlsx.load(io.BytesIO(data), errors="ignore")
                self.assertEqual(result, expected)

    def test_mapped(self):
        """R4: each mapping is read the same in both doors."""
        for row_id, data, expected in MAPPED:
            for errors in ("strict", "ignore"):
                with self.subTest(row_id, errors=errors):
                    result = xlsx.load(io.BytesIO(data), errors=errors)
                    self.assertEqual(result, expected)

    def test_always_refused(self):
        """R5: each invalid input is refused in both doors."""
        for row_id, data in ALWAYS:
            for errors in ("strict", "ignore"):
                with self.subTest(row_id, errors=errors):
                    with self.assertRaises(ValueError):
                        xlsx.load(io.BytesIO(data), errors=errors)

    def test_unknown_errors_value(self):
        """R5: an unknown errors value raises LookupError."""
        with self.assertRaises(LookupError):
            xlsx.load(io.BytesIO(package()), errors="replace")


class TestMain(unittest.TestCase):
    """The command line: python -m mtsv.integrations.xlsx."""

    def test_converts_both_ways(self):
        """R6: .mtsv to .xlsx and back gives the same bytes."""
        original = CONFORMANCE / "conforming" / "multiple-sheets.mtsv"
        with tempfile.TemporaryDirectory() as directory:
            book = Path(directory, "multiple-sheets.xlsx")
            back = Path(directory, "multiple-sheets.mtsv")
            xlsx.main([str(original), str(book)])
            xlsx.main([str(book), str(back)])
            self.assertEqual(back.read_bytes(), original.read_bytes())

    def test_extras_are_reported_not_refused(self):
        """R6: extras are noted, and --errors strict refuses them."""
        data = package(entries=sheet(attributes=" state='hidden'"))
        expected = bytes([0x0C]) + b"S" + bytes([0x0A]) + b"a" + bytes([0x0A])
        with tempfile.TemporaryDirectory() as directory:
            book = Path(directory, "hidden.xlsx")
            result = Path(directory, "hidden.mtsv")
            book.write_bytes(data)
            with self.assertLogs("mtsv.integrations", logging.WARNING):
                xlsx.main([str(book), str(result)])
            self.assertEqual(result.read_bytes(), expected)
            with self.assertRaises(SystemExit):
                xlsx.main([str(book), str(result), "--errors", "strict"])
