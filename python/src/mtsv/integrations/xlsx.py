"""Convert between MTSV sheets and OOXML workbooks, ISO/IEC 29500.

Functions:
dump -- write MTSV sheets to a binary file as an OOXML workbook
load -- read MTSV sheets from a binary OOXML workbook file
main -- convert a .mtsv file to .xlsx, or an .xlsx file to .mtsv
"""

__all__ = ["dump", "load", "main"]

import zipfile
from collections.abc import Iterator
from typing import Any, BinaryIO
from xml.etree import ElementTree
from xml.sax.saxutils import escape, quoteattr

import mtsv
from mtsv import _command

_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_CONTENT_TYPES = "http://schemas.openxmlformats.org/package/2006/content-types"
_RELATIONSHIPS = "http://schemas.openxmlformats.org/package/2006/relationships"
_PREFIXES = {_MAIN: "", _R: "r", _RELATIONSHIPS: "", _CONTENT_TYPES: ""}

# Content types and source relationships: ECMA-376 Part 2, 6.5.2.1,
# Part 1, 12.3.23 and 12.3.24, and Part 4, 10.2.23 and 10.2.24.
_RELATIONSHIP_TYPE = "application/vnd.openxmlformats-package.relationships+xml"
_WORKBOOK_TYPE = (
    "application/vnd.openxmlformats-officedocument"
    ".spreadsheetml.sheet.main+xml"
)
_WORKSHEET_TYPE = (
    "application/vnd.openxmlformats-officedocument"
    ".spreadsheetml.worksheet+xml"
)
_OFFICE_DOCUMENT_REL = _R + "/officeDocument"
_WORKSHEET_REL = _R + "/worksheet"

_CONTENT_TYPES_PART = "[Content_Types].xml"
_ROOT_RELS = "_rels/.rels"
_WORKBOOK_RELS = "xl/_rels/workbook.xml.rels"
_SHARED_STRINGS = "xl/sharedStrings.xml"

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


def dump(obj: list[dict[str, Any]], fp: BinaryIO) -> None:
    """Write MTSV sheets to a binary file as an OOXML workbook.

    Raise ValueError if the sheets are not MTSV, if the file has no
    sheets, if a sheet is unnamed, if a sheet is wider or longer than
    the grid, or if a field or sheet name holds a character that XML
    1.0 does not allow.
    """
    mtsv.dumps(obj)
    if not obj:
        raise ValueError(
            "a workbook holds at least one sheet, so an MTSV file of no"
            " sheets cannot be represented in XLSX"
        )
    for sheet in obj:
        if sheet["sheet name"] is None:
            raise ValueError(
                "every sheet of a workbook has a name, so the unnamed"
                " sheet cannot be represented in XLSX"
            )
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
        values = [sheet["sheet name"]]
        for fields in lines:
            values.extend(fields)
        for value in values:
            if not all(_xml_char(char) for char in value):
                raise ValueError(
                    "a field or sheet name that contains a character not"
                    " allowed in XML 1.0 cannot be represented in XLSX"
                )
    with zipfile.ZipFile(fp, "w", zipfile.ZIP_DEFLATED) as package:
        package.writestr(_CONTENT_TYPES_PART, _content_types(len(obj)))
        package.writestr(_ROOT_RELS, _root_relationships())
        package.writestr("xl/workbook.xml", _workbook(obj))
        package.writestr(_WORKBOOK_RELS, _workbook_relationships(len(obj)))
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
    if errors not in ("strict", "ignore"):
        raise LookupError(f"unknown error handler name {errors!r}")
    extras: set[str] = set()
    try:
        with zipfile.ZipFile(fp) as package:
            sheets = _package(package, extras)
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as error:
        raise ValueError("the file is not an OOXML package") from error
    if errors == "strict" and extras:
        raise ValueError(
            "these would be left behind: " + ", ".join(sorted(extras))
        )
    mtsv.dumps(sheets)
    return sheets


def main(argv: list[str] | None = None) -> None:
    """Convert a .mtsv file to .xlsx, or an .xlsx file to .mtsv."""
    _command.run(
        "python -m mtsv.integrations.xlsx",
        "Convert a .mtsv file to .xlsx, or .xlsx to .mtsv.",
        {".xlsx": (load, dump)},
        argv,
    )


def _lines(sheet: dict[str, Any]) -> list[list[str]]:
    """Return the lines of a sheet; an empty sheet has none."""
    if sheet["header"] is None:
        return []
    return [sheet["header"], *sheet["records"]]


