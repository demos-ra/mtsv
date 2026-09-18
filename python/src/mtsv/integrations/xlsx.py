"""Convert between MTSV sheets and OOXML workbooks, ISO/IEC 29500.

Functions:
dump -- write MTSV sheets to a binary file as an OOXML workbook
load -- read MTSV sheets from a binary OOXML workbook file
main -- deprecated: convert .mtsv to .xlsx, or .xlsx to .mtsv
"""

__all__ = ["dump", "load", "main"]

import re
import zipfile
from collections.abc import Iterator
from typing import Any, BinaryIO
from xml.etree import ElementTree
from xml.sax.saxutils import escape, quoteattr

import mtsv
import mtsv.integrations
from mtsv import _command
from mtsv.integrations import _xml

_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_CONTENT_TYPES = "http://schemas.openxmlformats.org/package/2006/content-types"
_RELATIONSHIPS = "http://schemas.openxmlformats.org/package/2006/relationships"
_PREFIXES = {_MAIN: "", _R: "r", _RELATIONSHIPS: "", _CONTENT_TYPES: ""}

# Content types and source relationships: ECMA-376 Part 2, 6.5.2.1,
# Part 1, 12.3.15, 12.3.23 and 12.3.24, and Part 4, 10.2.15, 10.2.23
# and 10.2.24.
_RELATIONSHIP_TYPE = "application/vnd.openxmlformats-package.relationships+xml"
_WORKBOOK_TYPE = (
    "application/vnd.openxmlformats-officedocument"
    ".spreadsheetml.sheet.main+xml"
)
_WORKSHEET_TYPE = (
    "application/vnd.openxmlformats-officedocument"
    ".spreadsheetml.worksheet+xml"
)
_SHARED_STRINGS_TYPE = (
    "application/vnd.openxmlformats-officedocument"
    ".spreadsheetml.sharedStrings+xml"
)
_OFFICE_DOCUMENT_REL = _R + "/officeDocument"
_WORKSHEET_REL = _R + "/worksheet"
_SHARED_STRINGS_REL = _R + "/sharedStrings"

_CONTENT_TYPES_PART = "[Content_Types].xml"
_ROOT_RELS = "_rels/.rels"
_WORKBOOK_RELS = "xl/_rels/workbook.xml.rels"
_SHARED_STRINGS = "xl/sharedStrings.xml"

# ECMA-376 Part 2, 6.5.3.4: TargetMode is Internal by default.
_TARGET_MODE = "TargetMode"
_INTERNAL = "Internal"

# ECMA-376 Part 3, 7.1 and 9.4: the Markup Compatibility namespace, and
# the attributes an MCE processor removes from every element.
_MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
_MCE_ATTRIBUTES = (
    "{" + _MC + "}Ignorable",
    "{" + _MC + "}ProcessContent",
    "{" + _MC + "}MustUnderstand",
)

_SHEETS = "{" + _MAIN + "}sheets"
_SHEET = "{" + _MAIN + "}sheet"
_SHEET_DATA = "{" + _MAIN + "}sheetData"
_ROW = "{" + _MAIN + "}row"
_CELL = "{" + _MAIN + "}c"
_VALUE = "{" + _MAIN + "}v"
_INLINE = "{" + _MAIN + "}is"
_SST = "{" + _MAIN + "}sst"
_SI = "{" + _MAIN + "}si"
_TEXT = "{" + _MAIN + "}t"
_RUN = "{" + _MAIN + "}r"
_RELATIONSHIP = "{" + _RELATIONSHIPS + "}Relationship"
_ID = "{" + _R + "}id"
_NAME = "name"
_SHEET_ID = "sheetId"
_REFERENCE = "r"
_TYPE = "t"

# The cell types that carry text, ISO/IEC 29500 ST_CellType.
_TEXT_TYPES = ("s", "str", "inlineStr")

# The grid of Part 1, 18.17.5.1: columns A to XFD, rows 1 to 1048576.
_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_COLUMNS = 16384
_ROWS = 1048576

_DIGITS = re.compile("[0-9]+")


