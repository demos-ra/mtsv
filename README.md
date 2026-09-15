# MTSV

Codecs and adapters for Multi-Sheet Tab-Separated Values (MTSV).

* [Specification](https://github.com/demos-ra/mtsv-spec)
* [Internet-Draft on the IETF Datatracker](https://datatracker.ietf.org/doc/draft-demos-ra-mtsv/)

## Layout

Each container implements the specification for one runtime. Inside a
container, the codec reads and writes MTSV, and the adapters connect the codec
to other standards.

| Folder         | Contents                                           |
|----------------|----------------------------------------------------|
| `conformance/` | Test files shared by every codec                   |
| `python/`      | Python codec, with ODS and Apache Arrow adapters   |

## Conformance

Every codec is tested against the same files. Results are JSON (RFC 8259):
an array of sheets, each with `"sheet name"`, `"header"`, and `"records"`.

| Folder                               | Files                         | A codec must                                                        |
|--------------------------------------|-------------------------------|---------------------------------------------------------------------|
| `conformance/conforming/`            | `name.mtsv` with `name.json`  | parse `name.mtsv` to `name.json`, and generate a conforming file from `name.json` that parses back to it |
| `conformance/non-conforming/`        | `name.mtsv`                   | nothing: these files are not MTSV, and a parser may accept or reject them |
| `conformance/cannot-be-represented/` | `name.json`                   | not write these values                                              |

## Status

Conformance files only. No codec or releases yet.

## License

[MIT](LICENSE)
