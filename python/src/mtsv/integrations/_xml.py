"""XML 1.0 characters and namespace names, for ODS and XLSX.

Functions:
check_chars -- refuse a sheet name or field holding a non-Char
char -- return whether a character is an XML 1.0 Char
attributes_left_behind -- return the attributes outside the MTSV mapping
prefixed -- return {namespace}local as prefix:local for known prefixes
"""

__all__ = ["check_chars", "char", "attributes_left_behind", "prefixed"]

from typing import Any
from xml.etree import ElementTree


def check_chars(sheets: list[dict[str, Any]], format_name: str) -> None:
    """Refuse a sheet name or field holding a character not a Char.

    sheets -- the MTSV sheets
    format_name -- the format named in the error

    Raise ValueError for the first such character.
    """
    for sheet in sheets:
        values = [sheet["sheet name"]]
        for fields in [sheet["header"] or [], *sheet["records"]]:
            values.extend(fields)
        for value in values:
            if not all(char(c) for c in value):
                raise ValueError(
                    "a field or sheet name that contains a character not"
                    " allowed in XML 1.0 cannot be represented in"
                    f" {format_name}"
                )


def char(c: str) -> bool:
    """Return whether a character is an XML 1.0 Char.

    c -- one character

    XML 1.0, 2.2 Characters, production [2]:
    Char ::= #x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD]
             | [#x10000-#x10FFFF]
    """
    code = ord(c)
    return (
        code in (0x09, 0x0A, 0x0D)
        or 0x20 <= code <= 0xD7FF
        or 0xE000 <= code <= 0xFFFD
        or 0x10000 <= code <= 0x10FFFF
    )


def attributes_left_behind(
    element: ElementTree.Element,
    allowed: tuple[str, ...],
    prefixes: dict[str, str],
) -> set[str]:
    """Return the attributes outside the MTSV mapping.

    element -- the element read
    allowed -- the attribute names the mapping reads
    prefixes -- the prefix of each known namespace

    Return the other attribute names, each as prefix:local.
    """
    return {prefixed(key, prefixes) for key in element.attrib if key not in allowed}


def prefixed(name: str, prefixes: dict[str, str]) -> str:
    """Return {namespace}local as prefix:local for known prefixes.

    name -- a name as ElementTree gives it
    prefixes -- the prefix of each known namespace

    Return the name unchanged where its namespace is unknown. Namespaces
    in XML 1.0, 2.1 Basic Concepts: an expanded name is a pair of a
    namespace name and a local name.
    """
    if not name.startswith("{"):
        return name
    namespace, local = name[1:].split("}", 1)
    prefix = prefixes.get(namespace)
    if prefix is None:
        return name
    return local if not prefix else f"{prefix}:{local}"
