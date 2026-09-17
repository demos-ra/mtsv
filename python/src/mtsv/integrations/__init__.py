"""Conversions between MTSV and other standards.

Modules:
arrow -- convert between MTSV sheets and Apache Arrow tables
csv -- convert between MTSV sheets and CSV
json -- convert between MTSV sheets and JSON
ods -- convert between MTSV sheets and OpenDocument spreadsheets
xlsx -- convert between MTSV sheets and OOXML workbooks

Constants:
FORMATS -- the integration module that reads and writes each extension
"""

__all__ = ["FORMATS"]

from mtsv.integrations import csv, json, ods, xlsx

# The extension each media type registration declares: "CSV" in
# Section 5.1 of RFC 7111, ".json" in Section 11 of RFC 8259, "ods"
# for the OpenDocument spreadsheet type, and "xlsx" for the OOXML
# spreadsheet type. Arrow is not here, because its integration is
# between MTSV sheets and tables in memory, not a file format.
FORMATS = {".csv": csv, ".json": json, ".ods": ods, ".xlsx": xlsx}
