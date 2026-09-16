# MTSV for Python

A parser and a generator for Multi-Sheet Tab-Separated Values (MTSV), with
integrations for spreadsheets (ODS) and data tools (Apache Arrow). The
version is the `version` field of `pyproject.toml`.

* [Specification](https://github.com/demos-ra/mtsv-spec)
* [Repository](https://github.com/demos-ra/mtsv)

## Install

```
pip install mtsv
```

For the Arrow integration, which also installs pyarrow:

```
pip install "mtsv[arrow]"
```

A Python that an operating system manages does not accept packages
directly, so install into a virtual environment:

```
python3 -m venv .venv
.venv/bin/pip install mtsv
```

To install from a clone instead, run the same commands from the root of
the repository with `./python` in place of `mtsv`.

## Read and write MTSV

Sheets are a list of dictionaries with `"sheet name"`, `"header"`, and
`"records"`, the same shape as the
[conformance results](https://github.com/demos-ra/mtsv/blob/main/conformance/README.md).

```python
import mtsv

with open("book.mtsv", "rb") as file:
    sheets = mtsv.load(file)

with open("book.mtsv", "wb") as file:
    mtsv.dump(sheets, file)
```

`loads` and `dumps` work on strings.

## Spreadsheets (ODS)

```python
from mtsv.integrations import ods

with open("book.ods", "wb") as file:
    ods.dump(sheets, file)

with open("book.ods", "rb") as file:
    sheets = ods.load(file)
```

From the command line:

```
python -m mtsv.integrations.ods book.mtsv book.ods
python -m mtsv.integrations.ods book.ods book.mtsv
```

## Data tools (Apache Arrow)

```python
from mtsv.integrations import arrow

tables = arrow.to_arrow(sheets)
sheets = arrow.from_arrow(tables)
```

`tables` is a list of `(sheet name, pyarrow.Table)` pairs.

## What is left behind

MTSV holds sheets, names, rows, and text. Going out to ODS or Arrow keeps all
of it, with two ODS exceptions: characters that XML 1.0 does not allow raise
`ValueError`, and empty rows and columns at the edge of a sheet do not come
back from ODS, so a sheet of only empty fields comes back as an empty sheet.
Coming back in, anything else (formatting, formulas, types, missing values)
raises `ValueError` by default. To confirm and leave it behind, pass
`errors="ignore"`, or `--errors ignore` on the command line. Text that MTSV
cannot hold, such as a tab or line break inside a value, always raises
`ValueError`. So does an Arrow column whose values cannot be text at all, such
as binary, a list, or a struct.

## Layout

| Path                     | Contents                                    |
|--------------------------|---------------------------------------------|
| `src/mtsv/`              | the interface, the parser, and the generator |
| `src/mtsv/integrations/` | one module per target standard              |
| `tests/`                 | the test suite, run against the install     |

## Test

From the root of the repository:

```
.venv/bin/python -m unittest discover -s python/tests
```

## License

[MIT](https://github.com/demos-ra/mtsv/blob/main/LICENSE)