def _content_types(count: int) -> str:
    """Generate [Content_Types].xml, per ECMA-376 Part 2.

    Every part is covered by the rels default or by its own override,
    so no default is needed for the xml extension.
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
    """Generate xl/_rels/workbook.xml.rels, one entry per worksheet."""
    entries = "".join(
        f"<Relationship Id='rId{index + 1}' Type='{_WORKSHEET_REL}'"
        f" Target='worksheets/sheet{index + 1}.xml'/>"
        for index in range(count)
    )
    return (
        "<?xml version='1.0' encoding='UTF-8'?>"
        f"<Relationships xmlns='{_RELATIONSHIPS}'>{entries}"
        "</Relationships>"
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
    """Generate a cell; MTSV holds text, so a cell is inline text.

    An empty field is a cell that carries no value.
    """
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
    if prefix is None:
        return name
    return local if not prefix else f"{prefix}:{local}"


def _note_attributes(
    element: ElementTree.Element, allowed: tuple[str, ...], extras: set[str]
) -> None:
    """Record each attribute outside the MTSV mapping as left behind."""
    for key in element.attrib:
        if key not in allowed:
            extras.add(_prefixed(key))


def _package(
    package: zipfile.ZipFile, extras: set[str], /
) -> list[dict[str, Any]]:
    """Read a package into MTSV sheets, through its relationships.

    Record every part the mapping does not read as left behind.
    """
    part = _target(package, _ROOT_RELS, _OFFICE_DOCUMENT_REL, "")
    used = {_CONTENT_TYPES_PART, _ROOT_RELS, _WORKBOOK_RELS, part}
    strings = _shared_strings(package, extras)
    if _SHARED_STRINGS in package.namelist():
        used.add(_SHARED_STRINGS)
    root = ElementTree.fromstring(package.read(part))
    targets = _targets(package)
    sheets = []
    for child in root:
        if child.tag != _SHEETS:
            extras.add(_prefixed(child.tag))
            continue
        for entry in child:
            if entry.tag != _SHEET:
                extras.add(_prefixed(entry.tag))
                continue
            used.add(targets[entry.get(_ID)])
            sheets.append(_sheet(entry, package, targets, strings, extras))
    for name in package.namelist():
        if name not in used:
            extras.add(name)
    return sheets


def _target(
    package: zipfile.ZipFile, part: str, relationship: str, base: str
) -> str:
    """Return the part that a relationship of that type points to."""
    root = ElementTree.fromstring(package.read(part))
    for entry in root:
        if entry.tag == _RELATIONSHIP and entry.get("Type") == relationship:
            return base + entry.get("Target")
    raise ValueError(f"the package has no {relationship} relationship")


def _targets(package: zipfile.ZipFile) -> dict[str, str]:
    """Map each relationship Id of the workbook to its part name."""
    root = ElementTree.fromstring(package.read(_WORKBOOK_RELS))
    return {
        entry.get("Id"): "xl/" + entry.get("Target")
        for entry in root
        if entry.tag == _RELATIONSHIP
    }


def _sheet(
    entry: ElementTree.Element,
    package: zipfile.ZipFile,
    targets: dict[str, str],
    strings: list[str],
    extras: set[str],
) -> dict[str, Any]:
    """Read one sheet, named in the workbook, held in its own part.

    MTSV carries the name and the order; sheetId and r:id are what the
    format needs to hold itself together, as office:version is in ODS.
    """
    _note_attributes(entry, (_NAME, _SHEET_ID, _ID), extras)
    name = entry.get(_NAME)
    root = ElementTree.fromstring(package.read(targets[entry.get(_ID)]))
    lines: list[list[str]] = []
    for child in root:
        if child.tag != _SHEET_DATA:
            extras.add(_prefixed(child.tag))
            continue
        lines.extend(_rows(child, strings, extras))
    if not lines:
        return {"sheet name": name, "header": None, "records": []}
    width = max(len(values) for values in lines)
    padded = [values + [""] * (width - len(values)) for values in lines]
    return {"sheet name": name, "header": padded[0], "records": padded[1:]}


def _rows(
    element: ElementTree.Element, strings: list[str], extras: set[str]
) -> Iterator[list[str]]:
    """Yield the values of each row of a sheetData, in order."""
    for child in element:
        if child.tag != _ROW:
            extras.add(_prefixed(child.tag))
            continue
        _note_attributes(child, (_REFERENCE,), extras)
        yield _cells(child, strings, extras)


def _cells(
    row: ElementTree.Element, strings: list[str], extras: set[str]
) -> list[str]:
    """Read a row's cell values, at the positions the cells give.

    A cell that a row leaves out is an empty field, but a cell that a
    row writes is kept, empty or not: OOXML may omit a cell entirely,
    so writing one is itself the signal that the field is there.
    """
    values: list[str] = []
    for child in row:
        if child.tag != _CELL:
            extras.add(_prefixed(child.tag))
            continue
        reference = child.get(_REFERENCE)
        if reference is not None:
            position = _column(reference)
            values.extend([""] * (position - 1 - len(values)))
        values.append(_cell_value(child, strings, extras))
    return values


def _cell_value(
    cell: ElementTree.Element, strings: list[str], extras: set[str]
) -> str:
    """Read a cell's value, per ISO/IEC 29500 ST_CellType.

    A type other than s, str or inlineStr holds a value whose type
    MTSV cannot hold, so that type is itself left behind. A cell that
    carries no value leaves nothing behind, whatever its type says.
    """
    _note_attributes(cell, (_REFERENCE, _TYPE), extras)
    cell_type = cell.get(_TYPE, "n")
    text = None
    for child in cell:
        if child.tag == _VALUE:
            text = child.text or ""
        elif child.tag == _INLINE:
            text = _rst_text(child, extras)
        else:
            extras.add(_prefixed(child.tag))
    if text is None:
        return ""
    if cell_type not in _TEXT_TYPES:
        extras.add(f"cell type {cell_type}")
    if cell_type == "s":
        return strings[int(text)]
    return text


def _shared_strings(package: zipfile.ZipFile, extras: set[str]) -> list[str]:
    """Read the shared string table, which a workbook may not have."""
    if _SHARED_STRINGS not in package.namelist():
        return []
    root = ElementTree.fromstring(package.read(_SHARED_STRINGS))
    if root.tag != _SST:
        raise ValueError("the shared string part is not an sst")
    strings = []
    for child in root:
        if child.tag == _SI:
            strings.append(_rst_text(child, extras))
        else:
            extras.add(_prefixed(child.tag))
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
                    extras.add(_prefixed(part.tag))
        else:
            extras.add(_prefixed(child.tag))
    return "".join(parts)


if __name__ == "__main__":
    main()
