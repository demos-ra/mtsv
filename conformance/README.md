# Conformance

Every implementation is tested against the same files. Results are JSON
(RFC 8259): an array of sheets, each with `"sheet name"`, `"header"`, and
`"records"`.

| Folder                    | Files                         | An implementation must                                              |
|---------------------------|-------------------------------|---------------------------------------------------------------------|
| `conforming/`             | `name.mtsv` with `name.json`  | parse `name.mtsv` to `name.json`, and generate a conforming file from `name.json` that parses back to it |
| `non-conforming/`         | `name.mtsv`                   | nothing: these files are not MTSV, and a parser may accept or reject them |
| `cannot-be-represented/`  | `name.json`                   | not write these values or sheets                                    |
