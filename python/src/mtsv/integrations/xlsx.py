"""Convert between MTSV sheets and OOXML workbooks, ECMA-376.

Functions:
dump -- write MTSV sheets to a binary file as an OOXML workbook
load -- read MTSV sheets from a binary OOXML workbook file
"""

__all__ = ["dump", "load"]

import re
import zipfile
from typing import Any, BinaryIO
from xml.etree import ElementTree
from xml.sax.saxutils import escape, quoteattr

import mtsv
from mtsv.integrations import _errors, _xml
from mtsv.integrations._sheet import from_lines

_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_CONTENT_TYPES = "http://schemas.openxmlformats.org/package/2006/content-types"
_RELATIONSHIPS = "http://schemas.openxmlformats.org/package/2006/relationships"
_PREFIXES = {_MAIN: "", _R: "r", _RELATIONSHIPS: "", _CONTENT_TYPES: ""}

# Content types: ECMA-376 Part 2, 6.5.2.1, and Part 1, 12.3.15, 12.3.23
# and 12.3.24. Root namespace and source relationships of the
# Transitional parts: Part 4, 10.2.15, 10.2.23 and 10.2.24.
_RELATIONSHIP_TYPE = "application/vnd.openxmlformats-package.relationships+xml"
_WORKBOOK_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"
)
_WORKSHEET_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"
)
_SHARED_STRINGS_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"
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

# ECMA-376 Part 4, sml.xsd, ST_CellType: the cell types that carry text.
_TEXT_TYPES = ("s", "str", "inlineStr")

# ECMA-376 Part 1, 18.17.5.1: columns A to XFD, rows 1 to 1048576.
_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_COLUMNS = 16384
_ROWS = 1048576

_DIGITS = re.compile("[0-9]+")


def dump(obj: list[dict[str, Any]], fp: BinaryIO) -> None:
    """Write MTSV sheets to a binary file as an OOXML workbook.

    obj -- the MTSV sheets
    fp -- a binary file object open for writing

    Raise ValueError if the sheets are not MTSV, if the file has no
    sheets, if two sheets have one sheet name, if a sheet is wider or
    longer than the grid, or if a field or sheet name holds a character
    that XML 1.0 does not allow.
    """
    mtsv.dumps(obj)
    _check(obj)
    with zipfile.ZipFile(fp, "w", zipfile.ZIP_DEFLATED) as package:
        package.writestr(_CONTENT_TYPES_PART, _content_types(len(obj)))
        package.writestr(_ROOT_RELS, _root_relationships())
        package.writestr("xl/workbook.xml", _workbook(obj))
        package.writestr(_WORKBOOK_RELS, _workbook_relationships(len(obj)))
        package.writestr(_SHARED_STRINGS, _shared_string_table())
        for index, sheet in enumerate(obj):
            package.writestr(f"xl/worksheets/sheet{index + 1}.xml", _worksheet(sheet))


def load(fp: BinaryIO, /, errors: str = "strict") -> list[dict[str, Any]]:
    """Read MTSV sheets from a binary OOXML workbook file.

    fp -- a binary file object open for reading
    errors -- "strict" or "ignore"

    Return the sheets. With errors="strict", raise ValueError if
    anything outside MTSV would be left behind; with errors="ignore",
    leave it behind. Raise ValueError for a file that is not an OOXML
    workbook, and LookupError for another errors value.
    """
    _errors.lookup_error(errors)
    try:
        with zipfile.ZipFile(fp) as package:
            parts = {name: package.read(name) for name in package.namelist()}
        sheets, extras = _package(parts)
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as error:
        raise ValueError("the file is not an OOXML package") from error
    _errors.report(extras, errors)
    mtsv.dumps(sheets)
    return sheets


