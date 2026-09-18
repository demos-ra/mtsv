"""Match XML 1.0 characters, for the ODS and XLSX integrations."""

from typing import Any
from xml.etree import ElementTree


def check_chars(sheets: list[dict[str, Any]], format_name: str) -> None:
    """Refuse a sheet name or field holding a character not a Char."""
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
    """Match XML 1.0 Char.

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


def prefixed(name: str, prefixes: dict[str, str]) -> str:
    """Return {namespace}local as prefix:local for known prefixes."""
    if not name.startswith("{"):
        return name
    namespace, local = name[1:].split("}", 1)
    prefix = prefixes.get(namespace)
    if prefix is None:
        return name
    return local if not prefix else f"{prefix}:{local}"


def note_attributes(
    element: ElementTree.Element,
    allowed: tuple[str, ...],
    extras: set[str],
    prefixes: dict[str, str],
) -> None:
    """Record each attribute outside the MTSV mapping as left behind."""
    for key in element.attrib:
        if key not in allowed:
            extras.add(prefixed(key, prefixes))
