"""Generate MTSV text, following draft-demosra-mtsv-01, Section 6."""

from typing import Any

HTAB = chr(0x09)
LF = chr(0x0A)
FF = chr(0x0C)


def mtsv_file(sheets: list[dict[str, Any]]) -> str:
    """Generate: mtsv-file = first-sheet *named-sheet.

    Write an FF line before every sheet, so first-sheet is empty
    (Section 6).
    """
    return "".join(named_sheet(sheet) for sheet in sheets)


def named_sheet(sheet: dict[str, Any]) -> str:
    """Generate: named-sheet = FF sheet-name eol sheet-body."""
    return FF + sheet_name(sheet["sheet name"]) + eol() + sheet_body(sheet)


def sheet_body(sheet: dict[str, Any]) -> str:
    """Generate: sheet-body = [header *record]."""
    header_fields = sheet["header"]
    if header_fields is None:
        if sheet["records"]:
            raise ValueError(
                "a sheet with no lines is an empty sheet;"
                " it has neither a header nor records"
            )
        return ""
    lines = [header(header_fields)]
    for record_fields in sheet["records"]:
        if len(record_fields) != len(header_fields):
            raise ValueError(
                "each record in a sheet must have the same number of fields"
                " as the header of that sheet"
            )
        lines.append(record(record_fields))
    return "".join(lines)


def header(fields: list[str]) -> str:
    """Generate: header = record."""
    return record(fields)


def record(fields: list[str]) -> str:
    """Generate: record = field *(HTAB field) eol."""
    if not fields:
        raise ValueError(
            "a record must match: record = field *(HTAB field) eol"
        )
    return HTAB.join(field(value) for value in fields) + eol()


def field(value: str) -> str:
    """Generate: field = *field-char."""
    if not all(field_char(char) for char in value):
        raise ValueError(
            "a field or sheet name that contains HT, LF, FF, or CR"
            " cannot be represented in MTSV"
        )
    return value


def sheet_name(value: str) -> str:
    """Generate: sheet-name = *field-char."""
    if not isinstance(value, str):
        raise ValueError("every sheet has a sheet name")
    if not all(field_char(char) for char in value):
        raise ValueError(
            "a field or sheet name that contains HT, LF, FF, or CR"
            " cannot be represented in MTSV"
        )
    return value


def field_char(char: str) -> bool:
    """Match: field-char = %x00-08 / %x0B / %x0E-10FFFF."""
    code = ord(char)
    return 0x00 <= code <= 0x08 or code == 0x0B or 0x0E <= code <= 0x10FFFF


def eol() -> str:
    """Generate: eol = LF / CRLF, writing LF."""
    return LF
