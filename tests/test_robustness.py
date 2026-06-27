"""Robustness on adversarial / malformed input.

DeACED exists to parse untrusted, attacker-controlled serialization streams, so
it must fail cleanly -- a :class:`SerDumpError`, never a process crash or an
unencodable output string -- rather than propagate a low-level exception.
"""

import struct

import pytest

from deaced import dump, parse
from deaced.errors import IllegalStateError, SerDumpError
from deaced.model import StringVal
from deaced.parser import run_deep

# TC_STRING whose modified-UTF-8 bytes ED A0 80 decode to a lone high surrogate
# U+D800 (legal in a Java String, unencodable as UTF-8). The reference jar
# prints '?'; DeACED keeps the surrogate in the AST but sanitizes it on render.
SURROGATE_HEX = "aced0005740003eda080"


# --- H1: lone surrogates must never break UTF-8 output ---


@pytest.mark.parametrize("fmt", ["text", "json", "pretty"])
def test_lone_surrogate_output_is_utf8_encodable(fmt: str) -> None:
    out = dump(bytes.fromhex(SURROGATE_HEX), format=fmt)
    out.encode("utf-8")  # must not raise UnicodeEncodeError
    assert "?" in out
    assert not any(0xD800 <= ord(c) <= 0xDFFF for c in out)


def test_lone_surrogate_preserved_in_ast() -> None:
    # parse() keeps the faithful surrogate; only rendering sanitizes it.
    node = parse(bytes.fromhex(SURROGATE_HEX)).contents[0]
    assert isinstance(node, StringVal)
    assert node.value == "\ud800"


# --- M2/M3: negative structural sizes/counts are rejected, not mis-handled ---


def test_negative_array_size_rejected() -> None:
    # TC_ARRAY of "[B" with size 0xFFFFFFFF (signed -1).
    data = "aced0005757200025b4200000000000000000200007870ffffffff"
    with pytest.raises(IllegalStateError, match="negative array size"):
        dump(bytes.fromhex(data))


def test_negative_blockdatalong_length_rejected() -> None:
    with pytest.raises(IllegalStateError, match="negative block data length"):
        dump(bytes.fromhex("aced00057affffffff"))


def test_negative_field_count_rejected() -> None:
    data = "aced000572000141000000000000000002ffff"
    with pytest.raises(IllegalStateError, match="negative field count"):
        dump(bytes.fromhex(data))


def test_negative_proxy_interface_count_rejected() -> None:
    with pytest.raises(IllegalStateError, match="negative proxy interface count"):
        dump(bytes.fromhex("aced00057dffffffff"))


def test_negative_longstring_length_rejected() -> None:
    with pytest.raises(IllegalStateError, match="negative long string length"):
        dump(bytes.fromhex("aced00057cffffffffffffffff"))


# --- L6: error messages distinguish a real 0x00 tag from end-of-stream ---


def test_eof_reported_as_eof_not_zero() -> None:
    # A classdesc that ends right before its class annotations: the annotation
    # read peeks past end-of-stream. The message must say EOF, not "0x00".
    data = "aced0005720001410000000000000000020000"
    with pytest.raises(SerDumpError, match="EOF"):
        dump(bytes.fromhex(data))


def test_illegal_tag_reports_hex() -> None:
    with pytest.raises(SerDumpError, match="0xff"):
        dump(bytes.fromhex("aced0005ff"))


# --- L7: deep nesting must not crash the interpreter ---


def test_deeply_nested_input_parses_with_large_stack() -> None:
    # 5000 nested TC_EXCEPTION then a string. The default recursion limit (1000)
    # would fail; run_deep() gives the worker a large stack + high limit.
    data = bytes.fromhex("aced0005") + b"\x7b" * 5000 + bytes.fromhex("74000158")
    root = parse(data)
    assert root.magic_valid


def test_run_deep_returns_value() -> None:
    assert run_deep(lambda: 42) == 42


def test_run_deep_converts_recursion_error() -> None:
    def boom(n: int = 0) -> int:
        return boom(n + 1)

    with pytest.raises(IllegalStateError, match="maximum nesting depth"):
        run_deep(boom)


def test_run_deep_propagates_other_errors() -> None:
    def boom() -> int:
        raise ValueError("kaboom")

    with pytest.raises(ValueError, match="kaboom"):
        run_deep(boom)


# --- offsets are a text-only feature ---


def test_offsets_rejected_for_non_text() -> None:
    with pytest.raises(ValueError, match="offsets are only supported"):
        dump(bytes.fromhex(SURROGATE_HEX), format="json", offsets=True)


# --- subnormal floats round-trip (documented divergence from Java) ---


def test_subnormals_round_trip() -> None:
    from deaced.jfloat import double_to_string, float_to_string

    for bits in (1, 2, 3):
        v = struct.unpack(">d", bits.to_bytes(8, "big"))[0]
        assert float(double_to_string(v)) == v
    for bits in (1, 2, 3, 7):
        v = struct.unpack(">f", bits.to_bytes(4, "big"))[0]
        # a float string round-trips through float32, not double
        assert struct.unpack(">f", struct.pack(">f", float(float_to_string(v))))[0] == v
