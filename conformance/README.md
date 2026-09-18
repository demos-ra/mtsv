# Conformance

Every implementation is tested against the same files. Results are JSON
(RFC 8259): an array of sheets, each with `"sheet name"`, `"header"`, and
`"records"`. Each result is written with no white space except one final
line feed.

| Folder                    | Files                         | An implementation must                                              |
|---------------------------|-------------------------------|---------------------------------------------------------------------|
| `conforming/`             | `name.mtsv` with `name.json`  | parse `name.mtsv` to `name.json`, and generate from `name.json` a conforming file with an FF line before every sheet, that parses back to it |
| `non-conforming/`         | `name.mtsv`                   | nothing: these files are not MTSV, and a parser may accept or reject them |
| `cannot-be-represented/`  | `name.json`                   | not write these values or sheets                                    |
