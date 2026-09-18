"""Convert between MTSV sheets and OpenDocument spreadsheets, ODF 1.3.

Functions:
dump -- write MTSV sheets to a binary file as an ODF spreadsheet
load -- read MTSV sheets from a binary ODF spreadsheet file
main -- deprecated: convert .mtsv to .ods, or .ods to .mtsv
"""

__all__ = ["dump", "load", "main"]

import re
import zipfile
from collections.abc import Iterator
from itertools import groupby
from typing import Any, BinaryIO
from xml.etree import ElementTree
from xml.sax.saxutils import escape, quoteattr

import mtsv
import mtsv.integrations
from mtsv import _command
from mtsv.integrations import _xml

_MEDIA_TYPE = "application/vnd.oasis.opendocument.spreadsheet"
_PACKAGE_FILES = ("mimetype", "META-INF/manifest.xml", "content.xml")
_MANIFEST = "urn:oasis:names:tc:opendocument:xmlns:manifest:1.0"
_OFFICE = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
_TABLE = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
_TEXT = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
_PREFIXES = {
    _MANIFEST: "manifest",
    _OFFICE: "office",
    _TABLE: "table",
    _TEXT: "text",
}

_DOCUMENT_CONTENT = "{" + _OFFICE + "}document-content"
_VERSION = "{" + _OFFICE + "}version"
_BODY = "{" + _OFFICE + "}body"
_SPREADSHEET = "{" + _OFFICE + "}spreadsheet"
_VALUE_TYPE = "{" + _OFFICE + "}value-type"
_STRING_VALUE = "{" + _OFFICE + "}string-value"
_VALUE = "{" + _OFFICE + "}value"
_DATE_VALUE = "{" + _OFFICE + "}date-value"
_TIME_VALUE = "{" + _OFFICE + "}time-value"
_BOOLEAN_VALUE = "{" + _OFFICE + "}boolean-value"
_TABLE_TABLE = "{" + _TABLE + "}table"
_NAME = "{" + _TABLE + "}name"
_COLUMN = "{" + _TABLE + "}table-column"
_COLUMNS = "{" + _TABLE + "}table-columns"
_ROW = "{" + _TABLE + "}table-row"
_ROWS = "{" + _TABLE + "}table-rows"
_WRAPPERS = (
    "{" + _TABLE + "}table-header-rows",
    "{" + _TABLE + "}table-row-group",
    "{" + _TABLE + "}table-header-columns",
    "{" + _TABLE + "}table-column-group",
)
_CELL = "{" + _TABLE + "}table-cell"
_COVERED_CELL = "{" + _TABLE + "}covered-table-cell"
_COLUMNS_REPEATED = "{" + _TABLE + "}number-columns-repeated"
_ROWS_REPEATED = "{" + _TABLE + "}number-rows-repeated"
_P = "{" + _TEXT + "}p"
_H = "{" + _TEXT + "}h"
_S = "{" + _TEXT + "}s"
_C = "{" + _TEXT + "}c"
_TAB = "{" + _TEXT + "}tab"
_LINE_BREAK = "{" + _TEXT + "}line-break"
_RUBY = "{" + _TEXT + "}ruby"
_RUBY_BASE = "{" + _TEXT + "}ruby-base"
_PARAGRAPH_CONTENT = (
    "{" + _TEXT + "}a",
    "{" + _TEXT + "}meta",
    "{" + _TEXT + "}meta-field",
    "{" + _TEXT + "}span",
)

# The value attribute of each office:value-type, ODF 1.3, 19.389.
_VALUE_ATTRIBUTES = {
    "boolean": _BOOLEAN_VALUE,
    "currency": _VALUE,
    "date": _DATE_VALUE,
    "float": _VALUE,
    "percentage": _VALUE,
    "string": _STRING_VALUE,
    "time": _TIME_VALUE,
    "void": None,
}

_HTAB = chr(0x09)
_LF = chr(0x0A)
_CR = chr(0x0D)
_SPACE = chr(0x20)
_SPACES = re.compile(_SPACE + "+")
_XML_SPACE = _SPACE + _HTAB + _CR + _LF
_DIGITS = re.compile("[0-9]+")