def dump(obj: list[dict[str, Any]], fp: BinaryIO) -> None:
    """Write MTSV sheets to a binary file as an OOXML workbook.

    Raise ValueError if the sheets are not MTSV, if the file has no
    sheets, if a sheet is wider or longer than the grid, or if a field
    or sheet name holds a character that XML 1.0 does not allow.
    """
    mtsv.dumps(obj)
    if not obj:
        raise ValueError(
            "a workbook holds at least one sheet, so an MTSV file of no"
            " sheets cannot be represented in XLSX"
        )
    for sheet in obj:
        lines = _lines(sheet)
        if len(lines) > _ROWS:
            raise ValueError(
                f"a worksheet holds at most {_ROWS} rows, so a longer"
                " sheet cannot be represented in XLSX"
            )
        if lines and len(lines[0]) > _COLUMNS:
            raise ValueError(
                f"a worksheet holds at most {_COLUMNS} columns, so a"
                " wider sheet cannot be represented in XLSX"
            )
    _xml.check_chars(obj, "XLSX")
    with zipfile.ZipFile(fp, "w", zipfile.ZIP_DEFLATED) as package:
        package.writestr(_CONTENT_TYPES_PART, _content_types(len(obj)))
        package.writestr(_ROOT_RELS, _root_relationships())
        package.writestr("xl/workbook.xml", _workbook(obj))
        package.writestr(_WORKBOOK_RELS, _workbook_relationships(len(obj)))
        package.writestr(_SHARED_STRINGS, _shared_string_table())
        for index, sheet in enumerate(obj):
            package.writestr(
                f"xl/worksheets/sheet{index + 1}.xml", _worksheet(sheet)
            )


def load(fp: BinaryIO, /, errors: str = "strict") -> list[dict[str, Any]]:
    """Read MTSV sheets from a binary OOXML workbook file.

    With errors="strict", raise ValueError if anything outside MTSV
    would be left behind. With errors="ignore", leave it behind. Raise
    ValueError for a file that is not an OOXML workbook.
    """
    mtsv.integrations._errors(errors)
    extras: set[str] = set()
    try:
        with zipfile.ZipFile(fp) as package:
            sheets = _package(package, extras)
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as error:
        raise ValueError("the file is not an OOXML package") from error
    mtsv.integrations.report(extras, errors)
    mtsv.dumps(sheets)
    return sheets


def main(argv: list[str] | None = None) -> None:
    """Convert a .mtsv file to .xlsx, or an .xlsx file to .mtsv.

    Deprecated; to be removed in 0.5.0. Semantic Versioning, "How
    should I handle deprecating functionality?"
    """
    _command.run(
        "python -m mtsv.integrations.xlsx",
        "Convert a .mtsv file to .xlsx, or .xlsx to .mtsv.",
        (".xlsx",),
        argv,
    )


def _lines(sheet: dict[str, Any]) -> list[list[str]]:
    """Return the lines of a sheet; an empty sheet has none."""
    if sheet["header"] is None:
        return []
    return [sheet["header"], *sheet["records"]]


def _content_types(count: int) -> str:
    """Generate [Content_Types].xml, per ECMA-376 Part 2.

    Every part is covered by the rels default or by its own override.
    """
    overrides = "".join(
        f"<Override PartName='/xl/worksheets/sheet{index + 1}.xml'"
        f" ContentType='{_WORKSHEET_TYPE}'/>"
        for index in range(count)
    )
    return (
        "<?xml version='1.0' encoding='UTF-8'?>"
        f"<Types xmlns='{_CONTENT_TYPES}'>"
        f"<Default Extension='rels' ContentType='{_RELATIONSHIP_TYPE}'/>"
        f"<Override PartName='/xl/workbook.xml'"
        f" ContentType='{_WORKBOOK_TYPE}'/>"
        f"<Override PartName='/{_SHARED_STRINGS}'"
        f" ContentType='{_SHARED_STRINGS_TYPE}'/>"
        f"{overrides}</Types>"
    )


