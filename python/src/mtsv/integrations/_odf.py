"""The tables of an ODF spreadsheet, shared by both ODF documents.

ODF 1.3 Part 3, 3.1.1: a document is a package or a single XML
document; both hold the same office:body.

Functions:
body -- generate office:body with one table:table per sheet
read_body -- parse the children of a document's root into MTSV sheets

Constants:
OFFICE -- the office namespace
TABLE -- the table namespace
TEXT -- the text namespace
PREFIXES -- the prefix of each namespace, for naming what is left behind
VERSION -- the office:version attribute
ROOT_ATTRIBUTES -- the namespaces and office:version a root writes
MEDIA_TYPE -- the media type of a spreadsheet document
"""

__all__ = [
    "body",
    "read_body",
    "OFFICE",
    "TABLE",
    "TEXT",
    "PREFIXES",
    "VERSION",
    "ROOT_ATTRIBUTES",
    "MEDIA_TYPE",
]

import re
from itertools import groupby
from typing import Any
from xml.etree import ElementTree
from xml.sax.saxutils import escape, quoteattr

from mtsv.integrations import _xml
from mtsv.integrations._sheet import from_lines

MEDIA_TYPE = "application/vnd.oasis.opendocument.spreadsheet"
OFFICE = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
TABLE = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
TEXT = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
PREFIXES = {
    OFFICE: "office",
    TABLE: "table",
    TEXT: "text",
}
ROOT_ATTRIBUTES = (
    f" xmlns:office='{OFFICE}'"
    f" xmlns:table='{TABLE}'"
    f" xmlns:text='{TEXT}'"
    " office:version='1.3'"
)

VERSION = "{" + OFFICE + "}version"
_BODY = "{" + OFFICE + "}body"
_SPREADSHEET = "{" + OFFICE + "}spreadsheet"
_VALUE_TYPE = "{" + OFFICE + "}value-type"
_STRING_VALUE = "{" + OFFICE + "}string-value"
_VALUE = "{" + OFFICE + "}value"
_DATE_VALUE = "{" + OFFICE + "}date-value"
_TIME_VALUE = "{" + OFFICE + "}time-value"
_BOOLEAN_VALUE = "{" + OFFICE + "}boolean-value"
_TABLE_TABLE = "{" + TABLE + "}table"
_NAME = "{" + TABLE + "}name"
_COLUMN = "{" + TABLE + "}table-column"
_COLUMNS = "{" + TABLE + "}table-columns"
_ROW = "{" + TABLE + "}table-row"
_ROWS = "{" + TABLE + "}table-rows"
_WRAPPERS = (
    "{" + TABLE + "}table-header-rows",
    "{" + TABLE + "}table-row-group",
    "{" + TABLE + "}table-header-columns",
    "{" + TABLE + "}table-column-group",
)
_CELL = "{" + TABLE + "}table-cell"
_COVERED_CELL = "{" + TABLE + "}covered-table-cell"
_COLUMNS_REPEATED = "{" + TABLE + "}number-columns-repeated"
_ROWS_REPEATED = "{" + TABLE + "}number-rows-repeated"
_P = "{" + TEXT + "}p"
_H = "{" + TEXT + "}h"
_S = "{" + TEXT + "}s"
_C = "{" + TEXT + "}c"
_TAB = "{" + TEXT + "}tab"
_LINE_BREAK = "{" + TEXT + "}line-break"
_RUBY = "{" + TEXT + "}ruby"
_RUBY_BASE = "{" + TEXT + "}ruby-base"
_PARAGRAPH_CONTENT = (
    "{" + TEXT + "}a",
    "{" + TEXT + "}meta",
    "{" + TEXT + "}meta-field",
    "{" + TEXT + "}span",
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


def body(sheets: list[dict[str, Any]]) -> str:
    """Generate office:body with one table:table per sheet.

    sheets -- the MTSV sheets

    Return its XML.
    """
    tables = "".join(_table(sheet) for sheet in sheets)
    return (
        f"<office:body><office:spreadsheet>{tables}"
        "</office:spreadsheet></office:body>"
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


def read_body(
    root: ElementTree.Element,
) -> tuple[list[dict[str, Any]], set[str]]:
    """Parse the children of a document's root into MTSV sheets.

    root -- the root element of the document

    Return the sheets, and what they leave behind. Raise ValueError for
    a document that is not a spreadsheet.
    """
    left: set[str] = set()
    spreadsheet = None
    for child in root:
        if child.tag == _BODY:
            spreadsheet = child.find(_SPREADSHEET)
        else:
            left.add(_xml.prefixed(child.tag, PREFIXES))
    if spreadsheet is None:
        raise ValueError("the document is not an office:spreadsheet")
    left |= _xml.attributes_left_behind(spreadsheet, (), PREFIXES)
    sheets = []
    for child in spreadsheet:
        if child.tag != _TABLE_TABLE:
            left.add(_xml.prefixed(child.tag, PREFIXES))
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
    left = _xml.attributes_left_behind(element, (_NAME,), PREFIXES)
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
            left |= _xml.attributes_left_behind(child, (_ROWS_REPEATED,), PREFIXES)
            count = _count(child.get(_ROWS_REPEATED, "1"), 1)
            values, cells_left = _cells(child)
            rows.append((count, values))
            left |= cells_left
        elif child.tag == _COLUMN:
            left |= _xml.attributes_left_behind(child, (_COLUMNS_REPEATED,), PREFIXES)
            _count(child.get(_COLUMNS_REPEATED, "1"), 1)
        elif child.tag in (_ROWS, _COLUMNS):
            inner, inner_left = _rows(child)
            rows.extend(inner)
            left |= inner_left
        elif child.tag in _WRAPPERS:
            left.add(_xml.prefixed(child.tag, PREFIXES))
            left |= _xml.attributes_left_behind(child, (), PREFIXES)
            inner, inner_left = _rows(child)
            rows.extend(inner)
            left |= inner_left
        else:
            left.add(_xml.prefixed(child.tag, PREFIXES))
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
            left.add(_xml.prefixed(child.tag, PREFIXES))
            text = ""
        else:
            left.add(_xml.prefixed(child.tag, PREFIXES))
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
        left.add(_xml.prefixed(key, PREFIXES))
    text, text_left = _cell_text(cell)
    left |= text_left
    if value is None:
        return text, left
    if value_type != "string":
        left.add(f"office:value-type {value_type}")
    elif text and text != value:
        left.add(_xml.prefixed(_P, PREFIXES))
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
                left.add(_xml.prefixed(child.tag, PREFIXES))
            left |= _xml.attributes_left_behind(child, (), PREFIXES)
            text, paragraph_left = _paragraph_text(child)
            paragraphs.append(text)
            left |= paragraph_left
        else:
            left.add(_xml.prefixed(child.tag, PREFIXES))
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
            left.add(_xml.prefixed(child.tag, PREFIXES))
            base = child.find(_RUBY_BASE)
            if base is not None:
                inner, inner_left = _collect(base)
                tokens.extend(inner)
                left |= inner_left
        elif child.tag in _PARAGRAPH_CONTENT:
            left.add(_xml.prefixed(child.tag, PREFIXES))
            inner, inner_left = _collect(child)
            tokens.extend(inner)
            left |= inner_left
        else:
            left.add(_xml.prefixed(child.tag, PREFIXES))
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