def dump(obj: list[dict[str, Any]], fp: BinaryIO) -> None:
    """Write MTSV sheets to a binary file as an ODF spreadsheet.

    Raise ValueError if the sheets are not MTSV, or if a field or sheet
    name holds a character that XML 1.0 does not allow.
    """
    mtsv.dumps(obj)
    _xml.check_chars(obj, "ODS")
    # ODF 1.3 Part 2, 3.3: "mimetype" is the first file, not compressed.
    with zipfile.ZipFile(fp, "w") as package:
        package.writestr(
            zipfile.ZipInfo("mimetype"), _MEDIA_TYPE, zipfile.ZIP_STORED
        )
        package.writestr(
            zipfile.ZipInfo("META-INF/manifest.xml"),
            _manifest(),
            zipfile.ZIP_DEFLATED,
        )
        package.writestr(
            zipfile.ZipInfo("content.xml"),
            _document_content(obj),
            zipfile.ZIP_DEFLATED,
        )


def load(fp: BinaryIO, /, errors: str = "strict") -> list[dict[str, Any]]:
    """Read MTSV sheets from a binary ODF spreadsheet file.

    With errors="strict", raise ValueError if anything outside MTSV
    would be left behind. With errors="ignore", leave it behind. Raise
    ValueError for a file that is not an ODF spreadsheet.
    """
    mtsv.integrations._errors(errors)
    extras: set[str] = set()
    try:
        with zipfile.ZipFile(fp) as package:
            for name in package.namelist():
                if name not in _PACKAGE_FILES:
                    extras.add(name)
            root = ElementTree.fromstring(package.read("content.xml"))
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as error:
        raise ValueError("the file is not an ODF package") from error
    sheets = _spreadsheet(root, extras)
    mtsv.integrations.report(extras, errors)
    mtsv.dumps(sheets)
    return sheets


def main(argv: list[str] | None = None) -> None:
    """Convert a .mtsv file to .ods, or an .ods file to .mtsv.

    Deprecated; to be removed in 0.5.0. Semantic Versioning, "How
    should I handle deprecating functionality?"
    """
    _command.run(
        "python -m mtsv.integrations.ods",
        "Convert a .mtsv file to .ods, or an .ods file to .mtsv.",
        (".ods",),
        argv,
    )


def _manifest() -> str:
    """Generate META-INF/manifest.xml, per ODF 1.3 Part 2, 3.2."""
    return (
        "<?xml version='1.0' encoding='UTF-8'?>"
        f"<manifest:manifest xmlns:manifest='{_MANIFEST}'"
        " manifest:version='1.3'>"
        "<manifest:file-entry manifest:full-path='/'"
        f" manifest:media-type='{_MEDIA_TYPE}'/>"
        "<manifest:file-entry manifest:full-path='content.xml'"
        " manifest:media-type='text/xml'/>"
        "</manifest:manifest>"
    )


def _document_content(sheets: list[dict[str, Any]]) -> str:
    """Generate content.xml with one table:table per sheet."""
    tables = "".join(_table(sheet) for sheet in sheets)
    return (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<office:document-content"
        f" xmlns:office='{_OFFICE}'"
        f" xmlns:table='{_TABLE}'"
        f" xmlns:text='{_TEXT}'"
        " office:version='1.3'>"
        f"<office:body><office:spreadsheet>{tables}"
        "</office:spreadsheet></office:body>"
        "</office:document-content>"
    )


def _table(sheet: dict[str, Any]) -> str:
    """Generate table:table; an empty sheet gets one empty cell."""
    attribute = " table:name=" + quoteattr(sheet["sheet name"])
    if sheet["header"] is None:
        rows = [[""]]
    else:
        rows = [sheet["header"], *sheet["records"]]
    column = (
        "<table:table-column"
        f" table:number-columns-repeated='{len(rows[0])}'/>"
    )
    cells = "".join(_row(fields) for fields in rows)
    return f"<table:table{attribute}>{column}{cells}</table:table>"


def _row(fields: list[str]) -> str:
    """Generate table:table-row."""
    cells = "".join(_cell(value) for value in fields)
    return f"<table:table-row>{cells}</table:table-row>"


