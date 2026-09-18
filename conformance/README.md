# Conformance

Every implementation is tested against the same files. Results are JSON
(RFC 8259), compared as values: an array of sheets, each with
`"sheet name"`, `"header"`, and `"records"`. Each result is written with
no white space except one final line feed. Every field and sheet name is
a JSON string. An empty sheet has `"header":null` and `"records":[]`; a
file with no sheets, as the lines before the first form feed (FF) form a
sheet only if there are any, is `[]`. The results assume the
specification's two recommendations: a parser drops a U+FEFF at the
start of a file, and a generator writes UTF-8.

| Folder                    | Files                         | An implementation must                                              |
|---------------------------|-------------------------------|---------------------------------------------------------------------|
| `conforming/`             | `name.mtsv` with `name.json`  | parse `name.mtsv` to `name.json`, and generate from `name.json` a conforming file with an FF line before every sheet, that parses back to it |
| `non-conforming/`         | `name.mtsv`                   | nothing: these files are not MTSV, and a parser may accept or reject them |
| `cannot-be-represented/`  | `name.json`                   | not write these values or sheets                                    |
