"""Test mtsv.integrations.ods against ODF 1.3."""

import io
import unittest
import zipfile

from mtsv.integrations import ods

from support import (
    COLUMN,
    CONFORMANCE,
    GRDDL,
    MEDIA_TYPE,
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


def package(tables="", document="", spreadsheet="", entries=(), attributes=""):
    """Return an .ods file, as bytes, whose spreadsheet holds tables."""
    return archive(document_content(tables, document, spreadsheet, attributes), entries)


def one_cell(content="<text:p>a</text:p>", attributes=STRING):
    """Return an .ods file of table S with one column and one cell."""
    return package(table(COLUMN + row(cell(content, attributes))))


def round_trip(value):
    """Dump value to ODS and load it back strictly."""
    buffer = io.BytesIO()
    ods.dump(value, buffer)
    buffer.seek(0)
    return ods.load(buffer)


LEFT_BEHIND = [
    ("styles.xml", package(table(), entries=["styles.xml"]), SHEET_A),
    ("grddl:transformation", package(table(), attributes=GRDDL), SHEET_A),
]

ALWAYS = [
    ("not a ZIP file", b"not a zip"),
    ("no content.xml", archive()),
    (
        "not office:document-content",
        archive(f"<office:document-styles{NAMESPACES} office:version='1.3'/>"),
    ),
    ("two paragraphs", one_cell("<text:p>a</text:p><text:p>b</text:p>")),
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
            self.assertEqual(archive_file.read("mimetype"), MEDIA_TYPE.encode("ascii"))
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
