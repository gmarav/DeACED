"""Golden tests.

DeACED's text dump must match the patched SerializationDumper jar byte-for-byte
on a set of synthetic fixtures. The ``*.ser`` streams are produced by
``tools/GenerateFixtures.java`` and the ``*.golden`` dumps by running the jar
over them; see ``tools/README.md`` for how to regenerate. The data is fully
synthetic (no PII), so it is safe to ship in a public repository.
"""

from pathlib import Path

import pytest

from deaced import dump

DATA = Path(__file__).parent / "data"
CASES = sorted(p.stem for p in DATA.glob("*.ser"))


def test_fixtures_present() -> None:
    assert CASES, "no .ser fixtures found in tests/data"


@pytest.mark.parametrize("name", CASES)
def test_golden(name: str) -> None:
    data = (DATA / f"{name}.ser").read_bytes()
    expected = (DATA / f"{name}.golden").read_text(encoding="utf-8")
    assert dump(data) == expected
