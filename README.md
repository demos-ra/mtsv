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

## Status

Structure only. No releases yet.

## License

[MIT](LICENSE)
