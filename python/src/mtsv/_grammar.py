"""The characters of MTSV, following the draft, Grammar.

Constants:
HTAB -- the tab, %x09
LF -- the line feed, %x0A
FF -- the form feed, %x0C
CR -- the carriage return, %x0D
CRLF -- a carriage return followed by a line feed

Functions:
field_char -- return whether a character is a field-char
"""

__all__ = ["HTAB", "LF", "FF", "CR", "CRLF", "field_char"]

HTAB = chr(0x09)
LF = chr(0x0A)
FF = chr(0x0C)
CR = chr(0x0D)
CRLF = CR + LF


def field_char(char: str) -> bool:
    """Return whether a character is a field-char.

    char -- one character

    field-char = %x00-08 / %x0B / %x0E-10FFFF
    """
    code = ord(char)
    return 0x00 <= code <= 0x08 or code == 0x0B or 0x0E <= code <= 0x10FFFF
