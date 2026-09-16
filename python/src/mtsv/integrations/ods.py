"""Convert between MTSV sheets and OpenDocument spreadsheets, ODF 1.3.

Functions:
dump -- write MTSV sheets to a binary file as an ODF spreadsheet
load -- read MTSV sheets from a binary ODF spreadsheet file
main -- convert a .mtsv file to .ods, or an .ods file to .mtsv
"""

__all__ = ["dump", "load", "main"]

import argparse
import io
import re
import zipfile
from collections.abc import Iterator
from itertools import groupby
from pathlib import Path
from typing import Any, BinaryIO
from xml.etree import ElementTree
from xml.sax.saxutils import escape, quoteattr

import mtsv

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
    for sheet in obj:
        values = [sheet["sheet name"] or ""]
        for fields in [sheet["header"] or [], *sheet["records"]]:
            values.extend(fields)
        for value in values:
            if not all(_xml_char(char) for char in value):
                raise ValueError(
                    "a field or sheet name that contains a character not"
                    " allowed in XML 1.0 cannot be represented in ODS"
                )
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
    if errors not in ("strict", "ignore"):
        raise LookupError(f"unknown error handler name {errors!r}")
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
    if errors == "strict" and extras:
        raise ValueError(
            "these would be left behind: " + ", ".join(sorted(extras))
        )
    mtsv.dumps(sheets)
    return sheets


