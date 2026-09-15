"""Test mtsv.integrations.ods: the door out to ODS and the door back in."""

import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from mtsv.integrations import ods
from test_conformance import CONFORMANCE, load_json, paths

NOT_REPRESENTABLE_IN_ODS = {"control-characters"}
TRAILING_EMPTY_RECORDS_LEFT_BEHIND = {
    "blank-line": [
        {"sheet name": None, "header": ["a"], "records": []},
    ],
    "empty-fields": [
        {"sheet name": None, "header": ["a", "", "c"], "records": []},
    ],
}

NAMESPACES = (
    " xmlns:office='urn:oasis:names:tc:opendocument:xmlns:office:1.0'"
    " xmlns:table='urn:oasis:names:tc:opendocument:xmlns:table:1.0'"
    " xmlns:text='urn:oasis:names:tc:opendocument:xmlns:text:1.0'"
)


def package(tables):
    """Return an .ods file holding the given table:table elements."""
    content = (
        f"<office:document-content{NAMESPACES} office:version='1.3'>"
        f"<office:body><office:spreadsheet>{tables}"
        "</office:spreadsheet></office:body></office:document-content>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("content.xml", content)
    buffer.seek(0)
    return buffer


def round_trip(value):
    """Dump value to ODS and load it back strictly."""
    buffer = io.BytesIO()
    ods.dump(value, buffer)
    buffer.seek(0)
    return ods.load(buffer)


class TestDump(unittest.TestCase):
    def test_round_trip(self):
        for path in paths("conforming", ".json"):
            with self.subTest(path.name):
                value = load_json(path)
                name = path.stem
                if name in NOT_REPRESENTABLE_IN_ODS:
                    with self.assertRaises(ValueError):
                        ods.dump(value, io.BytesIO())
                elif name in TRAILING_EMPTY_RECORDS_LEFT_BEHIND:
                    expected = TRAILING_EMPTY_RECORDS_LEFT_BEHIND[name]
                    self.assertEqual(round_trip(value), expected)
                else:
                    self.assertEqual(round_trip(value), value)

    def test_package(self):
        buffer = io.BytesIO()
        value = load_json(CONFORMANCE / "conforming" / "named-only.json")
        ods.dump(value, buffer)
        with zipfile.ZipFile(buffer) as archive:
            first = archive.infolist()[0]
            self.assertEqual(first.filename, "mimetype")
            self.assertEqual(first.compress_type, zipfile.ZIP_STORED)
            self.assertEqual(
                archive.read("mimetype"),
                b"application/vnd.oasis.opendocument.spreadsheet",
            )
            self.assertEqual(
                archive.namelist(),
                ["mimetype", "META-INF/manifest.xml", "content.xml"],
            )


class TestLoad(unittest.TestCase):
    def test_extras_need_confirmation(self):
        tables = (
            "<table:table table:name='S' table:style-name='ta1'>"
            "<table:table-row><table:table-cell office:value-type='float'"
            " office:value='3' table:formula='of:=1+2'>"
            "<text:p>3</text:p></table:table-cell></table:table-row>"
            "</table:table>"
        )
        with self.assertRaises(ValueError):
            ods.load(package(tables))
        self.assertEqual(
            ods.load(package(tables), errors="ignore"),
            [{"sheet name": "S", "header": ["3"], "records": []}],
        )

    def test_formatted_text_keeps_its_text(self):
        tables = (
            "<table:table table:name='S'><table:table-row>"
            "<table:table-cell><text:p>a<text:span text:style-name='T1'>"
            "b</text:span></text:p></table:table-cell>"
            "</table:table-row></table:table>"
        )
        with self.assertRaises(ValueError):
            ods.load(package(tables))
        self.assertEqual(
            ods.load(package(tables), errors="ignore"),
            [{"sheet name": "S", "header": ["ab"], "records": []}],
        )

    def test_white_space_follows_odf_6_1_2(self):
        tables = (
            "<table:table table:name='S'><table:table-row>"
            "<table:table-cell><text:p>  a <text:s/> b  </text:p>"
            "</table:table-cell></table:table-row></table:table>"
        )
        self.assertEqual(
            ods.load(package(tables)),
            [{"sheet name": "S", "header": ["a   b"], "records": []}],
        )

    def test_tab_and_line_break_always_stop(self):
        for element in ("text:tab", "text:line-break"):
            tables = (
                "<table:table table:name='S'><table:table-row>"
                f"<table:table-cell><text:p>a<{element}/>b</text:p>"
                "</table:table-cell></table:table-row></table:table>"
            )
            for errors in ("strict", "ignore"):
                with self.subTest(element=element, errors=errors):
                    with self.assertRaises(ValueError):
                        ods.load(package(tables), errors=errors)

    def test_only_the_used_area_is_read(self):
        tables = (
            "<table:table table:name='S'>"
            "<table:table-row><table:table-cell><text:p>a</text:p>"
            "</table:table-cell><table:table-cell"
            " table:number-columns-repeated='1000'/></table:table-row>"
            "<table:table-row><table:table-cell/><table:table-cell>"
            "<text:p>b</text:p></table:table-cell></table:table-row>"
            "<table:table-row table:number-rows-repeated='1000000'>"
            "<table:table-cell/></table:table-row>"
            "</table:table>"
        )
        expected = [
            {"sheet name": "S", "header": ["a", ""], "records": [["", "b"]]}
        ]
        self.assertEqual(ods.load(package(tables)), expected)

    def test_unnamed_sheet_after_the_first_stops(self):
        tables = (
            "<table:table table:name='S'><table:table-row><table:table-cell>"
            "<text:p>a</text:p></table:table-cell></table:table-row>"
            "</table:table>"
            "<table:table><table:table-row><table:table-cell>"
            "<text:p>b</text:p></table:table-cell></table:table-row>"
            "</table:table>"
        )
        with self.assertRaises(ValueError):
            ods.load(package(tables), errors="ignore")

    def test_unknown_errors_value(self):
        with self.assertRaises(LookupError):
            ods.load(package(""), errors="replace")


class TestMain(unittest.TestCase):
    def test_converts_both_ways(self):
        original = CONFORMANCE / "conforming" / "named-only.mtsv"
        with tempfile.TemporaryDirectory() as directory:
            spreadsheet = Path(directory, "named-only.ods")
            back = Path(directory, "named-only.mtsv")
            ods.main([str(original), str(spreadsheet)])
            ods.main([str(spreadsheet), str(back)])
            self.assertEqual(back.read_bytes(), original.read_bytes())

    def test_extras_need_the_errors_option(self):
        tables = (
            "<table:table table:name='S' table:style-name='ta1'>"
            "<table:table-row><table:table-cell><text:p>a</text:p>"
            "</table:table-cell></table:table-row></table:table>"
        )
        expected = bytes([0x0C]) + b"S" + bytes([0x0A]) + b"a" + bytes([0x0A])
        with tempfile.TemporaryDirectory() as directory:
            spreadsheet = Path(directory, "styled.ods")
            result = Path(directory, "styled.mtsv")
            spreadsheet.write_bytes(package(tables).getvalue())
            with self.assertRaises(SystemExit):
                ods.main([str(spreadsheet), str(result)])
            ods.main([str(spreadsheet), str(result), "--errors", "ignore"])
            self.assertEqual(result.read_bytes(), expected)
