"""Convert between MTSV sheets and OpenDocument spreadsheets, ODF 1.3.

Functions:
dump -- write MTSV sheets to a binary file as an ODF spreadsheet
load -- read MTSV sheets from a binary ODF spreadsheet file
"""

__all__ = ["dump", "load"]

import re
import zipfile
from itertools import groupby
from typing import Any, BinaryIO
from xml.etree import ElementTree
from xml.sax.saxutils import escape, quoteattr

import mtsv
from mtsv.integrations import _errors, _xml
from mtsv.integrations._sheet import from_lines

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

# ODF 1.3 Part 3, 19.389, Table 14: the value attribute of each
# office:value-type.
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

    obj -- the MTSV sheets
    fp -- a binary file object open for writing

    Raise ValueError if the sheets are not MTSV, or if a field or sheet
    name holds a character that XML 1.0 does not allow.
    """
    mtsv.dumps(obj)
    _xml.check_chars(obj, "ODS")
    # ODF 1.3 Part 2, 3.3: "mimetype" is the first file, not compressed.
    with zipfile.ZipFile(fp, "w") as package:
        package.writestr(zipfile.ZipInfo("mimetype"), _MEDIA_TYPE, zipfile.ZIP_STORED)
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

    fp -- a binary file object open for reading
    errors -- "strict" or "ignore"

    Return the sheets. With errors="strict", raise ValueError if
    anything outside MTSV would be left behind; with errors="ignore",
    leave it behind. Raise ValueError for a file that is not an ODF
    spreadsheet, and LookupError for another errors value.
    """
    _errors.lookup_error(errors)
    try:
        with zipfile.ZipFile(fp) as package:
            names = package.namelist()
            root = ElementTree.fromstring(package.read("content.xml"))
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as error:
        raise ValueError("the file is not an ODF package") from error
    sheets, extras = _spreadsheet(root)
    extras |= {name for name in names if name not in _PACKAGE_FILES}
    _errors.report(extras, errors)
    mtsv.dumps(sheets)
    return sheets


def _manifest() -> str:
    """Generate META-INF/manifest.xml, ODF 1.3 Part 2, 3.2.

    Return its XML.
    """
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
    """Generate content.xml with one table:table per sheet.

    sheets -- the MTSV sheets

    Return its XML.
    """
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
    """Generate table:table; an empty sheet gets one empty cell.

    sheet -- one MTSV sheet

    Return its XML.
    """
    attribute = " table:name=" + quoteattr(sheet["sheet name"])
    if sheet["header"] is None:
        rows = [[""]]
    else:
        rows = [sheet["header"], *sheet["records"]]
    column = f"<table:table-column table:number-columns-repeated='{len(rows[0])}'/>"
    cells = "".join(_row(fields) for fields in rows)
    return f"<table:table{attribute}>{column}{cells}</table:table>"


def _row(fields: list[str]) -> str:
    """Generate table:table-row.

    fields -- the fields of one line

    Return its XML.
    """
    cells = "".join(_cell(value) for value in fields)
    return f"<table:table-row>{cells}</table:table-row>"


def _cell(value: str) -> str:
    """Generate table:table-cell of value type string.

    value -- one field

    Return its XML; an empty field is a cell without a paragraph. ODF
    1.3 Part 3, 19.389: "The value type of each of these elements shall
    be specified"; "If the value type is string and the
    office:string-value attribute is not present, the element content
    defines the value."
    """
    if not value:
        return "<table:table-cell office:value-type='string'/>"
    return (
        "<table:table-cell office:value-type='string'>"
        f"<text:p>{_paragraph(value)}</text:p>"
        "</table:table-cell>"
    )


