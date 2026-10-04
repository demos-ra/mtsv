"""Convert between MTSV sheets and ODF single XML documents, ODF 1.3.

Functions:
dump -- write MTSV sheets to a binary file as an ODF single XML file
load -- read MTSV sheets from a binary ODF single XML file
"""

__all__ = ["dump", "load"]

from typing import Any, BinaryIO
from xml.etree import ElementTree

import mtsv
from mtsv.integrations import _errors, _odf, _xml

_DOCUMENT = "{" + _odf.OFFICE + "}document"
_MIMETYPE = "{" + _odf.OFFICE + "}mimetype"


def dump(obj: list[dict[str, Any]], fp: BinaryIO) -> None:
    """Write MTSV sheets to a binary file as an ODF single XML document.

    obj -- the MTSV sheets
    fp -- a binary file object open for writing

    Raise ValueError, naming the position, if the sheets are not MTSV,
    or if a field or sheet name holds a character that XML 1.0 does not
    allow.
    """
    mtsv.dumps(obj)
    _xml.check_chars(obj, "ODF single XML document")
    fp.write(_document(obj).encode("utf-8"))


def load(fp: BinaryIO, /, errors: str = "strict") -> list[dict[str, Any]]:
    """Read MTSV sheets from a binary ODF single XML document.

    fp -- a binary file object open for reading
    errors -- "strict" or "ignore"

    Return the sheets. With errors="strict", raise ValueError if
    anything outside MTSV would be left behind; with errors="ignore",
    leave it behind. Raise ValueError for a file that is not an ODF
    single XML document, and LookupError for another errors value.
    """
    _errors.lookup_error(errors)
    try:
        root = ElementTree.fromstring(fp.read())
    except ElementTree.ParseError as error:
        raise ValueError("the file is not an ODF single XML document") from error
    if root.tag != _DOCUMENT:
        raise ValueError("the document is not office:document")
    extras = _xml.attributes_left_behind(root, (_odf.VERSION, _MIMETYPE), _odf.PREFIXES)
    sheets, body_left = _odf.read_body(root)
    extras |= body_left
    _errors.report(extras, errors)
    mtsv.dumps(sheets)
    return sheets


def _document(sheets: list[dict[str, Any]]) -> str:
    """Generate office:document, ODF 1.3 Part 3, 3.1.2.

    sheets -- the MTSV sheets

    Return its XML; office:mimetype is that of a spreadsheet, ODF 1.3
    Part 3, 2.2.4.
    """
    return (
        "<?xml version='1.0' encoding='UTF-8'?>"
        f"<office:document{_odf.ROOT_ATTRIBUTES}"
        f" office:mimetype='{_odf.MEDIA_TYPE}'>"
        f"{_odf.body(sheets)}"
        "</office:document>"
    )
