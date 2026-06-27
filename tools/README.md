# Developer tools

## Golden fixtures

`tests/data/*.ser` are synthetic Java serialization streams; `tests/data/*.golden`
are their expected text dumps. The golden tests (`tests/test_golden.py`) assert
that DeACED reproduces each dump byte-for-byte.

The goldens are produced by the **patched** SerializationDumper jar, which is the
reference DeACED is validated against. That jar is not shipped here.

### Regenerate

Requires a JDK on `PATH` (tested on Temurin 25 LTS) and the patched jar:

```bash
SERDUMP_JAR=/path/to/SerializationDumper-PATCHED.jar tools/regen_goldens.sh
```

This compiles and runs [`GenerateFixtures.java`](GenerateFixtures.java) to emit
the `.ser` files, then runs the jar over each to (re)write the `.golden` files.

All fixture data is synthetic (no PII). When you add a fixture, add a
`write(...)` call in `GenerateFixtures.java` and re-run the script.
