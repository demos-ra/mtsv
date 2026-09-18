# MTSV

Multi-Sheet Tab-Separated Values (MTSV) is TSV with one more dimension: a tab
separates fields, a line break separates records, and a form feed separates
sheets. This repository holds the conformance test files and the
implementations.

* [Specification](https://github.com/demos-ra/mtsv-spec)
* [Internet-Draft on the IETF Datatracker](https://datatracker.ietf.org/doc/draft-demosra-mtsv/)

## Layout

| Folder         | Contents                                                |
|----------------|---------------------------------------------------------|
| `conformance/` | Test files shared by every implementation               |
| `python/`      | Python implementation, with the `mtsv` command and CSV, JSON, ODS, XLSX and Apache Arrow integrations |

Each language folder holds one implementation of the specification: a parser
and a generator. Integrations connect an implementation to other standards,
and a command lets a person use it from a terminal. Conformance is the same
for every language, so it sits beside them rather than inside one.

## Conformance

See [conformance/README.md](conformance/README.md).

## Python

See [python/README.md](python/README.md) to install and use the package. Its
version is the `version` field of
[python/pyproject.toml](python/pyproject.toml).

## Status

Released on PyPI as [mtsv](https://pypi.org/project/mtsv/). Versions follow
[Semantic Versioning](https://semver.org).

## License

[MIT](LICENSE)
