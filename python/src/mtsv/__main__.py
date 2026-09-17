"""Convert a file to another format, through MTSV sheets.

Functions:
main -- convert a file to another format, by their file extensions
"""

__all__ = ["main"]

from mtsv import _command
from mtsv.integrations import FORMATS

_INTEGRATIONS = {
    suffix: (module.load, module.dump)
    for suffix, module in FORMATS.items()
}


def main(argv: list[str] | None = None) -> None:
    """Convert a file to another format, by their file extensions."""
    _command.run(
        "mtsv",
        "Convert a file to another format, by their file extensions.",
        _INTEGRATIONS,
        argv,
    )


if __name__ == "__main__":
    main()
