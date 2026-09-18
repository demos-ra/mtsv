"""The characters of MTSV, following the draft, Grammar."""

HTAB = chr(0x09)
LF = chr(0x0A)
FF = chr(0x0C)
CR = chr(0x0D)
CRLF = CR + LF


def field_char(char: str) -> bool:
    """Match: field-char = %x00-08 / %x0B / %x0E-10FFFF."""
    code = ord(char)
    return 0x00 <= code <= 0x08 or code == 0x0B or 0x0E <= code <= 0x10FFFF
