"""Parse MTSV text, following draft-demos-ra-mtsv-01, Section 4.4."""

from typing import Any

HTAB = chr(0x09)
LF = chr(0x0A)
FF = chr(0x0C)
CR = chr(0x0D)
CRLF = CR + LF


class MTSVDecodeError(ValueError):
    """Subclass of ValueError for text that is not an MTSV file."""

    def __init__(self, msg: str, doc: str, pos: int) -> None:
        lineno = doc.count(LF, 0, pos) + 1
        colno = pos - doc.rfind(LF, 0, pos)
        super().__init__(f"{msg}: line {lineno} column {colno} (char {pos})")
        self.msg = msg
        self.doc = doc
        self.pos = pos
        self.lineno = lineno
        self.colno = colno


def mtsv_file(src: str, pos: int) -> tuple[int, list[dict[str, Any]]]:
    """Parse: mtsv-file = unnamed-sheet *named-sheet."""
    pos, sheet = unnamed_sheet(src, pos)
    sheets: list[dict[str, Any]] = [] if sheet is None else [sheet]
    while pos < len(src):
        pos, sheet = named_sheet(src, pos)
        sheets.append(sheet)
    return pos, sheets


def unnamed_sheet(src: str, pos: int) -> tuple[int, dict[str, Any] | None]:
    """Parse: unnamed-sheet = sheet-body."""
    pos, (header_fields, records) = sheet_body(src, pos)
    if header_fields is None:
        return pos, None
    return pos, {
        "sheet name": None,
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


def field_char(char: str) -> bool:
    """Match: field-char = %x00-08 / %x0B / %x0E-10FFFF."""
    code = ord(char)
    return 0x00 <= code <= 0x08 or code == 0x0B or 0x0E <= code <= 0x10FFFF


def eol(src: str, pos: int) -> tuple[int, str]:
    """Parse: eol = LF / CRLF."""
    if src.startswith(LF, pos):
        return pos + 1, LF
    if src.startswith(CRLF, pos):
        return pos + 2, CRLF
    raise MTSVDecodeError("expected LF or CRLF", src, pos)