def _cell(value: str) -> str:
    """Generate table:table-cell; an empty field is an empty cell."""
    if not value:
        return "<table:table-cell/>"
    return (
        "<table:table-cell office:value-type='string'>"
        f"<text:p>{_paragraph(value)}</text:p>"
        "</table:table-cell>"
    )


def _paragraph(value: str) -> str:
    """Generate text:p content, spaces marked per ODF 1.3, 6.1.2-6.1.3.

    A single space between other characters stays a space; every other
    space is written with text:s.
    """
    groups = [
        (is_space, "".join(chars))
        for is_space, chars in groupby(value, lambda char: char == _SPACE)
    ]
    parts = []
    for index, (is_space, chars) in enumerate(groups):
        if not is_space:
            parts.append(escape(chars))
            continue
        count = len(chars)
        if 0 < index < len(groups) - 1:
            parts.append(_SPACE)
            count -= 1
        if count == 1:
            parts.append("<text:s/>")
        elif count > 1:
            parts.append(f"<text:s text:c='{count}'/>")
    return "".join(parts)


def _count(value: str, minimum: int) -> int:
    """Read a positiveInteger (minimum 1) or nonNegativeInteger (0)."""
    digits = value.strip(_XML_SPACE)
    if not _DIGITS.fullmatch(digits) or int(digits) < minimum:
        raise ValueError(f"not a valid ODF count: {value!r}")
    return int(digits)


def _spreadsheet(
    root: ElementTree.Element, extras: set[str]
) -> list[dict[str, Any]]:
    """Parse office:document-content into MTSV sheets."""
    if root.tag != _DOCUMENT_CONTENT:
        raise ValueError("content.xml is not office:document-content")
    _xml.note_attributes(root, (_VERSION,), extras, _PREFIXES)
    spreadsheet = None
    for child in root:
        if child.tag == _BODY:
            spreadsheet = child.find(_SPREADSHEET)
        else:
            extras.add(_xml.prefixed(child.tag, _PREFIXES))
    if spreadsheet is None:
        raise ValueError("the document is not an office:spreadsheet")
    _xml.note_attributes(spreadsheet, (), extras, _PREFIXES)
    sheets = []
    for child in spreadsheet:
        if child.tag != _TABLE_TABLE:
            extras.add(_xml.prefixed(child.tag, _PREFIXES))
            continue
        sheets.append(_sheet(child, extras))
    return sheets


def _sheet(element: ElementTree.Element, extras: set[str]) -> dict[str, Any]:
    """Parse table:table into a sheet, reading only its used area."""
    _xml.note_attributes(element, (_NAME,), extras, _PREFIXES)
    name = element.get(_NAME, "")
    lines: list[list[str]] = []
    pending = 0
    for count, values in _rows(element, extras):
        if values:
            lines.extend([] for _ in range(pending))
            pending = 0
            lines.extend(list(values) for _ in range(count))
        else:
            pending += count
    return mtsv.integrations._sheet(name, lines)


def _rows(
    element: ElementTree.Element, extras: set[str]
) -> Iterator[tuple[int, list[str]]]:
    """Yield (repeat count, values) per row, reading into wrappers."""
    for child in element:
        if child.tag == _ROW:
            _xml.note_attributes(
                child, (_ROWS_REPEATED,), extras, _PREFIXES
            )
            count = _count(child.get(_ROWS_REPEATED, "1"), 1)
            yield count, _cells(child, extras)
        elif child.tag == _COLUMN:
            _xml.note_attributes(
                child, (_COLUMNS_REPEATED,), extras, _PREFIXES
            )
            _count(child.get(_COLUMNS_REPEATED, "1"), 1)
        elif child.tag in (_ROWS, _COLUMNS):
            yield from _rows(child, extras)
        elif child.tag in _WRAPPERS:
            extras.add(_xml.prefixed(child.tag, _PREFIXES))
            _xml.note_attributes(child, (), extras, _PREFIXES)
            yield from _rows(child, extras)
        else:
            extras.add(_xml.prefixed(child.tag, _PREFIXES))