def _root_relationships() -> str:
    """Generate _rels/.rels, which names the workbook part."""
    return (
        "<?xml version='1.0' encoding='UTF-8'?>"
        f"<Relationships xmlns='{_RELATIONSHIPS}'>"
        f"<Relationship Id='rId1' Type='{_OFFICE_DOCUMENT_REL}'"
        " Target='xl/workbook.xml'/>"
        "</Relationships>"
    )


def _workbook_relationships(count: int) -> str:
    """Generate xl/_rels/workbook.xml.rels.

    One entry per worksheet, then the shared string table, which Part 1,
    12.3.15 makes the target of a relationship from the workbook.
    """
    entries = "".join(
        f"<Relationship Id='rId{index + 1}' Type='{_WORKSHEET_REL}'"
        f" Target='worksheets/sheet{index + 1}.xml'/>"
        for index in range(count)
    )
    return (
        "<?xml version='1.0' encoding='UTF-8'?>"
        f"<Relationships xmlns='{_RELATIONSHIPS}'>{entries}"
        f"<Relationship Id='rId{count + 1}' Type='{_SHARED_STRINGS_REL}'"
        " Target='sharedStrings.xml'/>"
        "</Relationships>"
    )


def _shared_string_table() -> str:
    """Generate xl/sharedStrings.xml, a table of no strings.

    Part 1, 12.3.15: a package contains exactly one shared string
    table.
    """
    return (
        "<?xml version='1.0' encoding='UTF-8'?>"
        f"<sst xmlns='{_MAIN}'/>"
    )


def _workbook(sheets: list[dict[str, Any]]) -> str:
    """Generate xl/workbook.xml; sheet order is the order written."""
    entries = "".join(
        f"<sheet name={quoteattr(sheet['sheet name'])}"
        f" sheetId='{index + 1}' r:id='rId{index + 1}'/>"
        for index, sheet in enumerate(sheets)
    )
    return (
        "<?xml version='1.0' encoding='UTF-8'?>"
        f"<workbook xmlns='{_MAIN}' xmlns:r='{_R}'>"
        f"<sheets>{entries}</sheets></workbook>"
    )


def _worksheet(sheet: dict[str, Any]) -> str:
    """Generate a worksheet; an empty sheet holds no rows."""
    rows = "".join(
        _row(fields, number)
        for number, fields in enumerate(_lines(sheet), 1)
    )
    return (
        "<?xml version='1.0' encoding='UTF-8'?>"
        f"<worksheet xmlns='{_MAIN}'>"
        f"<sheetData>{rows}</sheetData></worksheet>"
    )


def _row(fields: list[str], number: int) -> str:
    """Generate a row, numbered from one."""
    cells = "".join(
        _cell(value, _reference(column, number))
        for column, value in enumerate(fields, 1)
    )
    return f"<row r='{number}'>{cells}</row>"


def _cell(value: str, reference: str) -> str:
    """Generate a cell of inline text; an empty field has no value."""
    if not value:
        return f"<c r='{reference}'/>"
    return (
        f"<c r='{reference}' t='inlineStr'>"
        f"<is><t xml:space='preserve'>{escape(value)}</t></is></c>"
    )


def _reference(column: int, row: int) -> str:
    """Return the A1 reference of a position, Part 1, 18.17.5.1.

    Columns count from A in a bijective base 26, so that column 26 is
    Z, column 27 is AA, and column 16384 is XFD.
    """
    letters = ""
    while column:
        column, index = divmod(column - 1, len(_LETTERS))
        letters = _LETTERS[index] + letters
    return letters + str(row)


def _column(reference: str) -> int:
    """Return the column of an A1 reference, counting from one."""
    column = 0
    for char in reference:
        if char not in _LETTERS:
            break
        column = column * len(_LETTERS) + _LETTERS.index(char) + 1
    return column


