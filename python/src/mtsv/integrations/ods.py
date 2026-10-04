"""Convert between MTSV sheets and OpenDocument packages, ODF 1.3.

Functions:
dump -- write MTSV sheets to a binary file as an ODF spreadsheet
load -- read MTSV sheets from a binary ODF spreadsheet file
"""

__all__ = ["dump", "load"]

import zipfile
from typing import Any, BinaryIO
from xml.etree import ElementTree

import mtsv
from mtsv.integrations import _errors, _odf, _xml

_PACKAGE_FILES = ("mimetype", "META-INF/manifest.xml", "content.xml")
_MANIFEST = "urn:oasis:names:tc:opendocument:xmlns:manifest:1.0"
_DOCUMENT_CONTENT = "{" + _odf.OFFICE + "}document-content"


def dump(obj: list[dict[str, Any]], fp: BinaryIO) -> None:
    """Write MTSV sheets to a binary file as an ODF spreadsheet.

    obj -- the MTSV sheets
    fp -- a binary file object open for writing

    Raise ValueError, naming the position, if the sheets are not MTSV,
    or if a field or sheet name holds a character that XML 1.0 does not
    allow.
    """
    mtsv.dumps(obj)
    _xml.check_chars(obj, "ODS")
    # ODF 1.3 Part 2, 3.3: "mimetype" is the first file, not compressed.
    with zipfile.ZipFile(fp, "w") as package:
        package.writestr(
            zipfile.ZipInfo("mimetype"), _odf.MEDIA_TYPE, zipfile.ZIP_STORED
        )
        package.writestr(
            zipfile.ZipInfo("META-INF/manifest.xml"),
            _manifest(),
            zipfile.ZIP_DEFLATED,
        )
        package.writestr(
            zipfile.ZipInfo("content.xml"),
            _document_content(obj),
            zipfile.ZIP_DEFLATED,
        )


def load(fp: BinaryIO, /, errors: str = "strict") -> list[dict[str, Any]]:
    """Read MTSV sheets from a binary ODF spreadsheet file.

    fp -- a binary file object open for reading
    errors -- "strict" or "ignore"

    Return the sheets. With errors="strict", raise ValueError if
    anything outside MTSV would be left behind; with errors="ignore",
    leave it behind. Raise ValueError for a file that is not an ODF
    spreadsheet, and LookupError for another errors value.
    """
    _errors.lookup_error(errors)
    try:
        with zipfile.ZipFile(fp) as package:
            names = package.namelist()
            root = ElementTree.fromstring(package.read("content.xml"))
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as error:
        raise ValueError("the file is not an ODF package") from error
    if root.tag != _DOCUMENT_CONTENT:
        raise ValueError("content.xml is not office:document-content")
    extras = _xml.attributes_left_behind(root, (_odf.VERSION,), _odf.PREFIXES)
    sheets, body_left = _odf.read_body(root)
    extras |= body_left
    extras |= {name for name in names if name not in _PACKAGE_FILES}
    _errors.report(extras, errors)
    mtsv.dumps(sheets)
    return sheets


def _manifest() -> str:
    """Generate META-INF/manifest.xml, ODF 1.3 Part 2, 3.2.

    Return its XML.
    """
    return (
        "<?xml version='1.0' encoding='UTF-8'?>"
        f"<manifest:manifest xmlns:manifest='{_MANIFEST}'"
        " manifest:version='1.3'>"
        "<manifest:file-entry manifest:full-path='/'"
        f" manifest:media-type='{_odf.MEDIA_TYPE}'/>"
        "<manifest:file-entry manifest:full-path='content.xml'"
        " manifest:media-type='text/xml'/>"
        "</manifest:manifest>"
    )


def _document_content(sheets: list[dict[str, Any]]) -> str:
    """Generate content.xml.

    sheets -- the MTSV sheets

    Return its XML.
    """
    return (
        "<?xml version='1.0' encoding='UTF-8'?>"
        f"<office:document-content{_odf.ROOT_ATTRIBUTES}>"
        f"{_odf.body(sheets)}"
        "</office:document-content>"
    )
