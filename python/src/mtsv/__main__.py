"""Convert a file to another format, through MTSV sheets.

Functions:
main -- convert a file to another format, by their file extensions
"""

__all__ = ["main"]

from mtsv import _command


def main(argv: list[str] | None = None) -> None:
    """Convert a file to another format, by their file extensions.

    argv -- the arguments, or None for those of the process
    """
    _command.run(argv)


if __name__ == "__main__":
    main()
