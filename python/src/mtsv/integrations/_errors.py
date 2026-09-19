"""Refuse or report what an integration leaves behind.

Functions:
lookup_error -- refuse an error handler name other than strict or ignore
report -- refuse or report what an integration would leave behind
"""

__all__ = ["lookup_error", "report"]

import logging

_logger = logging.getLogger("mtsv.integrations")


def lookup_error(name: str) -> None:
    """Refuse an error handler name other than strict or ignore.

    name -- the errors argument given to a load

    Raise LookupError for any other name. Python codecs, Error
    Handlers: lookup_error "Raises a LookupError in case the handler
    cannot be found".
    """
    if name not in ("strict", "ignore"):
        raise LookupError(f"unknown error handler name {name!r}")


def report(extras: set[str], errors: str) -> None:
    """Refuse or report what an integration would leave behind.

    extras -- the names of what would be left behind
    errors -- "strict" or "ignore"

    Raise ValueError with errors="strict". Otherwise log a warning
    whose record carries the sorted names in its left_behind attribute.

    Logging HOWTO, When to use logging: a logger's warning() "if there
    is nothing the client application can do about the situation, but
    the event should still be noted". logging, Logger.debug: extra
    populates the LogRecord "with user-defined attributes".
    """
    if not extras:
        return
    names = sorted(extras)
    joined = ", ".join(names)
    if errors == "strict":
        raise ValueError(f"these would be left behind: {joined}")
    _logger.warning("left behind: %s", joined, extra={"left_behind": names})
