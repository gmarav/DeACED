"""Tests for the DeACED parser/renderer.

Fixtures are tiny and synthetic (no third-party data) so the repo is safe to
publish. The "ABCD" stream is the canonical example from upstream's README.
"""

import struct

import pytest

from deaced import __version__, dump, parse
from deaced.model import Null, Reference, Stream, StringVal
from deaced.parser import Parser
from deaced.render.text import TextRenderer

# A serialized String "ABCD" followed by TC_NULL and a back-reference.
ABCD_HEX = "aced0005740004414243447071007e0000"
ABCD_LINES = [
    "STREAM_MAGIC - 0xac ed",
    "STREAM_VERSION - 0x00 05",
    "Contents",
    "  TC_STRING - 0x74",
    "    newHandle 0x00 7e 00 00",
    "    Length - 4 - 0x00 04",
    "    Value - ABCD - 0x41424344",
    "  TC_NULL - 0x70",
    "  TC_REFERENCE - 0x71",
    "    Handle - 8257536 - 0x00 7e 00 00",
]
ABCD_EXPECTED = "\n" + "\n".join(ABCD_LINES) + "\n"


def test_string_abcd_golden():
    assert dump(bytes.fromhex(ABCD_HEX)) == ABCD_EXPECTED


def test_parse_returns_semantic_tree():
    root = parse(bytes.fromhex(ABCD_HEX))
    assert isinstance(root, Stream)
    assert root.magic_valid and root.version_valid
    assert [type(c).__name__ for c in root.contents] == ["StringVal", "Null", "Reference"]
    s = root.contents[0]
    assert isinstance(s, StringVal) and s.value == "ABCD"
    assert isinstance(root.contents[1], Null)
    ref = root.contents[2]
    assert isinstance(ref, Reference)
    # the back-reference resolves to the string object
    assert ref.handle == s.handle
    assert ref.target is s
    assert root.handles[s.handle] is s


def test_node_offsets_record_source_positions():
    # ABCD_HEX: 4-byte header, then TC_STRING@4, TC_NULL@11, TC_REFERENCE@12
    root = parse(bytes.fromhex(ABCD_HEX))
    assert root.offset == 0
    string_node, null_node, ref_node = root.contents
    assert string_node.offset == 4
    assert null_node.offset == 11
    assert ref_node.offset == 12


def test_offsets_mode_prefixes_each_line():
    out = dump(bytes.fromhex(ABCD_HEX), offsets=True)
    # line 0 is the leading blank line; STREAM_MAGIC starts after the 2 magic bytes
    assert out.splitlines()[1].startswith("@2|STREAM_MAGIC - 0xac ed")


def test_long_has_no_int_shift_bug():
    # 0xFFFFFFFFFFFFFFFF is -1, not -4294967297 (the upstream int-shift bug).
    node = Parser(b"\xff" * 8).read_long()
    assert node.value == -1
    tr = TextRenderer()
    tr.render_node(node)
    assert tr.out[-1] == "(long)-1 - 0xff ff ff ff ff ff ff ff"


def test_double_low_byte_high_bit():
    # b5 has the high bit set (0xdc); upstream would corrupt this value.
    node = Parser(struct.pack(">d", 123.45)).read_double()
    tr = TextRenderer()
    tr.render_node(node)
    assert tr.out[-1].startswith("(double)123.45 - 0x40 5e dc cc")


def test_invalid_magic_is_reported():
    out = dump(b"\x00\x01\x00\x05")
    assert "Invalid STREAM_MAGIC" in out


def test_unknown_format_rejected():
    with pytest.raises(ValueError):
        dump(bytes.fromhex(ABCD_HEX), format="xml")


def test_version_is_set():
    assert __version__
