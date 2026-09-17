# MTSV for Python

A parser and a generator for Multi-Sheet Tab-Separated Values (MTSV), with
integrations for spreadsheets (ODS and XLSX) and data tools (Apache Arrow).
The version is the `version` field of `pyproject.toml`.

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

## Convert files

```
mtsv book.xlsx book.mtsv
mtsv book.mtsv book.ods
```

The file extensions name the formats, so any two of `.mtsv`, `.csv`,
`.json`, `.ods` and `.xlsx` convert to one another. Options come
before the operands, and `-` is standard input or standard output:

```
mtsv -e ignore book.xlsx book.mtsv
mtsv book.xlsx -
```

The output file can also be named with `-o`, or `--output`:

```
mtsv -o book.mtsv book.xlsx
```

`-e ignore`, or `--errors ignore`, leaves behind whatever MTSV does not
hold instead of stopping. A stream carries MTSV, because it has no file
extension to name another format.

Each integration also has a module form of the same conversion, limited
to its own format, such as `python -m mtsv.integrations.ods`.

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

## JSON

The same sheets, written as JSON (RFC 8259). This is the form the
conformance results use, so a file written here is the file that sits
beside every `.mtsv` file in the corpus.

```python
from mtsv.integrations import json

with open("book.json", "wb") as file:
    json.dump(sheets, file)

with open("book.json", "rb") as file:
    sheets = json.load(file)
```

## CSV

```python
from mtsv.integrations import csv

with open("book.csv", "wb") as file:
    csv.dump(sheets, file)

with open("book.csv", "rb") as file:
    sheets = csv.load(file)
```

CSV holds one table and has nowhere to record which sheet it came
from, so it reads and writes the unnamed sheet — the same plane a TSV
file holds. A file of more than one sheet, or whose sheet has a name,
raises `ValueError`.

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

## Spreadsheets (XLSX)

```python
from mtsv.integrations import xlsx

with open("book.xlsx", "wb") as file:
    xlsx.dump(sheets, file)

with open("book.xlsx", "rb") as file:
    sheets = xlsx.load(file)
```

From the command line:

```
python -m mtsv.integrations.xlsx book.mtsv book.xlsx
python -m mtsv.integrations.xlsx book.xlsx book.mtsv
```

## Data tools (Apache Arrow)

```python
from mtsv.integrations import arrow

tables = arrow.to_arrow(sheets)
sheets = arrow.from_arrow(tables)
```

`tables` is a list of `(sheet name, pyarrow.Table)` pairs.

## What is left behind

MTSV holds sheets, names, rows, and text. Everything else is left at the
door, and each door reports what it dropped.

Going out, ODS and XLSX both raise `ValueError` for a character that XML
1.0 does not allow. XLSX also raises for a sheet with no name, for a file
with no sheets, and for a sheet wider than 16,384 columns or longer than
1,048,576 rows, because a workbook holds none of those. Begin a file with
a form feed and name every sheet, and it converts.

Coming back in, whatever a spreadsheet holds that MTSV does not —
formatting, formulas, types, styles, and the parts that carry them —
raises `ValueError` by default. To confirm and leave it behind, pass
`errors="ignore"`, or `--errors ignore` on the command line.

Two differences are worth knowing. Empty rows and columns at the edge of
an ODS sheet do not come back, so an ODS sheet of only empty fields comes
back as an empty sheet; XLSX keeps them, because a workbook may leave a
cell out entirely. And a workbook holds a date as a serial number, with
the date format kept apart from it, so a cell showing `Jan-23` comes back
from XLSX as `44927` where ODS gives `2023-01-15`.

Text that MTSV cannot hold, such as a tab or line break inside a value,
always raises `ValueError`. So does an Arrow column whose values cannot be
text at all, such as binary, a list, or a struct.

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
