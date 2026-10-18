mtsv
====

Convert Excel (XLSX), ODS, CSV, JSON, SQLite, Parquet and Arrow files to and
from Multi-Sheet Tab-Separated Values (MTSV), with a Python library and the
mtsv command. MTSV is TSV with sheets: a whole Excel workbook becomes one
plain-text file that people, AI agents and tools such as diff and grep can
read. This repository holds the conformance tests and the implementations
of the [MTSV specification](https://github.com/demos-ra/mtsv-spec).

Why It Is Useful
----------------

One command converts between any two of eight formats, every sheet at once.
Whatever a format cannot carry, such as formatting or formulas, is named on
standard error instead of being dropped silently, and `-e strict` refuses
the conversion instead. Conformance tests shared by every implementation
fix what each file means.

Get Started
-----------

* Install the command: `pipx install mtsv`
* Convert Excel to MTSV: `mtsv book.xlsx`, which writes book.mtsv beside it
* Convert MTSV to another format: `mtsv book.mtsv book.ods`
* Use the library, and every format: [python/README.md](python/README.md)

Details
-------

* Specification: [MTSV, an IETF Internet-Draft](https://github.com/demos-ra/mtsv-spec)
* Requirements: Python 3.11 or later; for Parquet and Arrow, pyarrow, installed with `pipx install "mtsv[arrow]"`
* Version: the version field of [python/pyproject.toml](python/pyproject.toml); released on [PyPI](https://pypi.org/project/mtsv/); versions follow [Semantic Versioning](https://semver.org)
* Layout: [conformance/](conformance/README.md), the tests every implementation passes; [python/](python/README.md), the Python implementation
* License: [MIT](LICENSE)

Get Help
--------

* Issues: [mtsv issue tracker](https://github.com/demos-ra/mtsv/issues)
* Security: [SECURITY.md](SECURITY.md)
* Maintainer: Demos Ra
* More: [all MTSV tools by Demos Ra](https://github.com/demos-ra)
