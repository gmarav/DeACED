# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-06-27

First public release.

### Added
- Python port of [NickstaDB/SerializationDumper](https://github.com/NickstaDB/SerializationDumper)
  as a dependency-free library + CLI.
- Public API: `dump(data, *, format="text"|"json"|"pretty", offsets=False)` and
  `parse(data) -> Stream`, which returns a typed semantic AST (nodes mirror
  protocol entities; back-references are resolved against a handle table).
- Text dump byte-for-byte compatible with the patched upstream jar; `--offsets`
  prefixes each line with its byte offset.
- JSON renderer (structured, machine-readable) and pretty renderer (compact data
  tree); CLI `deaced -r/-f/-x [-o FILE] [-F text|json|pretty] [--offsets]`, stdin.
- Layered architecture: `reader` (byte reader), `tags` (`TC`/`SC` enums),
  `parser` (stream → AST), `model` (the AST), `render/` (visitors), with
  dedicated exceptions that carry the byte offset.

### Fixed / improved (vs upstream)
- `(long)`/`(double)` integer-shift bug: bytes are widened before shifting, so
  `0xFFFFFFFFFFFFFFFF` reads as `-1` (not `-4294967297`).
- `TC_LONGSTRING` accepted as an object-field value; `TC_BLOCKDATA` /
  `TC_BLOCKDATALONG` accepted as array-field values.
- Strings decoded as Java modified UTF-8 (`U+0000` as `C0 80`, supplementary
  characters as surrogate pairs); the original decoded byte-by-byte.
- `TC_RESET` (`0x79`) and `TC_EXCEPTION` (`0x7b`) are parsed; upstream aborts on
  both. `TC_RESET` restarts handle numbering as Java does.
- `float`/`double` rendered with Java's exact `Double.toString` /
  `Float.toString` notation (e.g. `1.0E7`, `1.5E-10`), not Python's `repr`.
- `long` field type code is labelled `Long - J` (the JVM type code, JVMS 4.3.2);
  upstream's `Long - L` is a typo (the dumped hex byte `0x4a` is already `J`).

### Hardened
- Output is always valid UTF-8: lone UTF-16 surrogates render as `?` (matching
  the jar); previously such a value could crash the CLI on write.
- Structurally-invalid streams (negative array sizes, field/interface counts, or
  block-data/string lengths) are rejected with a clear `SerDumpError` instead of
  a misleading dump or a huge allocation attempt.
- Deeply nested streams parse with an enlarged worker-thread stack and raise a
  clean error past a generous depth limit, instead of crashing the interpreter.
- Parse errors distinguish end-of-stream (`EOF`) from a literal `0x00` tag.
- `--offsets` is validated as a text-format-only option.

[0.1.0]: https://github.com/gmarav/DeACED/releases/tag/v0.1.0