def _paragraph(value: str) -> str:
    """Generate text:p content, ODF 1.3 Part 3, 6.1.2 and 6.1.3.

    value -- one field, not empty

    Return its XML: a single space between other characters stays a
    space; every other space is written with text:s.
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


def _spreadsheet(
    root: ElementTree.Element,
) -> tuple[list[dict[str, Any]], set[str]]:
    """Parse office:document-content into MTSV sheets.

    root -- the root element of content.xml

    Return the sheets, and what they leave behind. Raise ValueError for
    a document that is not a spreadsheet.
    """
    if root.tag != _DOCUMENT_CONTENT:
        raise ValueError("content.xml is not office:document-content")
    left = _xml.attributes_left_behind(root, (_VERSION,), _PREFIXES)
    spreadsheet = None
    for child in root:
        if child.tag == _BODY:
            spreadsheet = child.find(_SPREADSHEET)
        else:
            left.add(_xml.prefixed(child.tag, _PREFIXES))
    if spreadsheet is None:
        raise ValueError("the document is not an office:spreadsheet")
    left |= _xml.attributes_left_behind(spreadsheet, (), _PREFIXES)
    sheets = []
    for child in spreadsheet:
        if child.tag != _TABLE_TABLE:
            left.add(_xml.prefixed(child.tag, _PREFIXES))
            continue
        sheet, sheet_left = _sheet(child)
        sheets.append(sheet)
        left |= sheet_left
    return sheets, left


def _sheet(element: ElementTree.Element) -> tuple[dict[str, Any], set[str]]:
    """Parse table:table into a sheet, reading only its used area.

    element -- one table:table

    Return the sheet, and what it leaves behind. Raise ValueError for
    a count that is not valid.
    """
    left = _xml.attributes_left_behind(element, (_NAME,), _PREFIXES)
    name = element.get(_NAME, "")
    rows, rows_left = _rows(element)
    left |= rows_left
    lines: list[list[str]] = []
    pending = 0
    for count, values in rows:
        if values:
            lines.extend([] for _ in range(pending))
            pending = 0
            lines.extend(list(values) for _ in range(count))
        else:
            pending += count
    return from_lines(name, lines), left


def _rows(
    element: ElementTree.Element,
) -> tuple[list[tuple[int, list[str]]], set[str]]:
    """Read the rows of a table, reading into wrappers.

    element -- a table:table or a wrapper of rows

    Return (repeat count, values) per row, and what the rows leave
    behind. Raise ValueError for a count that is not valid.
    """
    rows = []
    left: set[str] = set()
    for child in element:
        if child.tag == _ROW:
            left |= _xml.attributes_left_behind(child, (_ROWS_REPEATED,), _PREFIXES)
            count = _count(child.get(_ROWS_REPEATED, "1"), 1)
            values, cells_left = _cells(child)
            rows.append((count, values))
            left |= cells_left
        elif child.tag == _COLUMN:
            left |= _xml.attributes_left_behind(child, (_COLUMNS_REPEATED,), _PREFIXES)
            _count(child.get(_COLUMNS_REPEATED, "1"), 1)
        elif child.tag in (_ROWS, _COLUMNS):
            inner, inner_left = _rows(child)
            rows.extend(inner)
            left |= inner_left
        elif child.tag in _WRAPPERS:
            left.add(_xml.prefixed(child.tag, _PREFIXES))
            left |= _xml.attributes_left_behind(child, (), _PREFIXES)
            inner, inner_left = _rows(child)
            rows.extend(inner)
            left |= inner_left
        else:
            left.add(_xml.prefixed(child.tag, _PREFIXES))
    return rows, left


def _cells(row: ElementTree.Element) -> tuple[list[str], set[str]]:
    """Read a row's cell values, without its trailing empty cells.

    row -- one table:table-row

    Return the values, and what the cells leave behind. Raise
    ValueError for a count that is not valid.
    """
    values: list[str] = []
    left: set[str] = set()
    pending = 0
    for child in row:
        if child.tag == _CELL:
            text, cell_left = _cell_value(child)
            left |= cell_left
        elif child.tag == _COVERED_CELL:
            left.add(_xml.prefixed(child.tag, _PREFIXES))
            text = ""
        else:
            left.add(_xml.prefixed(child.tag, _PREFIXES))
            continue
        count = _count(child.get(_COLUMNS_REPEATED, "1"), 1)
        if text:
            values.extend([""] * pending)
            pending = 0
            values.extend([text] * count)
        else:
            pending += count
    return values, left


def _cell_value(cell: ElementTree.Element) -> tuple[str, set[str]]:
    """Read a cell's value, from its value attribute.

    cell -- one table:table-cell

    Return the value, and what the cell leaves behind; a value type
    other than string is left behind. ODF 1.3 Part 3, 19.389: the value
    attribute holds the value "if the value type is not string or if
    the <table:table-cell> element content differs from the value".
    """
    value_type = cell.get(_VALUE_TYPE)
    holder = _VALUE_ATTRIBUTES.get(value_type)
    value = None if holder is None else cell.get(holder)
    left = set()
    for key in cell.attrib:
        if key == _COLUMNS_REPEATED:
            continue
        if key == _VALUE_TYPE and value_type in _VALUE_ATTRIBUTES:
            continue
        if key == holder and value is not None:
            continue
        left.add(_xml.prefixed(key, _PREFIXES))
    text, text_left = _cell_text(cell)
    left |= text_left
    if value is None:
        return text, left
    if value_type != "string":
        left.add(f"office:value-type {value_type}")
    elif text and text != value:
        left.add(_xml.prefixed(_P, _PREFIXES))
    return value, left


def _cell_text(cell: ElementTree.Element) -> tuple[str, set[str]]:
    """Read a cell's paragraphs, joined by line breaks.

    cell -- one table:table-cell

    Return the text, and what the paragraphs leave behind.
    """
    paragraphs = []
    left: set[str] = set()
    for child in cell:
        if child.tag in (_P, _H):
            if child.tag == _H:
                left.add(_xml.prefixed(child.tag, _PREFIXES))
            left |= _xml.attributes_left_behind(child, (), _PREFIXES)
            text, paragraph_left = _paragraph_text(child)
            paragraphs.append(text)
            left |= paragraph_left
        else:
            left.add(_xml.prefixed(child.tag, _PREFIXES))
    return _LF.join(paragraphs), left


def _paragraph_text(
    paragraph: ElementTree.Element,
) -> tuple[str, set[str]]:
    """Read a paragraph, ODF 1.3 Part 3, 6.1.2 White Space Characters.

    paragraph -- one text:p or text:h

    Return its text, and what it leaves behind.
    """
    tokens, left = _collect(paragraph)
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
    text = "".join(text if kept else _SPACES.sub(_SPACE, text) for kept, text in merged)
    return text, left


def _collect(
    element: ElementTree.Element,
) -> tuple[list[tuple[bool, str]], set[str]]:
    """Flatten paragraph content, steps 1 to 4 of ODF 1.3 Part 3, 6.1.2.

    element -- a paragraph, or an element inside one

    Return (kept, text) tokens, kept for the characters of text:s,
    text:tab and text:line-break, and what the content leaves behind.
    """
    tokens: list[tuple[bool, str]] = []
    left: set[str] = set()
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
            left.add(_xml.prefixed(child.tag, _PREFIXES))
            base = child.find(_RUBY_BASE)
            if base is not None:
                inner, inner_left = _collect(base)
                tokens.extend(inner)
                left |= inner_left
        elif child.tag in _PARAGRAPH_CONTENT:
            left.add(_xml.prefixed(child.tag, _PREFIXES))
            inner, inner_left = _collect(child)
            tokens.extend(inner)
            left |= inner_left
        else:
            left.add(_xml.prefixed(child.tag, _PREFIXES))
        if child.tail:
            tokens.append((False, _to_spaces(child.tail)))
    return tokens, left


def _to_spaces(text: str) -> str:
    """Replace HT, CR and LF with a space, ODF 1.3 Part 3, 6.1.2 step 4.

    text -- character data of a paragraph

    Return the text.
    """
    text = text.replace(_HTAB, _SPACE)
    text = text.replace(_CR, _SPACE)
    return text.replace(_LF, _SPACE)


def _count(value: str, minimum: int) -> int:
    """Read a positiveInteger (minimum 1) or nonNegativeInteger (0).

    value -- the attribute value
    minimum -- 1 or 0

    Return the count. Raise ValueError for anything else.
    """
    digits = value.strip(_XML_SPACE)
    if not _DIGITS.fullmatch(digits) or int(digits) < minimum:
        raise ValueError(f"not a valid ODF count: {value!r}")
    return int(digits)
