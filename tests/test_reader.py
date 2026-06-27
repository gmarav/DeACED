"""Unit tests for the low-level byte Reader."""

import pytest

from deaced.errors import TruncatedStreamError
from deaced.reader import Reader


def test_unsigned_reads():
    r = Reader(bytes.fromhex("01 0203 04050607 08090a0b0c0d0e0f".replace(" ", "")))
    assert r.u8() == 0x01
    assert r.u16() == 0x0203
    assert r.u32() == 0x04050607
    assert r.u64() == 0x08090A0B0C0D0E0F


def test_position_and_peek():
    r = Reader(b"\xaa\xbb")
    assert r.pos == 0
    assert r.peek() == 0xAA
    assert r.pos == 0  # peek does not advance
    assert r.u8() == 0xAA
    assert r.pos == 1
    assert r.remaining() == 1
    assert r.u8() == 0xBB
    assert r.peek() is None


def test_read_chunk():
    r = Reader(b"ABCD")
    assert r.read(3) == b"ABC"
    assert r.pos == 3
    assert r.remaining() == 1


def test_truncation_raises_with_offset():
    r = Reader(b"\x01\x02")
    r.u8()
    with pytest.raises(TruncatedStreamError) as exc:
        r.u32()
    assert exc.value.offset == 1