def main(argv: list[str] | None = None) -> None:
    """Convert a .mtsv file to .ods, or an .ods file to .mtsv."""
    parser = argparse.ArgumentParser(
        prog="python -m mtsv.integrations.ods",
        description="Convert a .mtsv file to .ods, or an .ods file to .mtsv.",
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--errors", choices=["strict", "ignore"], default="strict"
    )
    args = parser.parse_args(argv)
    suffixes = (args.input.suffix, args.output.suffix)
    buffer = io.BytesIO()
    try:
        if suffixes == (".mtsv", ".ods"):
            with args.input.open("rb") as source:
                dump(mtsv.load(source), buffer)
        elif suffixes == (".ods", ".mtsv"):
            with args.input.open("rb") as source:
                mtsv.dump(load(source, args.errors), buffer)
        else:
            parser.error("convert a .mtsv file to .ods, or .ods to .mtsv")
    except ValueError as error:
        raise SystemExit(error)
    args.output.write_bytes(buffer.getvalue())


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
    name = sheet["sheet name"]
    attribute = "" if name is None else " table:name=" + quoteattr(name)
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
    """Generate text:p content, with spaces marked per ODF 6.1.2-6.1.3.

    A single space between other characters stays a space; every other
    space is written with text:s, so collapsing cannot remove it.
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


def _xml_char(char: str) -> bool:
    """Match XML 1.0 Char.

    Char ::= #x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD]
             | [#x10000-#x10FFFF]
    """
    code = ord(char)
    return (
        code in (0x09, 0x0A, 0x0D)
        or 0x20 <= code <= 0xD7FF
        or 0xE000 <= code <= 0xFFFD
        or 0x10000 <= code <= 0x10FFFF
    )


def _prefixed(name: str) -> str:
    """Return {namespace}local as prefix:local for known prefixes."""
    if not name.startswith("{"):
        return name
    namespace, local = name[1:].split("}", 1)
    prefix = _PREFIXES.get(namespace)
    return name if prefix is None else f"{prefix}:{local}"


def _note_attributes(
    element: ElementTree.Element, allowed: tuple[str, ...], extras: set[str]
) -> None:
    """Record each attribute outside the MTSV mapping as left behind."""
    for key in element.attrib:
        if key not in allowed:
            extras.add(_prefixed(key))


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
    _note_attributes(root, (_VERSION,), extras)
    spreadsheet = None
    for child in root:
        if child.tag == _BODY:
            spreadsheet = child.find(_SPREADSHEET)
        else:
            extras.add(_prefixed(child.tag))
    if spreadsheet is None:
        raise ValueError("the document is not an office:spreadsheet")
    _note_attributes(spreadsheet, (), extras)
    sheets = []
    for child in spreadsheet:
        if child.tag != _TABLE_TABLE:
            extras.add(_prefixed(child.tag))
            continue
        sheets.append(_sheet(child, extras))
    return sheets


def _sheet(element: ElementTree.Element, extras: set[str]) -> dict[str, Any]:
    """Parse table:table into a sheet, reading only its used area."""
    _note_attributes(element, (_NAME,), extras)
    name = element.get(_NAME)
    lines: list[list[str]] = []
    pending = 0
    for count, values in _rows(element, extras):
        if values:
            lines.extend([] for _ in range(pending))
            pending = 0
            lines.extend(list(values) for _ in range(count))
        else:
            pending += count
    if not lines:
        return {"sheet name": name, "header": None, "records": []}
    width = max(len(values) for values in lines)
    padded = [values + [""] * (width - len(values)) for values in lines]
    return {"sheet name": name, "header": padded[0], "records": padded[1:]}


def _rows(
    element: ElementTree.Element, extras: set[str]
) -> Iterator[tuple[int, list[str]]]:
    """Yield (repeat count, values) per row, reading into wrappers."""
    for child in element:
        if child.tag == _ROW:
            _note_attributes(child, (_ROWS_REPEATED,), extras)
            count = _count(child.get(_ROWS_REPEATED, "1"), 1)
            yield count, _cells(child, extras)
        elif child.tag == _COLUMN:
            _note_attributes(child, (_COLUMNS_REPEATED,), extras)
            _count(child.get(_COLUMNS_REPEATED, "1"), 1)
        elif child.tag in (_ROWS, _COLUMNS):
            yield from _rows(child, extras)
        elif child.tag in _WRAPPERS:
            extras.add(_prefixed(child.tag))
            _note_attributes(child, (), extras)
            yield from _rows(child, extras)
        else:
            extras.add(_prefixed(child.tag))


def _cells(row: ElementTree.Element, extras: set[str]) -> list[str]:
    """Read a row's cell texts, without its trailing empty cells."""
    values: list[str] = []
    pending = 0
    for child in row:
        if child.tag == _CELL:
            text = _cell_value(child, extras)
        elif child.tag == _COVERED_CELL:
            extras.add(_prefixed(child.tag))
            text = ""
        else:
            extras.add(_prefixed(child.tag))
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
    """Read a cell's text, from office:string-value when it is given."""
    is_string = cell.get(_VALUE_TYPE) == "string"
    for key in cell.attrib:
        if key == _COLUMNS_REPEATED:
            continue
        if is_string and key in (_VALUE_TYPE, _STRING_VALUE):
            continue
        extras.add(_prefixed(key))
    text = _cell_text(cell, extras)
    value = cell.get(_STRING_VALUE)
    if not is_string or value is None:
        return text
    if text and text != value:
        extras.add(_prefixed(_P))
    return value


def _cell_text(cell: ElementTree.Element, extras: set[str]) -> str:
    """Read a cell's paragraphs, joined by line breaks."""
    paragraphs = []
    for child in cell:
        if child.tag in (_P, _H):
            if child.tag == _H:
                extras.add(_prefixed(child.tag))
            _note_attributes(child, (), extras)
            paragraphs.append(_paragraph_text(child, extras))
        else:
            extras.add(_prefixed(child.tag))
    return _LF.join(paragraphs)


def _paragraph_text(paragraph: ElementTree.Element, extras: set[str]) -> str:
    """Read a paragraph per the white space algorithm, ODF 6.1.2."""
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
            extras.add(_prefixed(child.tag))
            base = child.find(_RUBY_BASE)
            if base is not None:
                _collect(base, tokens, extras)
        elif child.tag in _PARAGRAPH_CONTENT:
            extras.add(_prefixed(child.tag))
            _collect(child, tokens, extras)
        else:
            extras.add(_prefixed(child.tag))
        if child.tail:
            tokens.append((False, _to_spaces(child.tail)))


def _to_spaces(text: str) -> str:
    """Replace HT, CR, and LF with a space, step 4 of ODF 1.3, 6.1.2."""
    text = text.replace(_HTAB, _SPACE)
    text = text.replace(_CR, _SPACE)
    return text.replace(_LF, _SPACE)


if __name__ == "__main__":
    main()
