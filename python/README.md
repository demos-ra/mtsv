# MTSV for Python

A parser and a generator for Multi-Sheet Tab-Separated Values (MTSV),
with integrations for CSV, JSON, spreadsheets (ODS and XLSX) and data
tools (Apache Arrow). The version is the `version` field of
`pyproject.toml`.

* [Specification](https://github.com/demos-ra/mtsv-spec)
* [Repository](https://github.com/demos-ra/mtsv)

## Install

The `mtsv` command, in an environment of its own:

```
pipx install mtsv
```

The library, in a virtual environment:

```
python3 -m venv .venv
.venv/bin/pip install mtsv
```

For the Arrow integration, which also installs pyarrow:

```
.venv/bin/pip install "mtsv[arrow]"
```

To install from a clone instead, run the same commands from the root of
the repository with `./python` in place of `mtsv`.

## Convert files

```
mtsv book.xlsx
```

That writes `book.mtsv` beside it. Name the output to choose the format,
or the name:

```
mtsv book.xlsx book.mtsv
mtsv book.mtsv book.ods
```

The file extensions name the formats, so any two of `.mtsv`, `.csv`,
`.json`, `.ods` and `.xlsx` convert to one another. Options come
before the operands, and `-` is standard input or standard output:

```
mtsv -e strict book.xlsx book.mtsv
mtsv book.xlsx -
```

The output file can also be named with `-o`, or `--output`:

```
mtsv -o book.mtsv book.xlsx
```

A conversion that cannot carry everything still converts, and says on
standard error what it left behind. `-e strict`, or `--errors strict`,
refuses it instead. A stream carries MTSV, because it has no file
extension to name another format, and the output must be named where
there is no name to derive: a stream, or MTSV already.

`mtsv.integrations.FORMATS` is deprecated and will be removed in
0.6.0; use `mtsv.integrations.lookup` instead.

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
beside every conforming `.mtsv` file.

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
from, so it reads and writes a sheet whose sheet name is empty, as a
TSV file does. A file of more than one sheet, whose sheet
name is not empty, or whose sheet has no lines, raises `ValueError`.

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
mtsv book.mtsv book.ods
mtsv book.ods book.mtsv
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
mtsv book.mtsv book.xlsx
mtsv book.xlsx book.mtsv
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
1.0 does not allow. XLSX also raises for a file with no sheets, for two
sheets with one sheet name, and for a sheet wider than 16,384 columns or
longer than 1,048,576 rows, because a workbook holds none of those. CSV raises for a file of more than one
sheet, whose sheet name is not empty, or whose sheet has no lines,
because CSV holds one table of at least one record and no sheet name.
JSON holds everything MTSV holds, so it refuses nothing.

Coming back in, whatever a spreadsheet holds that MTSV does not —
formatting, formulas, types, styles, and the parts that carry them —
is left behind. `load` raises `ValueError` rather than drop it, unless
it is passed `errors="ignore"`. The command drops it and names it on
standard error instead, because the person running it is reading the
report; `--errors strict` makes the command refuse it too.

The report goes to the `mtsv.integrations` logger at level WARNING, as
`left behind: a, b`. Its record also carries the names, sorted, as a
list in its `left_behind` attribute, so a program can collect them with
a handler of its own.

Two differences are worth knowing. Empty rows and columns at the edge of
an ODS sheet do not come back, so an ODS sheet of only empty fields comes
back as an empty sheet; XLSX keeps them, because a workbook may leave a
cell out entirely. And a workbook holds a date as a serial number, with
the date format kept apart from it, so a cell showing `Jan-23` comes back
from XLSX as `44927` where ODS gives `2023-01-01`.

Text that MTSV cannot hold, such as a tab or line break inside a value,
always raises `ValueError`. So does an Arrow column whose values cannot be
text at all, such as binary, a list, or a struct.

## Layout

Each module hides one decision, named beside it. "core" and "command"
are groups of files in `src/mtsv/`, not folders.

```
src/mtsv/
  core
    _grammar       which characters MTSV uses
    _parser        how text becomes sheets
    _generator     how sheets become text
    __init__       the public shape: dump, dumps, load, loads
  integrations/
    _xml           what XML 1.0 allows in names and characters
    _sheet         how the lines of a table become a sheet
    _errors        the errors values, and how loss is reported
    csv · json · ods · xlsx · arrow     one outside format each
    __init__       which extension names which format
  command
    _command       how a person runs a conversion
    __main__       the mtsv entry point
tests/             one test file per module above
```

## Test

From the root of the repository:

```
python3 -m venv .venv
.venv/bin/pip install "./python[arrow]"
.venv/bin/python -m unittest discover -s python/tests
```

## License

[MIT](https://github.com/demos-ra/mtsv/blob/main/LICENSE)