def _check(obj: list[dict[str, Any]]) -> None:
    """Refuse sheets that a workbook cannot hold.

    obj -- the MTSV sheets

    Raise ValueError if there are no sheets, if two sheets have one
    sheet name, if a sheet is wider or longer than the grid, or if a
    field or sheet name holds a character that XML 1.0 does not allow.
    ECMA-376 Part 4, sml.xsd, CT_Sheets: at least one sheet; Part 1,
    18.2.19: a sheet's name "shall be unique"; Part 1, 18.17.5.1: the
    grid.
    """
    if not obj:
        raise ValueError(
            "a workbook holds at least one sheet, so an MTSV file of no"
            " sheets cannot be represented in XLSX"
        )
    names = [sheet["sheet name"] for sheet in obj]
    if len(set(names)) != len(names):
        raise ValueError(
            "each sheet name in a workbook is unique, so sheets that share"
            " a sheet name cannot be represented in XLSX"
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


def _content_types(count: int) -> str:
    """Generate [Content_Types].xml, ECMA-376 Part 2, 7.2.3.

    count -- the number of worksheets

    Return its XML: every part is covered by the rels default or by its
    own override.
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
    """Generate _rels/.rels, which names the workbook part.

    Return its XML.
    """
    return (
        "<?xml version='1.0' encoding='UTF-8'?>"
        f"<Relationships xmlns='{_RELATIONSHIPS}'>"
        f"<Relationship Id='rId1' Type='{_OFFICE_DOCUMENT_REL}'"
        " Target='xl/workbook.xml'/>"
        "</Relationships>"
    )


def _workbook(sheets: list[dict[str, Any]]) -> str:
    """Generate xl/workbook.xml; sheet order is the order written.

    sheets -- the MTSV sheets

    Return its XML.
    """
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


def _workbook_relationships(count: int) -> str:
    """Generate xl/_rels/workbook.xml.rels.

    count -- the number of worksheets

    Return its XML: one entry per worksheet, then the shared string
    table, which ECMA-376 Part 1, 12.3.15 makes the target of a
    relationship from the workbook.
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

    Return its XML. ECMA-376 Part 1, 12.3.15: "A package shall contain
    exactly one Shared String Table part".
    """
    return f"<?xml version='1.0' encoding='UTF-8'?><sst xmlns='{_MAIN}'/>"


def _worksheet(sheet: dict[str, Any]) -> str:
    """Generate a worksheet; an empty sheet holds no rows.

    sheet -- one MTSV sheet

    Return its XML.
    """
    rows = "".join(
        _row(fields, number) for number, fields in enumerate(_lines(sheet), 1)
    )
    return (
        "<?xml version='1.0' encoding='UTF-8'?>"
        f"<worksheet xmlns='{_MAIN}'>"
        f"<sheetData>{rows}</sheetData></worksheet>"
    )


def _lines(sheet: dict[str, Any]) -> list[list[str]]:
    """Return the lines of a sheet; an empty sheet has none.

    sheet -- one MTSV sheet
    """
    if sheet["header"] is None:
        return []
    return [sheet["header"], *sheet["records"]]


def _row(fields: list[str], number: int) -> str:
    """Generate a row.

    fields -- the fields of one line
    number -- the row number, counting from one

    Return its XML.
    """
    cells = "".join(
        _cell(value, _reference(column, number))
        for column, value in enumerate(fields, 1)
    )
    return f"<row r='{number}'>{cells}</row>"


def _cell(value: str, reference: str) -> str:
    """Generate a cell of inline text; an empty field has no value.

    value -- one field
    reference -- the cell's A1 reference

    Return its XML.
    """
    if not value:
        return f"<c r='{reference}'/>"
    return (
        f"<c r='{reference}' t='inlineStr'>"
        f"<is><t xml:space='preserve'>{escape(value)}</t></is></c>"
    )


def _reference(column: int, row: int) -> str:
    """Return the A1 reference of a cell, ECMA-376 Part 1, 18.17.5.1.

    column -- the column, counting from one
    row -- the row, counting from one

    Columns count from A in a bijective base 26: column 26 is Z,
    column 27 is AA, and column 16384 is XFD.
    """
    letters = ""
    while column:
        column, index = divmod(column - 1, len(_LETTERS))
        letters = _LETTERS[index] + letters
    return letters + str(row)


def _package(parts: dict[str, bytes], /) -> tuple[list[dict[str, Any]], set[str]]:
    """Read a package into MTSV sheets, through its relationships.

    parts -- the bytes of each ZIP item, by item name

    Return the sheets, and what they leave behind: every part the
    mapping does not read is left behind by name. Raise KeyError for a
    part that is missing, and ValueError for a package that is not a
    workbook.
    """
    workbook = _part(_relationships(parts, "/"), _OFFICE_DOCUMENT_REL)
    relationships = _relationships(parts, workbook)
    used = {
        _CONTENT_TYPES_PART,
        _zip_name(_relationships_part("/")),
        _zip_name(workbook),
        _zip_name(_relationships_part(workbook)),
    }
    strings: list[str] = []
    left: set[str] = set()
    if any(kind == _SHARED_STRINGS_REL for kind, _ in relationships.values()):
        table = _part(relationships, _SHARED_STRINGS_REL)
        used.add(_zip_name(table))
        strings, strings_left = _shared_strings(parts, table)
        left |= strings_left
    root = ElementTree.fromstring(parts[_zip_name(workbook)])
    left |= _xml.attributes_left_behind(root, _MCE_ATTRIBUTES, _PREFIXES)
    sheets = []
    for child in root:
        if child.tag != _SHEETS:
            left.add(_xml.prefixed(child.tag, _PREFIXES))
            continue
        for entry in child:
            if entry.tag != _SHEET:
                left.add(_xml.prefixed(entry.tag, _PREFIXES))
                continue
            part = relationships[entry.get(_ID)][1]
            used.add(_zip_name(part))
            sheet, sheet_left = _sheet(entry, parts, part, strings)
            sheets.append(sheet)
            left |= sheet_left
    left |= {name for name in parts if name not in used}
    return sheets, left


def _relationships(parts: dict[str, bytes], source: str) -> dict[str, tuple[str, str]]:
    """Map each internal relationship Id of a source to type and part.

    parts -- the bytes of each ZIP item, by item name
    source -- the source part name, or "/" for the package

    Return the map. ECMA-376 Part 2, 6.5.3.4: a Target is resolved
    against its source. Raise KeyError where the source has no
    Relationships part.
    """
    name = _zip_name(_relationships_part(source))
    root = ElementTree.fromstring(parts[name])
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
    """Return the part that the first relationship of a type targets.

    relationships -- a map from _relationships
    kind -- the relationship type

    Raise ValueError where there is no such relationship.
    """
    for relationship, part in relationships.values():
        if relationship == kind:
            return part
    raise ValueError(f"the package has no {kind} relationship")


def _relationships_part(source: str) -> str:
    """Return the name of a source's Relationships part.

    source -- the source part name, or "/" for the package

    ECMA-376 Part 2, 6.5.2.2 and 6.5.2.3: "_rels" is inserted before
    the last segment, and ".rels" is added to it.
    """
    folder, _, last = source.rpartition("/")
    return f"{folder}/_rels/{last}.rels"


def _resolve(source: str, target: str) -> str:
    """Resolve an internal Target to a part name, RFC 3986, 5.2.2.

    source -- the source part name
    target -- the Target attribute

    Return the part name. ECMA-376 Part 2, 6.5.3.4: an internal Target
    is a relative reference. Raise ValueError for a Target with a
    scheme or an authority.
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
    """Remove "." and ".." segments from a path, RFC 3986, 5.2.4.

    path -- an absolute path

    Return the path.
    """
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


def _sheet(
    entry: ElementTree.Element,
    parts: dict[str, bytes],
    part: str,
    strings: list[str],
) -> tuple[dict[str, Any], set[str]]:
    """Read one sheet, named in the workbook, held in its own part.

    entry -- the sheet element of the workbook
    parts -- the bytes of each ZIP item, by item name
    part -- the worksheet part name
    strings -- the shared string table

    Return the sheet, and what it leaves behind. Raise KeyError for a
    missing part, and ValueError for a cell that is not valid.
    """
    left = _xml.attributes_left_behind(entry, (_NAME, _SHEET_ID, _ID), _PREFIXES)
    name = entry.get(_NAME)
    root = ElementTree.fromstring(parts[_zip_name(part)])
    left |= _xml.attributes_left_behind(root, _MCE_ATTRIBUTES, _PREFIXES)
    lines: list[list[str]] = []
    for child in root:
        if child.tag != _SHEET_DATA:
            left.add(_xml.prefixed(child.tag, _PREFIXES))
            continue
        rows, rows_left = _rows(child, strings)
        lines.extend(rows)
        left |= rows_left
    return from_lines(name, lines), left


def _rows(
    element: ElementTree.Element, strings: list[str]
) -> tuple[list[list[str]], set[str]]:
    """Read the values of each row of a sheetData, in order.

    element -- the sheetData element
    strings -- the shared string table

    Return the rows, and what they leave behind. Raise ValueError for a
    cell that is not valid.
    """
    rows = []
    left: set[str] = set()
    for child in element:
        if child.tag != _ROW:
            left.add(_xml.prefixed(child.tag, _PREFIXES))
            continue
        left |= _xml.attributes_left_behind(child, (_REFERENCE,), _PREFIXES)
        values, cells_left = _cells(child, strings)
        rows.append(values)
        left |= cells_left
    return rows, left


def _cells(row: ElementTree.Element, strings: list[str]) -> tuple[list[str], set[str]]:
    """Read a row's cell values, at the positions the cells give.

    row -- one row element
    strings -- the shared string table

    Return the values, and what the cells leave behind: a cell that a
    row leaves out is an empty field; a cell that a row writes is kept,
    empty or not. Raise ValueError for a cell that is not valid.
    """
    values: dict[int, str] = {}
    left: set[str] = set()
    position = 0
    for child in row:
        if child.tag != _CELL:
            left.add(_xml.prefixed(child.tag, _PREFIXES))
            continue
        reference = child.get(_REFERENCE)
        position = position + 1 if reference is None else _column(reference)
        if position < 1 or position in values:
            raise ValueError(
                f"cell {reference!r} does not give a free column of its row"
            )
        values[position], cell_left = _cell_value(child, strings)
        left |= cell_left
    width = max(values, default=0)
    return [values.get(column, "") for column in range(1, width + 1)], left


def _column(reference: str) -> int:
    """Return the column of an A1 reference, counting from one.

    reference -- an A1 reference
    """
    column = 0
    for char in reference:
        if char not in _LETTERS:
            break
        column = column * len(_LETTERS) + _LETTERS.index(char) + 1
    return column


def _cell_value(cell: ElementTree.Element, strings: list[str]) -> tuple[str, set[str]]:
    """Read a cell's value, ECMA-376 Part 4, sml.xsd, ST_CellType.

    cell -- one c element
    strings -- the shared string table

    Return the value, and what the cell leaves behind: a type other
    than s, str or inlineStr is left behind; a cell that carries no
    value leaves nothing behind, whatever its type says. Raise
    ValueError for a shared string index outside the table.
    """
    left = _xml.attributes_left_behind(cell, (_REFERENCE, _TYPE), _PREFIXES)
    cell_type = cell.get(_TYPE, "n")
    text = None
    for child in cell:
        if child.tag == _VALUE:
            text = child.text or ""
        elif child.tag == _INLINE:
            text, inline_left = _rst_text(child)
            left |= inline_left
        else:
            left.add(_xml.prefixed(child.tag, _PREFIXES))
    if text is None:
        return "", left
    if cell_type not in _TEXT_TYPES:
        left.add(f"cell type {cell_type}")
    if cell_type == "s":
        if not _DIGITS.fullmatch(text) or int(text) >= len(strings):
            raise ValueError(f"no shared string {text!r}")
        return strings[int(text)], left
    return text, left


def _shared_strings(parts: dict[str, bytes], part: str) -> tuple[list[str], set[str]]:
    """Read the shared string table that the workbook points to.

    parts -- the bytes of each ZIP item, by item name
    part -- the shared string table part name

    Return the strings, and what the table leaves behind. Raise
    KeyError for a missing part, and ValueError for a part that is
    not an sst.
    """
    root = ElementTree.fromstring(parts[_zip_name(part)])
    if root.tag != _SST:
        raise ValueError("the shared string part is not an sst")
    left = _xml.attributes_left_behind(root, _MCE_ATTRIBUTES, _PREFIXES)
    strings = []
    for child in root:
        if child.tag == _SI:
            text, item_left = _rst_text(child)
            strings.append(text)
            left |= item_left
        else:
            left.add(_xml.prefixed(child.tag, _PREFIXES))
    return strings, left


def _rst_text(element: ElementTree.Element) -> tuple[str, set[str]]:
    """Read a rich string as text, joining its runs in order.

    element -- an is or si element

    Return the text, and what the runs leave behind.
    """
    parts = []
    left: set[str] = set()
    for child in element:
        if child.tag == _TEXT:
            parts.append(child.text or "")
        elif child.tag == _RUN:
            for part in child:
                if part.tag == _TEXT:
                    parts.append(part.text or "")
                else:
                    left.add(_xml.prefixed(part.tag, _PREFIXES))
        else:
            left.add(_xml.prefixed(child.tag, _PREFIXES))
    return "".join(parts), left


def _zip_name(part: str) -> str:
    """Return the ZIP item name of a part name, ECMA-376 Part 2, 7.3.4.

    part -- a part name

    The leading "/" is removed, and every non-ASCII character is
    percent-encoded.
    """
    return "".join(
        (
            char
            if char.isascii()
            else "".join(f"%{byte:02X}" for byte in char.encode("utf-8"))
        )
        for char in part[1:]
    )
