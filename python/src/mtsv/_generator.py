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

from typing import Any

from mtsv._grammar import FF, HTAB, LF, field_char


def mtsv_file(sheets: list[dict[str, Any]]) -> str:
    """Generate: mtsv-file = first-sheet *named-sheet.

    sheets -- the MTSV sheets

    Return the MTSV text. The draft, Generators: "A generator MUST
    write an FF line before every sheet, including the first". Raise
    ValueError for sheets that MTSV cannot represent.
    """
    return "".join(named_sheet(sheet) for sheet in sheets)


def named_sheet(sheet: dict[str, Any]) -> str:
    """Generate: named-sheet = FF sheet-name eol sheet-body.

    sheet -- one MTSV sheet

    Return its text. Raise ValueError for a sheet that MTSV cannot
    represent.
    """
    return FF + sheet_name(sheet["sheet name"]) + eol() + sheet_body(sheet)


def sheet_body(sheet: dict[str, Any]) -> str:
    """Generate: sheet-body = [header *record].

    sheet -- one MTSV sheet

    Return its lines. Raise ValueError for a sheet MTSV cannot
    represent.
    """
    check_sheet(sheet)
    if sheet["header"] is None:
        return ""
    lines = [header(sheet["header"])]
    lines.extend(record(fields) for fields in sheet["records"])
    return "".join(lines)


def header(fields: list[str]) -> str:
    """Generate: header = record.

    fields -- the header fields

    Return the line. Raise ValueError for a line MTSV cannot represent.
    """
    return record(fields)


def record(fields: list[str]) -> str:
    """Generate: record = field *(HTAB field) eol.

    fields -- the fields of the line

    Return the line. Raise ValueError for no fields, or a field MTSV
    cannot represent.
    """
    if not fields:
        raise ValueError("a record must match: record = field *(HTAB field) eol")
    return HTAB.join(field(value) for value in fields) + eol()


def field(value: str) -> str:
    """Generate: field = *field-char.

    value -- the field

    Return it. Raise ValueError for a field that holds HT, LF, FF or CR
    (the draft, Generators).
    """
    if not all(field_char(char) for char in value):
        raise ValueError(
            "a field or sheet name that contains HT, LF, FF, or CR"
            " cannot be represented in MTSV"
        )
    return value


def sheet_name(value: str) -> str:
    """Generate: sheet-name = *field-char.

    value -- the sheet name

    Return it. Raise ValueError for a sheet name that is not text, or
    that holds HT, LF, FF or CR (the draft, Data Model and Generators).
    """
    if not isinstance(value, str):
        raise ValueError("every sheet has a sheet name")
    if not all(field_char(char) for char in value):
        raise ValueError(
            "a field or sheet name that contains HT, LF, FF, or CR"
            " cannot be represented in MTSV"
        )
    return value


def eol() -> str:
    """Generate: eol = LF / CRLF.

    Return LF.
    """
    return LF


def check_sheet(sheet: dict[str, Any]) -> None:
    """Refuse a sheet whose lines do not fit the data model.

    sheet -- one MTSV sheet

    Raise ValueError for records without a header, and for a record
    that has not as many fields as the header. The draft, Data Model:
    "Every record in a sheet has as many fields as the header of that
    sheet. A sheet with no lines is an empty sheet; it has neither a
    header nor records."
    """
    header_fields = sheet["header"]
    if header_fields is None:
        if sheet["records"]:
            raise ValueError(
                "a sheet with no lines is an empty sheet;"
                " it has neither a header nor records"
            )
        return
    for fields in sheet["records"]:
        if len(fields) != len(header_fields):
            raise ValueError(
                "each record in a sheet must have the same number of fields"
                " as the header of that sheet"
            )
