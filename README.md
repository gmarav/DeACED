# DeACED

[![CI](https://github.com/gmarav/DeACED/actions/workflows/ci.yml/badge.svg)](https://github.com/gmarav/DeACED/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/deaced)](https://pypi.org/project/deaced/)
[![Python versions](https://img.shields.io/pypi/pyversions/deaced)](https://pypi.org/project/deaced/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

> Dump and inspect **Java Object Serialization** (`0xAC 0xED`) streams — and Java RMI
> packet contents — in a clear, human-readable, hierarchical form.

`DeACED` (a nod to the `AC ED` stream magic, and to *de*-serialization) is a small,
**dependency-free** Python library and CLI. It is a port of
[SerializationDumper](https://github.com/NickstaDB/SerializationDumper) by Nicky Bloor,
with several correctness fixes (see [NOTICE](NOTICE)).

## Install

```bash
pip install deaced
# or from source:
pip install .
```

## CLI

```bash
deaced -r dump.bin                 # raw serialized file
cat dump.bin | deaced -r -         # from stdin
deaced -x aced0005740004414243...  # hex on the command line
deaced -f hexdump.txt              # file of hex-ascii bytes
deaced -r dump.bin --offsets       # prefix each line with '@<byte-offset>|'
deaced -r dump.bin -o out.txt      # write to a file
deaced -r dump.bin -F json         # structured, machine-readable JSON
deaced -r dump.bin -F pretty       # compact, human-readable data tree
```

Example:

```text
$ deaced -x aced0005740004414243447071007e0000

STREAM_MAGIC - 0xac ed
STREAM_VERSION - 0x00 05
Contents
  TC_STRING - 0x74
    newHandle 0x00 7e 00 00
    Length - 4 - 0x00 04
    Value - ABCD - 0x41424344
  TC_NULL - 0x70
  TC_REFERENCE - 0x71
    Handle - 8257536 - 0x00 7e 00 00
```

## Library

```python
from deaced import dump, parse

data = open("dump.bin", "rb").read()

print(dump(data))                       # text dump (default)
print(dump(data, offsets=True))         # with '@<offset>|' prefixes
print(dump(data, format="json"))        # structured JSON
print(dump(data, format="pretty"))      # compact human-readable tree

tree = parse(data)                      # the semantic AST (deaced.model.Stream)
```

## Why a port?

Removes the JVM dependency (the original is a Java jar), runs anywhere Python does,
integrates into Python tooling, and fixes real bugs in the original — most notably
the `(long)`/`(double)` integer-shift bug (`0xFFFFFFFFFFFFFFFF` was shown as
`-4294967297` instead of `-1`). See [NOTICE](NOTICE) for the full list.

## Safety

DeACED is built to inspect **untrusted, attacker-controlled** serialization
streams (that is the usual reason to dump one), so:

- **It never deserializes Java objects.** DeACED only reads and decodes the byte
  stream into a descriptive tree — it does not load classes, instantiate objects,
  or invoke `readObject`. The classic Java deserialization gadget chains cannot
  fire through it.
- **It fails cleanly on malformed input.** Truncated or structurally-invalid
  streams raise a `SerDumpError` carrying the byte offset; negative
  lengths/counts are rejected rather than driving huge allocations; deeply nested
  streams raise an error instead of crashing the interpreter.

Resource use is still proportional to input size — apply your own limits when
dumping data straight off the network. See [SECURITY.md](SECURITY.md).

## Development

```bash
pip install -e ".[dev]"
pytest            # tests (tiny synthetic fixtures)
ruff check .
ruff format --check .
mypy
```

## Contributing

Contributions welcome — see [CONTRIBUTING](CONTRIBUTING.md). The stream "rebuild"
(`-b`) mode of the original is intentionally not ported (see [NOTICE](NOTICE)).

## Credits & license

Python port by **Alexander Gmar** ([@gmarav](https://github.com/gmarav)) —
[github.com/gmarav/DeACED](https://github.com/gmarav/DeACED).
Based on **SerializationDumper** by **Nicky Bloor** ([@NickstaDB](https://github.com/NickstaDB)).
Licensed under the [MIT License](LICENSE); port © 2026 Alexander Gmar, original © 2017 Nicky Bloor.
