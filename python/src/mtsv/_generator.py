"""Generate MTSV text, following the draft, Generators.

Functions:
mtsv_file -- generate the whole text from sheets
named_sheet -- generate a sheet with its FF line
sheet_body -- generate the lines of a sheet
header -- generate the first line of a sheet
record -- generate one line from its fields
field -- generate one field
sheet_name -- generate the sheet name after an FF
eol -- generate a line break
check_sheet -- refuse a sheet whose lines do not fit the data model
"""

__all__ = [
    "mtsv_file",
    "named_sheet",
    "sheet_body",
    "header",
    "record",
    "field",
    "sheet_name",
    "eol",
    "check_sheet",
]

from typing import Any

from mtsv import _data_model
from mtsv._grammar import FF, HTAB, LF, field_char


def mtsv_file(sheets: list[dict[str, Any]]) -> str:
    """Generate: mtsv-file = first-sheet *named-sheet.

    sheets -- the MTSV sheets

    Return the MTSV text. The draft, Generators: "A generator MUST
    write an FF line before every sheet, including the first". Raise
    ValueError, naming the position, for sheets that MTSV cannot
    represent.
    """
    return "".join(named_sheet(sheet, index) for index, sheet in enumerate(sheets))


def named_sheet(sheet: dict[str, Any], index: int) -> str:
    """Generate: named-sheet = FF sheet-name eol sheet-body.

    sheet -- one MTSV sheet
    index -- the index of the sheet in the file

    Return its text. Raise ValueError, naming the position, for a
    sheet that MTSV cannot represent.
    """
    return (
        FF + sheet_name(sheet["sheet name"], index) + eol() + sheet_body(sheet, index)
    )


def sheet_body(sheet: dict[str, Any], index: int) -> str:
    """Generate: sheet-body = [header *record].

    sheet -- one MTSV sheet
    index -- the index of the sheet in the file

    Return its lines. Raise ValueError, naming the position, for a
    sheet MTSV cannot represent.
    """
    check_sheet(sheet, index)
    if sheet["header"] is None:
        return ""
    lines = [header(sheet["header"], index)]
    lines.extend(
        record(fields, _data_model.record(index, record_index))
        for record_index, fields in enumerate(sheet["records"])
    )
    return "".join(lines)


def header(fields: list[str], index: int) -> str:
    """Generate: header = record.

    fields -- the header fields
    index -- the index of the sheet in the file

    Return the line. Raise ValueError, naming the position, for a line
    MTSV cannot represent.
    """
    return record(fields, _data_model.header(index))


def record(fields: list[str], line: str) -> str:
    """Generate: record = field *(HTAB field) eol.

    fields -- the fields of the line
    line -- the position of the line, as named

    Return the line. Raise ValueError, naming the position, for no
    fields, or a field MTSV cannot represent.
    """
    if not fields:
        raise ValueError(
            f"a record must match: record = field *(HTAB field) eol: {line}"
        )
    return (
        HTAB.join(
            field(value, _data_model.field(line, field_index))
            for field_index, value in enumerate(fields)
        )
        + eol()
    )


def field(value: str, position: str) -> str:
    """Generate: field = *field-char.

    value -- the field
    position -- the position of the field, as named

    Return it. Raise ValueError, naming the position, for a field that
    holds HT, LF, FF or CR (the draft, Generators).
    """
    if not all(field_char(char) for char in value):
        raise ValueError(
            "a field or sheet name that contains HT, LF, FF, or CR"
            f" cannot be represented in MTSV: {position}"
        )
    return value


def sheet_name(value: str, index: int) -> str:
    """Generate: sheet-name = *field-char.

    value -- the sheet name
    index -- the index of the sheet in the file

    Return it. Raise ValueError, naming the position, for a sheet name
    that is not text, or that holds HT, LF, FF or CR (the draft, Data
    Model and Generators).
    """
    position = _data_model.sheet_name(index)
    if not isinstance(value, str):
        raise ValueError(f"every sheet has a sheet name: {position}")
    if not all(field_char(char) for char in value):
        raise ValueError(
            "a field or sheet name that contains HT, LF, FF, or CR"
            f" cannot be represented in MTSV: {position}"
        )
    return value


def eol() -> str:
    """Generate: eol = LF / CRLF.

    Return LF.
    """
    return LF


def check_sheet(sheet: dict[str, Any], index: int) -> None:
    """Refuse a sheet whose lines do not fit the data model.

    sheet -- one MTSV sheet
    index -- the index of the sheet in the file

    Raise ValueError, naming the position, for records without a
    header, and for a record that has not as many fields as the header.
    The draft, Data Model: "Every record in a sheet has as many fields
    as the header of that sheet. A sheet with no lines is an empty
    sheet; it has neither a header nor records."
    """
    header_fields = sheet["header"]
    if header_fields is None:
        if sheet["records"]:
            raise ValueError(
                "a sheet with no lines is an empty sheet;"
                " it has neither a header nor records:"
                f" {_data_model.sheet(index)}"
            )
        return
    for record_index, fields in enumerate(sheet["records"]):
        if len(fields) != len(header_fields):
            raise ValueError(
                "each record in a sheet must have the same number of fields"
                " as the header of that sheet:"
                f" {_data_model.record(index, record_index)}"
            )
