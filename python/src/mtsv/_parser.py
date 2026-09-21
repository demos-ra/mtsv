"""Parse MTSV text, following the draft, Parsers.

Classes:
MTSVDecodeError -- raised for text that is not an MTSV file

Functions:
mtsv_file -- parse the whole text into sheets
signature -- skip a U+FEFF at the start of the text
first_sheet -- parse the lines before the first FF
named_sheet -- parse a sheet that begins with an FF line
sheet_body -- parse the lines of a sheet
header -- parse the first line of a sheet
record -- parse one line into its fields
field -- parse one field
sheet_name -- parse the sheet name after an FF
eol -- parse a line break
check_width -- refuse a record that is not as wide as its header

Constants:
SIGNATURE -- U+FEFF, the encoding signature
"""

__all__ = [
    "MTSVDecodeError",
    "mtsv_file",
    "signature",
    "first_sheet",
    "named_sheet",
    "sheet_body",
    "header",
    "record",
    "field",
    "sheet_name",
    "eol",
    "check_width",
    "SIGNATURE",
]

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

    src -- the MTSV text
    pos -- the index to start at

    Return the index after the file, and its sheets. Raise
    MTSVDecodeError where the text does not match.
    """
    pos = signature(src, pos)
    pos, sheet = first_sheet(src, pos)
    sheets: list[dict[str, Any]] = [] if sheet is None else [sheet]
    while pos < len(src):
        pos, sheet = named_sheet(src, pos)
        sheets.append(sheet)
    return pos, sheets


def signature(src: str, pos: int) -> int:
    """Skip a U+FEFF at the start of the text.

    src -- the MTSV text
    pos -- the index to start at

    Return the index after the signature, if any. The draft, Parsers:
    "A parser SHOULD treat a U+FEFF character at the start of a file as
    an encoding signature and not as part of the first field".
    """
    if pos == 0 and src.startswith(SIGNATURE):
        return 1
    return pos


def first_sheet(src: str, pos: int) -> tuple[int, dict[str, Any] | None]:
    """Parse: first-sheet = sheet-body, whose sheet name is empty.

    src -- the MTSV text
    pos -- the index to start at

    Return the index after the sheet, and the sheet, or None where the
    text has no lines before the first FF. Raise MTSVDecodeError where
    the text does not match.
    """
    pos, (header_fields, records) = sheet_body(src, pos)
    if header_fields is None:
        return pos, None
    return pos, {
        "sheet name": "",
        "header": header_fields,
        "records": records,
    }


def named_sheet(src: str, pos: int) -> tuple[int, dict[str, Any]]:
    """Parse: named-sheet = FF sheet-name eol sheet-body.

    src -- the MTSV text
    pos -- the index to start at

    Return the index after the sheet, and the sheet. Raise
    MTSVDecodeError where the text does not match.
    """
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
    """Parse: sheet-body = [header *record].

    src -- the MTSV text
    pos -- the index to start at

    Return the index after the lines, and the header, or None for an
    empty sheet, with the records. Raise MTSVDecodeError where the text
    does not match.
    """
    if pos == len(src) or src.startswith(FF, pos):
        return pos, (None, [])
    pos, header_fields = header(src, pos)
    records: list[list[str]] = []
    while pos < len(src) and not src.startswith(FF, pos):
        start = pos
        pos, record_fields = record(src, pos)
        check_width(src, start, record_fields, header_fields)
        records.append(record_fields)
    return pos, (header_fields, records)


def header(src: str, pos: int) -> tuple[int, list[str]]:
    """Parse: header = record.

    src -- the MTSV text
    pos -- the index to start at

    Return the index after the line, and its fields. Raise
    MTSVDecodeError where the text does not match.
    """
    return record(src, pos)


def record(src: str, pos: int) -> tuple[int, list[str]]:
    """Parse: record = field *(HTAB field) eol.

    src -- the MTSV text
    pos -- the index to start at

    Return the index after the line, and its fields. Raise
    MTSVDecodeError where the text does not match.
    """
    pos, value = field(src, pos)
    fields = [value]
    while src.startswith(HTAB, pos):
        pos, value = field(src, pos + 1)
        fields.append(value)
    pos, _ = eol(src, pos)
    return pos, fields


def field(src: str, pos: int) -> tuple[int, str]:
    """Parse: field = *field-char.

    src -- the MTSV text
    pos -- the index to start at

    Return the index after the field, and the field.
    """
    start = pos
    while pos < len(src) and field_char(src[pos]):
        pos += 1
    return pos, src[start:pos]


def sheet_name(src: str, pos: int) -> tuple[int, str]:
    """Parse: sheet-name = *field-char.

    src -- the MTSV text
    pos -- the index to start at

    Return the index after the sheet name, and the sheet name.
    """
    start = pos
    while pos < len(src) and field_char(src[pos]):
        pos += 1
    return pos, src[start:pos]


def eol(src: str, pos: int) -> tuple[int, str]:
    """Parse: eol = LF / CRLF.

    src -- the MTSV text
    pos -- the index to start at

    Return the index after the line break, and the line break. Raise
    MTSVDecodeError where there is none.
    """
    if src.startswith(LF, pos):
        return pos + 1, LF
    if src.startswith(CRLF, pos):
        return pos + 2, CRLF
    raise MTSVDecodeError("expected LF or CRLF", src, pos)


def check_width(
    src: str, pos: int, fields: list[str], header_fields: list[str]
) -> None:
    """Refuse a record that is not as wide as its header.

    src -- the MTSV text
    pos -- the index where the record starts
    fields -- the record's fields
    header_fields -- the header's fields

    Raise MTSVDecodeError where they differ. The draft, Grammar: "each
    record in a sheet MUST have the same number of fields as the header
    of that sheet".
    """
    if len(fields) != len(header_fields):
        raise MTSVDecodeError(
            "each record in a sheet must have the same number of fields"
            " as the header of that sheet",
            src,
            pos,
        )
