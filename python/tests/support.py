"""Shared helpers for the tests: the conformance files."""

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