def _package(
    package: zipfile.ZipFile, extras: set[str], /
) -> list[dict[str, Any]]:
    """Read a package into MTSV sheets, through its relationships.

    Record every part the mapping does not read as left behind.
    """
    workbook = _part(_relationships(package, "/"), _OFFICE_DOCUMENT_REL)
    relationships = _relationships(package, workbook)
    used = {
        _CONTENT_TYPES_PART,
        _zip_name(_relationships_part("/")),
        _zip_name(workbook),
        _zip_name(_relationships_part(workbook)),
    }
    strings: list[str] = []
    if any(kind == _SHARED_STRINGS_REL for kind, _ in relationships.values()):
        table = _part(relationships, _SHARED_STRINGS_REL)
        used.add(_zip_name(table))
        strings = _shared_strings(package, table, extras)
    root = ElementTree.fromstring(package.read(_zip_name(workbook)))
    _xml.note_attributes(root, _MCE_ATTRIBUTES, extras, _PREFIXES)
    sheets = []
    for child in root:
        if child.tag != _SHEETS:
            extras.add(_xml.prefixed(child.tag, _PREFIXES))
            continue
        for entry in child:
            if entry.tag != _SHEET:
                extras.add(_xml.prefixed(entry.tag, _PREFIXES))
                continue
            part = relationships[entry.get(_ID)][1]
            used.add(_zip_name(part))
            sheets.append(_sheet(entry, package, part, strings, extras))
    for name in package.namelist():
        if name not in used:
            extras.add(name)
    return sheets


def _relationships(
    package: zipfile.ZipFile, source: str
) -> dict[str, tuple[str, str]]:
    """Map each internal relationship Id of a source to type and part.

    ECMA-376 Part 2, 6.5.3.4: a Target is resolved against its source.
    """
    name = _zip_name(_relationships_part(source))
    root = ElementTree.fromstring(package.read(name))
    return {
        entry.get("Id"): (
            entry.get("Type"),
            _resolve(source, entry.get("Target")),
        )
        for entry in root
        if entry.tag == _RELATIONSHIP
        and entry.get(_TARGET_MODE, _INTERNAL) == _INTERNAL
    }


def _part(relationships: dict[str, tuple[str, str]], kind: str) -> str:
    """Return the part that the first relationship of a type targets."""
    for relationship, part in relationships.values():
        if relationship == kind:
            return part
    raise ValueError(f"the package has no {kind} relationship")


def _relationships_part(source: str) -> str:
    """Return the name of a source's Relationships part.

    ECMA-376 Part 2, 6.5.2.2 and 6.5.2.3: "_rels" is inserted before
    the last segment, and ".rels" is added to it.
    """
    folder, _, last = source.rpartition("/")
    return f"{folder}/_rels/{last}.rels"


def _resolve(source: str, target: str) -> str:
    """Resolve an internal Target to a part name, RFC 3986, 5.2.2.

    ECMA-376 Part 2, 6.5.3.4: an internal Target is a relative
    reference. A Target with a scheme or an authority is refused.
    """
    if target.startswith("//") or ":" in target.split("/", 1)[0]:
        raise ValueError(f"target {target!r} is not a relative reference")
    if not target:
        path = source
    elif target.startswith("/"):
        path = target
    else:
        path = source[: source.rfind("/") + 1] + target
    return _remove_dot_segments(path)


def _remove_dot_segments(path: str) -> str:
    """Remove "." and ".." segments from a path, RFC 3986, 5.2.4."""
    segments = path.split("/")[1:]
    output: list[str] = []
    for segment in segments:
        if segment == "..":
            if output:
                output.pop()
        elif segment != ".":
            output.append(segment)
    if segments and segments[-1] in (".", ".."):
        output.append("")
    return "/" + "/".join(output)


def _zip_name(part: str) -> str:
    """Return the ZIP item name of a part name, Part 2, 7.3.4.

    The leading "/" is removed, and every non-ASCII character is
    percent-encoded.
    """
    return "".join(
        char
        if char.isascii()
        else "".join(f"%{byte:02X}" for byte in char.encode("utf-8"))
        for char in part[1:]
    )


