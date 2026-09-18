"""Parse MTSV text, following the draft, Parsers."""

from typing import Any

from mtsv._grammar import CRLF, FF, HTAB, LF, field_char

SIGNATURE = chr(0xFEFF)


class MTSVDecodeError(ValueError):
    """Subclass of ValueError with the following additional properties:

    msg: The unformatted error message
    doc: The MTSV document being parsed
    pos: The start index of doc where parsing failed
    lineno: The line corresponding to pos
    colno: The column corresponding to pos
    """

    def __init__(self, msg: str, doc: str, pos: int) -> None:
        """Store msg, doc and pos, and the line and column of pos."""
        lineno = doc.count(LF, 0, pos) + 1
        colno = pos - doc.rfind(LF, 0, pos)
        super().__init__(f"{msg}: line {lineno} column {colno} (char {pos})")
        self.msg = msg
        self.doc = doc
        self.pos = pos
        self.lineno = lineno
        self.colno = colno

    def __reduce__(self) -> tuple[type, tuple[str, str, int]]:
        """Return how to rebuild this error when it is unpickled."""
        return self.__class__, (self.msg, self.doc, self.pos)


def mtsv_file(src: str, pos: int) -> tuple[int, list[dict[str, Any]]]:
    """Parse: mtsv-file = first-sheet *named-sheet.

    Skip a U+FEFF at the start of the file, which is an encoding
    signature (the draft, Parsers).
    """
    if pos == 0 and src.startswith(SIGNATURE):
        pos = 1
    pos, sheet = first_sheet(src, pos)
    sheets: list[dict[str, Any]] = [] if sheet is None else [sheet]
    while pos < len(src):
        pos, sheet = named_sheet(src, pos)
        sheets.append(sheet)
    return pos, sheets


def first_sheet(src: str, pos: int) -> tuple[int, dict[str, Any] | None]:
    """Parse: first-sheet = sheet-body, whose sheet name is empty."""
    pos, (header_fields, records) = sheet_body(src, pos)
    if header_fields is None:
        return pos, None
    return pos, {
        "sheet name": "",
        "header": header_fields,
        "records": records,
    }


def named_sheet(src: str, pos: int) -> tuple[int, dict[str, Any]]:
    """Parse: named-sheet = FF sheet-name eol sheet-body."""
    if not src.startswith(FF, pos):
        raise MTSVDecodeError("expected FF", src, pos)
    pos, name = sheet_name(src, pos + 1)
    pos, _ = eol(src, pos)
    pos, (header_fields, records) = sheet_body(src, pos)
    return pos, {
        "sheet name": name,
        "header": header_fields,
        "records": records,
    }


def sheet_body(
    src: str, pos: int
) -> tuple[int, tuple[list[str] | None, list[list[str]]]]:
    """Parse: sheet-body = [header *record]."""
    if pos == len(src) or src.startswith(FF, pos):
        return pos, (None, [])
    pos, header_fields = header(src, pos)
    records: list[list[str]] = []
    while pos < len(src) and not src.startswith(FF, pos):
        start = pos
        pos, record_fields = record(src, pos)
        if len(record_fields) != len(header_fields):
            raise MTSVDecodeError(
                "each record in a sheet must have the same number of fields"
                " as the header of that sheet",
                src,
                start,
            )
        records.append(record_fields)
    return pos, (header_fields, records)


def header(src: str, pos: int) -> tuple[int, list[str]]:
    """Parse: header = record."""
    return record(src, pos)


def record(src: str, pos: int) -> tuple[int, list[str]]:
    """Parse: record = field *(HTAB field) eol."""
    pos, value = field(src, pos)
    fields = [value]
    while src.startswith(HTAB, pos):
        pos, value = field(src, pos + 1)
        fields.append(value)
    pos, _ = eol(src, pos)
    return pos, fields


def field(src: str, pos: int) -> tuple[int, str]:
    """Parse: field = *field-char."""
    start = pos
    while pos < len(src) and field_char(src[pos]):
        pos += 1
    return pos, src[start:pos]


def sheet_name(src: str, pos: int) -> tuple[int, str]:
    """Parse: sheet-name = *field-char."""
    start = pos
    while pos < len(src) and field_char(src[pos]):
        pos += 1
    return pos, src[start:pos]


def eol(src: str, pos: int) -> tuple[int, str]:
    """Parse: eol = LF / CRLF."""
    if src.startswith(LF, pos):
        return pos + 1, LF
    if src.startswith(CRLF, pos):
        return pos + 2, CRLF
    raise MTSVDecodeError("expected LF or CRLF", src, pos)