def _cells(row: ElementTree.Element, extras: set[str]) -> list[str]:
    """Read a row's cell values, without its trailing empty cells."""
    values: list[str] = []
    pending = 0
    for child in row:
        if child.tag == _CELL:
            text = _cell_value(child, extras)
        elif child.tag == _COVERED_CELL:
            extras.add(_xml.prefixed(child.tag, _PREFIXES))
            text = ""
        else:
            extras.add(_xml.prefixed(child.tag, _PREFIXES))
            continue
        count = _count(child.get(_COLUMNS_REPEATED, "1"), 1)
        if text:
            values.extend([""] * pending)
            pending = 0
            values.extend([text] * count)
        else:
            pending += count
    return values


def _cell_value(cell: ElementTree.Element, extras: set[str]) -> str:
    """Read a cell's value, from its value attribute, ODF 1.3, 19.389.

    A value type other than string is left behind.
    """
    value_type = cell.get(_VALUE_TYPE)
    holder = _VALUE_ATTRIBUTES.get(value_type)
    value = None if holder is None else cell.get(holder)
    for key in cell.attrib:
        if key == _COLUMNS_REPEATED:
            continue
        if key == _VALUE_TYPE and value_type in _VALUE_ATTRIBUTES:
            continue
        if key == holder and value is not None:
            continue
        extras.add(_xml.prefixed(key, _PREFIXES))
    text = _cell_text(cell, extras)
    if value is None:
        return text
    if value_type != "string":
        extras.add(f"office:value-type {value_type}")
    elif text and text != value:
        extras.add(_xml.prefixed(_P, _PREFIXES))
    return value


def _cell_text(cell: ElementTree.Element, extras: set[str]) -> str:
    """Read a cell's paragraphs, joined by line breaks."""
    paragraphs = []
    for child in cell:
        if child.tag in (_P, _H):
            if child.tag == _H:
                extras.add(_xml.prefixed(child.tag, _PREFIXES))
            _xml.note_attributes(child, (), extras, _PREFIXES)
            paragraphs.append(_paragraph_text(child, extras))
        else:
            extras.add(_xml.prefixed(child.tag, _PREFIXES))
    return _LF.join(paragraphs)


def _paragraph_text(paragraph: ElementTree.Element, extras: set[str]) -> str:
    """Read a paragraph by the white space rules of ODF 1.3, 6.1.2."""
    tokens: list[tuple[bool, str]] = []
    _collect(paragraph, tokens, extras)
    merged: list[tuple[bool, str]] = []
    for kept, text in tokens:
        if not kept and merged and not merged[-1][0]:
            merged[-1] = (False, merged[-1][1] + text)
        else:
            merged.append((kept, text))
    if merged and not merged[0][0]:
        merged[0] = (False, merged[0][1].lstrip(_SPACE))
    if merged and not merged[-1][0]:
        merged[-1] = (False, merged[-1][1].rstrip(_SPACE))
    return "".join(
        text if kept else _SPACES.sub(_SPACE, text) for kept, text in merged
    )


def _collect(
    element: ElementTree.Element,
    tokens: list[tuple[bool, str]],
    extras: set[str],
) -> None:
    """Flatten paragraph content per steps 1 to 4 of ODF 1.3, 6.1.2."""
    if element.text:
        tokens.append((False, _to_spaces(element.text)))
    for child in element:
        if child.tag == _S:
            tokens.append((True, _SPACE * _count(child.get(_C, "1"), 0)))
        elif child.tag == _TAB:
            tokens.append((True, _HTAB))
        elif child.tag == _LINE_BREAK:
            tokens.append((True, _LF))
        elif child.tag == _RUBY:
            extras.add(_xml.prefixed(child.tag, _PREFIXES))
            base = child.find(_RUBY_BASE)
            if base is not None:
                _collect(base, tokens, extras)
        elif child.tag in _PARAGRAPH_CONTENT:
            extras.add(_xml.prefixed(child.tag, _PREFIXES))
            _collect(child, tokens, extras)
        else:
            extras.add(_xml.prefixed(child.tag, _PREFIXES))
        if child.tail:
            tokens.append((False, _to_spaces(child.tail)))


def _to_spaces(text: str) -> str:
    """Replace HT, CR, and LF with a space, step 4 of ODF 1.3, 6.1.2."""
    text = text.replace(_HTAB, _SPACE)
    text = text.replace(_CR, _SPACE)
    return text.replace(_LF, _SPACE)


if __name__ == "__main__":
    main()