def _sheet(
    entry: ElementTree.Element,
    package: zipfile.ZipFile,
    part: str,
    strings: list[str],
    extras: set[str],
) -> dict[str, Any]:
    """Read one sheet, named in the workbook, held in its own part."""
    _xml.note_attributes(entry, (_NAME, _SHEET_ID, _ID), extras, _PREFIXES)
    name = entry.get(_NAME)
    root = ElementTree.fromstring(package.read(_zip_name(part)))
    _xml.note_attributes(root, _MCE_ATTRIBUTES, extras, _PREFIXES)
    lines: list[list[str]] = []
    for child in root:
        if child.tag != _SHEET_DATA:
            extras.add(_xml.prefixed(child.tag, _PREFIXES))
            continue
        lines.extend(_rows(child, strings, extras))
    return mtsv.integrations._sheet(name, lines)


def _rows(
    element: ElementTree.Element, strings: list[str], extras: set[str]
) -> Iterator[list[str]]:
    """Yield the values of each row of a sheetData, in order."""
    for child in element:
        if child.tag != _ROW:
            extras.add(_xml.prefixed(child.tag, _PREFIXES))
            continue
        _xml.note_attributes(child, (_REFERENCE,), extras, _PREFIXES)
        yield _cells(child, strings, extras)


def _cells(
    row: ElementTree.Element, strings: list[str], extras: set[str]
) -> list[str]:
    """Read a row's cell values, at the positions the cells give.

    A cell that a row leaves out is an empty field; a cell that a row
    writes is kept, empty or not.
    """
    values: dict[int, str] = {}
    position = 0
    for child in row:
        if child.tag != _CELL:
            extras.add(_xml.prefixed(child.tag, _PREFIXES))
            continue
        reference = child.get(_REFERENCE)
        position = position + 1 if reference is None else _column(reference)
        if position < 1 or position in values:
            raise ValueError(
                f"cell {reference!r} does not give a free column of its row"
            )
        values[position] = _cell_value(child, strings, extras)
    width = max(values, default=0)
    return [values.get(column, "") for column in range(1, width + 1)]


def _cell_value(
    cell: ElementTree.Element, strings: list[str], extras: set[str]
) -> str:
    """Read a cell's value, per ISO/IEC 29500 ST_CellType.

    A type other than s, str or inlineStr is left behind. A cell that
    carries no value leaves nothing behind, whatever its type says.
    """
    _xml.note_attributes(cell, (_REFERENCE, _TYPE), extras, _PREFIXES)
    cell_type = cell.get(_TYPE, "n")
    text = None
    for child in cell:
        if child.tag == _VALUE:
            text = child.text or ""
        elif child.tag == _INLINE:
            text = _rst_text(child, extras)
        else:
            extras.add(_xml.prefixed(child.tag, _PREFIXES))
    if text is None:
        return ""
    if cell_type not in _TEXT_TYPES:
        extras.add(f"cell type {cell_type}")
    if cell_type == "s":
        if not _DIGITS.fullmatch(text) or int(text) >= len(strings):
            raise ValueError(f"no shared string {text!r}")
        return strings[int(text)]
    return text


def _shared_strings(
    package: zipfile.ZipFile, part: str, extras: set[str]
) -> list[str]:
    """Read the shared string table that the workbook points to."""
    root = ElementTree.fromstring(package.read(_zip_name(part)))
    if root.tag != _SST:
        raise ValueError("the shared string part is not an sst")
    _xml.note_attributes(root, _MCE_ATTRIBUTES, extras, _PREFIXES)
    strings = []
    for child in root:
        if child.tag == _SI:
            strings.append(_rst_text(child, extras))
        else:
            extras.add(_xml.prefixed(child.tag, _PREFIXES))
    return strings


def _rst_text(element: ElementTree.Element, extras: set[str]) -> str:
    """Read a rich string as text, joining its runs in order."""
    parts = []
    for child in element:
        if child.tag == _TEXT:
            parts.append(child.text or "")
        elif child.tag == _RUN:
            for part in child:
                if part.tag == _TEXT:
                    parts.append(part.text or "")
                else:
                    extras.add(_xml.prefixed(part.tag, _PREFIXES))
        else:
            extras.add(_xml.prefixed(child.tag, _PREFIXES))
    return "".join(parts)


if __name__ == "__main__":
    main()
