"""Tests for Java modified-UTF-8 (deaced.mutf8) and its use by the parser.

Non-ASCII characters are built with chr() to keep this source ASCII-only.
"""

from deaced import dump
from deaced.mutf8 import decode, encode

EMOJI = chr(0x1F600)  # U+1F600, outside the BMP
REPLACEMENT = chr(0xFFFD)


def test_ascii_roundtrip():
    s = "Hello, World!"
    assert encode(s) == s.encode("ascii")
    assert decode(s.encode("ascii")) == s


def test_nul_is_c0_80():
    # The defining quirk: U+0000 is two bytes, and standard UTF-8 can't read it.
    assert encode("\x00") == b"\xc0\x80"
    assert decode(b"\xc0\x80") == "\x00"
    assert b"\xc0\x80".decode("utf-8", errors="replace") != "\x00"


def test_bmp_matches_standard_utf8():
    # For BMP, non-zero characters mUTF-8 is byte-identical to standard UTF-8.
    for cp in [0x00FC, 0x0416, 0x4E2D, 0x0080, 0x07FF, 0x0800, 0xFFFF]:
        s = chr(cp)
        assert encode(s) == s.encode("utf-8")
        assert decode(s.encode("utf-8")) == s


def test_supplementary_uses_surrogate_pair():
    s = EMOJI
    enc = encode(s)
    assert enc == bytes.fromhex("eda0bdedb880")  # CESU-8 / mUTF-8 surrogate pair
    assert decode(enc) == s
    # standard UTF-8 uses a 4-byte form and cannot decode the 6-byte one
    assert s.encode("utf-8") == bytes.fromhex("f09f9880")
    assert enc.decode("utf-8", errors="replace") != s


def test_roundtrip_mixed():
    s = "A" + chr(0) + chr(0x0416) + EMOJI + "Z"
    assert decode(encode(s)) == s


def test_lone_surrogate_passes_through():
    assert decode(b"\xed\xa0\x80") == chr(0xD800)


def test_malformed_yields_replacement():
    assert decode(b"\xff") == REPLACEMENT
    assert decode(b"\xc0") == REPLACEMENT  # truncated two-byte sequence


def test_parser_decodes_supplementary_string():
    payload = encode("A" + EMOJI)  # 1 + 6 = 7 bytes
    stream = bytes.fromhex("aced000574") + len(payload).to_bytes(2, "big") + payload
    out = dump(stream)
    assert ("Value - A" + EMOJI + " - 0x41eda0bdedb880") in out
