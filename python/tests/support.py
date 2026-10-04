"""Shared helpers for the tests: conformance files and ODF content."""

import json
import logging
from pathlib import Path

# Logging HOWTO, Configuring Logging for a Library: a library adds a
# NullHandler where its events should not be printed without
# configuration.
_LOGGER = logging.getLogger("mtsv")
_LOGGER.addHandler(logging.NullHandler())
_LOGGER.propagate = False

CONFORMANCE = Path(__file__).resolve().parents[2] / "conformance"

MEDIA_TYPE = "application/vnd.oasis.opendocument.spreadsheet"
OFFICE = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
TABLE = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
TEXT = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
NAMESPACES = f" xmlns:office='{OFFICE}' xmlns:table='{TABLE}' xmlns:text='{TEXT}'"
# ODF 1.3 Part 3, 3.1.2 and 3.1.3.2: grddl:transformation is an
# attribute of both roots.
GRDDL = " xmlns:grddl='http://www.w3.org/2003/g/data-view#' grddl:transformation='t'"
COLUMN = "<table:table-column/>"
STRING = " office:value-type='string'"
SHEET_A = [{"sheet name": "S", "header": ["a"], "records": []}]
XML_FORBIDDEN = {
    "field-u0000",
    "field-u0008",
    "field-u000b",
    "field-u000e",
    "sheet-name-u0000",
    "sheet-name-u0008",
    "sheet-name-u000b",
    "sheet-name-u000e",
}
TRIMMED = {
    "empty-first-field": [
        {"sheet name": "", "header": None, "records": []},
    ],
    "empty-later-field": [
        {"sheet name": "", "header": ["a"], "records": []},
    ],
}


def paths(folder, suffix):
    """Return the sorted paths in a conformance folder with a suffix."""
    found = sorted((CONFORMANCE / folder).glob("*" + suffix))
    if not found:
        raise FileNotFoundError(CONFORMANCE / folder)
    return found


def load_json(path):
    """Return the JSON value in a file, decoded as UTF-8."""
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def cell(content="<text:p>a</text:p>", attributes=STRING):
    """Return a table:table-cell."""
    return f"<table:table-cell{attributes}>{content}</table:table-cell>"


def row(cells=None, attributes=""):
    """Return a table:table-row, by default holding cell a."""
    cells = cell() if cells is None else cells
    return f"<table:table-row{attributes}>{cells}</table:table-row>"


def table(inner=None, attributes=" table:name='S'"):
    """Return table:table S, by default with a column and row a."""
    inner = COLUMN + row() if inner is None else inner
    return f"<table:table{attributes}>{inner}</table:table>"


def wrap(tag, inner):
    """Return inner wrapped in the element tag."""
    return f"<{tag}>{inner}</{tag}>"


def document_content(tables="", document="", spreadsheet="", attributes=""):
    """Return office:document-content whose spreadsheet holds tables."""
    return (
        f"<office:document-content{NAMESPACES} office:version='1.3'{attributes}>"
        f"{document}<office:body><office:spreadsheet{spreadsheet}>"
        f"{tables}</office:spreadsheet></office:body>"
        "</office:document-content>"
    )
