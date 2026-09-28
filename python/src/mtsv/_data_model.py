"""Positions in MTSV sheets, following the draft, Data Model.

Each function takes indexes counted from 0 and names the position
counted from 1. GNU Coding Standards 4.4: "Line numbers should start
from 1 at the beginning of the file, and column numbers should start
from 1 at the beginning of the line."

Functions:
sheet -- name a sheet
sheet_name -- name the sheet name of a sheet
header -- name the header of a sheet
record -- name a record of a sheet
field -- name a field of a line, or of every line of a sheet
"""

__all__ = ["sheet", "sheet_name", "header", "record", "field"]


def sheet(index: int) -> str:
    """Name a sheet.

    index -- the index of the sheet in the file

    The draft, Data Model: "An MTSV file is an ordered sequence of
    sheets."
    """
    return f"sheet {index + 1}"


def sheet_name(index: int) -> str:
    """Name the sheet name of a sheet.

    index -- the index of the sheet in the file

    The draft, Data Model: "Every sheet has a sheet name."
    """
    return f"{sheet(index)}, sheet name"


def header(index: int) -> str:
    """Name the header of a sheet.

    index -- the index of the sheet in the file

    The draft, Data Model: "A sheet is a header and an ordered sequence
    of zero or more records."
    """
    return f"{sheet(index)}, header"


def record(sheet_index: int, index: int) -> str:
    """Name a record of a sheet.

    sheet_index -- the index of the sheet in the file
    index -- the index of the record among the records of the sheet

    The draft, Data Model: "A sheet is a header and an ordered sequence
    of zero or more records."
    """
    return f"{sheet(sheet_index)}, record {index + 1}"


def field(line: str, index: int) -> str:
    """Name a field of a line, or of every line of a sheet.

    line -- the header or record, as named, or the sheet, as named
    index -- the index of the field in the line

    The draft, Data Model: "A record is an ordered sequence of fields.
    Every record in a sheet has as many fields as the header of that
    sheet."
    """
    return f"{line}, field {index + 1}"
