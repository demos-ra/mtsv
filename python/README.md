# MTSV for Python

A parser and a generator for Multi-Sheet Tab-Separated Values (MTSV),
with integrations for CSV, JSON, spreadsheets (ODS and XLSX), databases
(SQLite) and data tools (Apache Arrow, Parquet and Arrow IPC). The
version is the `version` field of `pyproject.toml`.

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

For the Arrow, Parquet and Arrow IPC integrations, which also install
pyarrow:

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
`.json`, `.ods`, `.xlsx`, `.sqlite`, `.parquet` and `.arrow` convert to
one another. Options come before the operands, and `-` is standard
input or standard output:

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

## Databases (SQLite)

```python
from mtsv.integrations import sqlite

with open("book.sqlite", "wb") as file:
    sqlite.dump(sheets, file)

with open("book.sqlite", "rb") as file:
    sheets = sqlite.load(file)
```

From the command line:

```
mtsv book.mtsv book.sqlite
mtsv book.sqlite book.mtsv
```

One table per sheet, its column names the header and its rows the
records. Views, indexes and triggers are left behind, as are the
objects SQLite keeps for itself, whose names begin with `sqlite_`.

## Data tools (Apache Arrow)

```python
from mtsv.integrations import arrow

tables = arrow.to_arrow(sheets)
sheets = arrow.from_arrow(tables)
```

`tables` is a list of `(sheet name, pyarrow.Table)` pairs.

## Data tools (Parquet and Arrow IPC)

```python
from mtsv.integrations import parquet

with open("book.parquet", "wb") as file:
    parquet.dump(sheets, file)

with open("book.parquet", "rb") as file:
    sheets = parquet.load(file)
```

`arrow_ipc` reads and writes `.arrow` files the same way.

A Parquet file holds one schema, and an Arrow IPC file holds one schema
for every record batch in it, so each carries a single sheet whose
sheet name is empty, as a CSV file does. To carry a workbook of several
sheets, take `to_arrow` and write one file per pair.

## What is left behind

MTSV holds sheets, names, rows, and text. Everything else is left at the
door, and each door reports what it dropped.

Going out, a format refuses what it cannot hold. ODS and XLSX both
raise `ValueError` for a character that XML 1.0 does not allow. XLSX
also raises for a file with no sheets, for two sheets with one sheet
name, and for a sheet wider than 16,384 columns or longer than
1,048,576 rows, because a workbook holds none of those. CSV, Parquet
and Arrow IPC each hold one table with nowhere to write a sheet name,
so each raises for a file of more than one sheet or a sheet name that
is not empty; CSV also raises for a sheet with no lines, holding at
least one record. SQLite raises for a sheet with no lines, because a
table has at least one column; for a header that repeats a field name,
because column names are unique; for two sheets with one sheet name;
for a sheet name beginning `sqlite_`, which SQLite reserves; and for a
sheet name or header field holding U+0000, which cannot be written
into a statement. JSON holds everything MTSV holds, so it refuses
nothing.

Coming back in, whatever the other format holds that MTSV does not —
formatting, formulas, types, styles, and the parts that carry them — is
left behind. From SQLite that is views, indexes, triggers and the
objects named `sqlite_`; from a workbook or a table it is the type of
every value that is not already text. `load` raises `ValueError` rather
than drop any of it, unless it is passed `errors="ignore"`. The command
drops it and names it on standard error instead, because the person
running it is reading the report; `--errors strict` makes the command
refuse it too.

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
always raises `ValueError`. So does a value with no text form at all: a
SQLite BLOB, or an Arrow column of binary, a list, or a struct.

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
    arrow          how Arrow types become text
    csv · json · ods · xlsx · sqlite    one outside format each
    arrow_ipc · parquet                 one Arrow-backed format each
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
