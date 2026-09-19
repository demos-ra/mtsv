"""Make a sheet from the lines of a spreadsheet table.

Functions:
from_lines -- return a sheet whose lines are padded to the widest line
"""

__all__ = ["from_lines"]

from typing import Any


def from_lines(name: str, lines: list[list[str]]) -> dict[str, Any]:
    """Return a sheet whose lines are padded to the widest line.

    name -- the sheet name
    lines -- the lines of the table, the header first, of any widths

    The draft, Data Model: every record in a sheet has as many fields
    as the header of that sheet, and a sheet with no lines is an empty
    sheet.
    """
    if not lines:
        return {"sheet name": name, "header": None, "records": []}
    width = max(len(values) for values in lines)
    padded = [values + [""] * (width - len(values)) for values in lines]
    return {"sheet name": name, "header": padded[0], "records": padded[1:]}
