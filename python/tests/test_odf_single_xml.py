"""Test mtsv.integrations.odf_single_xml against ODF 1.3."""

import io
import unittest
from xml.etree import ElementTree

from mtsv.integrations import odf_single_xml

from support import (
    COLUMN,
    CONFORMANCE,
    GRDDL,
    MEDIA_TYPE,
    NAMESPACES,
    OFFICE,
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
)


def document(tables="", attributes=""):
    """Return a single XML file, as bytes, holding tables."""
    return (
        f"<office:document{NAMESPACES} office:version='1.3'"
        f" office:mimetype='{MEDIA_TYPE}'{attributes}>"
        f"<office:body><office:spreadsheet>{tables}"
        "</office:spreadsheet></office:body></office:document>"
    ).encode("utf-8")


def one_cell(content="<text:p>a</text:p>", attributes=STRING):
    """Return a single XML file of table S with one cell."""
    return document(table(COLUMN + row(cell(content, attributes))))


def round_trip(value):
    """Dump value to a single XML document and load it back strictly."""
    buffer = io.BytesIO()
    odf_single_xml.dump(value, buffer)
    buffer.seek(0)
    return odf_single_xml.load(buffer)


LEFT_BEHIND = [
    ("grddl:transformation", document(table(), attributes=GRDDL), SHEET_A),
]

ALWAYS = [
    ("not XML", b"not xml"),
    ("not office:document", document_content(table()).encode("utf-8")),
    ("two paragraphs", one_cell("<text:p>a</text:p><text:p>b</text:p>")),
    ("text:tab", one_cell("<text:p>a<text:tab/>b</text:p>")),
    ("text:line-break", one_cell("<text:p>a<text:line-break/>b</text:p>")),
    ("tab in table:name", document(table(attributes=" table:name='S&#9;S'"))),
]


class TestDump(unittest.TestCase):
    """Writing a single XML document."""

    def test_conforming_round_trip(self):
        """Each conforming file survives dump then strict load."""
        for path in paths("conforming", ".json"):
            with self.subTest(path.name):
                value = load_json(path)
                name = path.stem
                if name in XML_FORBIDDEN:
                    with self.assertRaises(ValueError):
                        odf_single_xml.dump(value, io.BytesIO())
                else:
                    expected = TRIMMED.get(name, value)
                    self.assertEqual(round_trip(value), expected)

    def test_cannot_be_represented(self):
        """Each file that MTSV cannot hold is refused by dump."""
        for path in paths("cannot-be-represented", ".json"):
            with self.subTest(path.name):
                with self.assertRaises(ValueError):
                    odf_single_xml.dump(load_json(path), io.BytesIO())

    def test_document(self):
        """Root office:document, office:mimetype of a spreadsheet."""
        buffer = io.BytesIO()
        value = load_json(CONFORMANCE / "conforming" / "multiple-sheets.json")
        odf_single_xml.dump(value, buffer)
        root = ElementTree.fromstring(buffer.getvalue())
        self.assertEqual(root.tag, "{" + OFFICE + "}document")
        self.assertEqual(root.get("{" + OFFICE + "}mimetype"), MEDIA_TYPE)
        self.assertEqual(root.get("{" + OFFICE + "}version"), "1.3")


class TestLoad(unittest.TestCase):
    """Reading a single XML document."""

    def test_left_behind(self):
        """Strict refuses each extra; ignore leaves it behind."""
        for row_id, data, expected in LEFT_BEHIND:
            with self.subTest(row_id):
                with self.assertRaises(ValueError):
                    odf_single_xml.load(io.BytesIO(data))
                result = odf_single_xml.load(io.BytesIO(data), errors="ignore")
                self.assertEqual(result, expected)

    def test_always_refused(self):
        """Each invalid input is refused in both doors."""
        for row_id, data in ALWAYS:
            for errors in ("strict", "ignore"):
                with self.subTest(row_id, errors=errors):
                    with self.assertRaises(ValueError):
                        odf_single_xml.load(io.BytesIO(data), errors=errors)

    def test_unknown_errors_value(self):
        """An unknown errors value raises LookupError."""
        with self.assertRaises(LookupError):
            odf_single_xml.load(io.BytesIO(document(table())), errors="replace")
