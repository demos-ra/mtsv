# MTSV

Implementations and integrations for Multi-Sheet Tab-Separated Values (MTSV).

* [Specification](https://github.com/demos-ra/mtsv-spec)
* [Internet-Draft on the IETF Datatracker](https://datatracker.ietf.org/doc/draft-demosra-mtsv/)

## Layout

Each language folder holds one implementation of the specification: a parser
and a generator. Integrations connect an implementation to other standards.

| Folder         | Contents                                                |
|----------------|---------------------------------------------------------|
| `conformance/` | Test files shared by every implementation               |
| `python/`      | Python implementation, with ODS and Apache Arrow integrations |

## Python

### Install

From this repository:

```
pip install ./python
pip install "./python[arrow]"
```

The second line also installs pyarrow, for the Arrow integration.

### Read and write MTSV

Sheets are a list of dictionaries with `"sheet name"`, `"header"`, and
`"records"`, the same shape as the
[conformance results](conformance/README.md).

```python
import mtsv

with open("book.mtsv", "rb") as file:
    sheets = mtsv.load(file)

with open("book.mtsv", "wb") as file:
    mtsv.dump(sheets, file)
```

`loads` and `dumps` work on strings.

### Spreadsheets (ODS)

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

### Data tools (Apache Arrow)

```python
from mtsv.integrations import arrow

tables = arrow.to_arrow(sheets)
sheets = arrow.from_arrow(tables)
```

`tables` is a list of `(sheet name, pyarrow.Table)` pairs.

### What is left behind

MTSV holds sheets, names, rows, and text. Going out to ODS or Arrow keeps all
of it, with two ODS exceptions: control characters raise `ValueError`, and
empty rows at the end of a sheet do not come back from ODS. Coming back in,
anything else (formatting, formulas, types, missing values) raises
`ValueError` by default. To confirm and leave it behind, pass
`errors="ignore"`, or `--errors ignore` on the command line. Text that MTSV
cannot hold, such as a tab or line break inside a value, always raises
`ValueError`.

### Test

```
python -m unittest discover -s python/tests
```

## Conformance

See [conformance/README.md](conformance/README.md).

## Status

Python implementation with ODS and Apache Arrow integrations. Not yet released
on PyPI.

## License

[MIT](LICENSE)
