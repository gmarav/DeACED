"""Hand-verified tests for protocol elements the reference jar does not support.

TC_RESET (0x79) and TC_EXCEPTION (0x7b) are legal serialization elements but the
upstream SerializationDumper aborts on them, so they cannot be golden-tested
against the jar. The expected dumps below are verified by hand against the spec.
"""

from deaced import dump, parse
from deaced.model import ExceptionObj, Reset, StringVal


def _expected(lines: list[str]) -> str:
    return "\n" + "\n".join(lines) + "\n"


# TC_STRING "A", TC_RESET, TC_STRING "B": the reset restarts handle numbering,
# so *both* strings get newHandle 0x00 7e 00 00.
RESET_HEX = "aced0005740001417974000142"
RESET_LINES = [
    "STREAM_MAGIC - 0xac ed",
    "STREAM_VERSION - 0x00 05",
    "Contents",
    "  TC_STRING - 0x74",
    "    newHandle 0x00 7e 00 00",
    "    Length - 1 - 0x00 01",
    "    Value - A - 0x41",
    "  TC_RESET - 0x79",
    "  TC_STRING - 0x74",
    "    newHandle 0x00 7e 00 00",
    "    Length - 1 - 0x00 01",
    "    Value - B - 0x42",
]

# TC_EXCEPTION followed by the (here, minimal) Throwable object.
EXCEPTION_HEX = "aced00057b74000158"
EXCEPTION_LINES = [
    "STREAM_MAGIC - 0xac ed",
    "STREAM_VERSION - 0x00 05",
    "Contents",
    "  TC_EXCEPTION - 0x7b",
    "    TC_STRING - 0x74",
    "      newHandle 0x00 7e 00 00",
    "      Length - 1 - 0x00 01",
    "      Value - X - 0x58",
]


def test_reset_dump():
    assert dump(bytes.fromhex(RESET_HEX)) == _expected(RESET_LINES)


def test_reset_restarts_handles():
    contents = parse(bytes.fromhex(RESET_HEX)).contents
    assert [type(c).__name__ for c in contents] == ["StringVal", "Reset", "StringVal"]
    assert isinstance(contents[1], Reset)
    first, second = contents[0], contents[2]
    assert isinstance(first, StringVal) and isinstance(second, StringVal)
    assert first.handle == second.handle  # reset reused the base handle


def test_exception_dump():
    assert dump(bytes.fromhex(EXCEPTION_HEX)) == _expected(EXCEPTION_LINES)


def test_exception_holds_throwable():
    contents = parse(bytes.fromhex(EXCEPTION_HEX)).contents
    assert len(contents) == 1
    exc = contents[0]
    assert isinstance(exc, ExceptionObj)
    assert isinstance(exc.throwable, StringVal)
    assert exc.throwable.value == "X"


def test_reset_offsets_align():
    # the second string's bytes start after: 4 (header) + 4 ("A" string) + 1 (reset)
    out = dump(bytes.fromhex(RESET_HEX), offsets=True).splitlines()
    reset_line = next(line for line in out if "TC_RESET" in line)
    assert reset_line.startswith("@9|")  # 0xac 0xed 0x00 0x05 | 74 00 01 41 | 79 -> pos 9


def test_rmi_prefix():
    # a non-0xAC leading byte is read as an RMI packet type, then the stream
    out = dump(bytes.fromhex("51aced000570"))  # RMI ReturnData + magic + TC_NULL
    lines = out.splitlines()
    assert lines[1] == "RMI ReturnData - 0x51"
    assert "  TC_NULL - 0x70" in lines


def test_unknown_rmi_prefix():
    out = dump(bytes.fromhex("55aced000570"))
    assert "Unknown RMI packet type - 0x55" in out


def test_invalid_version_reported():
    out = dump(bytes.fromhex("aced000670"))  # magic ok, version 0x0006, then TC_NULL
    assert "Invalid STREAM_VERSION, should be 0x00 05" in out
    assert "TC_NULL - 0x70" in out  # parsing continues past a bad version


def test_blockdatalong():
    # TC_BLOCKDATALONG with a 4-byte length of 3, contents "ABC"
    out = dump(bytes.fromhex("aced00057a00000003414243"))
    assert "  TC_BLOCKDATALONG - 0x7a" in out
    assert "    Length - 3 - 0x00 00 00 03" in out
    assert "    Contents - 0x414243" in out


# --- field-value type codes the patched fork accepts but NickstaDB upstream does
# not (the headline fixes). These streams are hand-crafted -- Java never emits a
# short TC_LONGSTRING nor block data as a field value -- but each dump below is
# byte-for-byte identical to the patched reference jar (verified during dev). ---

# An 'L' (object) field whose value is TC_LONGSTRING (0x7c).
LONGSTRING_OBJFIELD_HEX = (
    "aced0005"
    "73"
    "72"
    "000141"
    "0000000000000000"
    "02"
    "0001"
    "4c"
    "000173"
    "7400124c6a6176612f6c616e672f537472696e673b"
    "78"
    "70"
    "7c"
    "0000000000000003"
    "414243"
)
LONGSTRING_OBJFIELD_DUMP = """
STREAM_MAGIC - 0xac ed
STREAM_VERSION - 0x00 05
Contents
  TC_OBJECT - 0x73
    TC_CLASSDESC - 0x72
      className
        Length - 1 - 0x00 01
        Value - A - 0x41
      serialVersionUID - 0x00 00 00 00 00 00 00 00
      newHandle 0x00 7e 00 00
      classDescFlags - 0x02 - SC_SERIALIZABLE
      fieldCount - 1 - 0x00 01
      Fields
        0:
          Object - L - 0x4c
          fieldName
            Length - 1 - 0x00 01
            Value - s - 0x73
          className1
            TC_STRING - 0x74
              newHandle 0x00 7e 00 01
              Length - 18 - 0x00 12
              Value - Ljava/lang/String; - 0x4c6a6176612f6c616e672f537472696e673b
      classAnnotations
        TC_ENDBLOCKDATA - 0x78
      superClassDesc
        TC_NULL - 0x70
    newHandle 0x00 7e 00 02
    classdata
      CLASS A
        values
          FIELD s
            (object)
              TC_LONGSTRING - 0x7c
                newHandle 0x00 7e 00 03
                Length - 3 - 0x00 00 00 00 00 00 00 03
                Value - ABC - 0x414243
"""

# A '[' (array) field whose value is TC_BLOCKDATA (0x77).
BLOCKDATA_ARRAYFIELD_HEX = (
    "aced0005737200014100000000000000000200015b0001617400025b4278707703414243"
)
BLOCKDATA_ARRAYFIELD_DUMP = """
STREAM_MAGIC - 0xac ed
STREAM_VERSION - 0x00 05
Contents
  TC_OBJECT - 0x73
    TC_CLASSDESC - 0x72
      className
        Length - 1 - 0x00 01
        Value - A - 0x41
      serialVersionUID - 0x00 00 00 00 00 00 00 00
      newHandle 0x00 7e 00 00
      classDescFlags - 0x02 - SC_SERIALIZABLE
      fieldCount - 1 - 0x00 01
      Fields
        0:
          Array - [ - 0x5b
          fieldName
            Length - 1 - 0x00 01
            Value - a - 0x61
          className1
            TC_STRING - 0x74
              newHandle 0x00 7e 00 01
              Length - 2 - 0x00 02
              Value - [B - 0x5b42
      classAnnotations
        TC_ENDBLOCKDATA - 0x78
      superClassDesc
        TC_NULL - 0x70
    newHandle 0x00 7e 00 02
    classdata
      CLASS A
        values
          FIELD a
            (array)
              TC_BLOCKDATA - 0x77
                Length - 3 - 0x03
                Contents - 0x414243
"""

# The same, but TC_BLOCKDATALONG (0x7a) as the array field value.
BLOCKDATALONG_ARRAYFIELD_HEX = (
    "aced0005737200014100000000000000000200015b0001617400025b4278707a00000003414243"
)


def test_longstring_as_object_field():
    assert dump(bytes.fromhex(LONGSTRING_OBJFIELD_HEX)) == LONGSTRING_OBJFIELD_DUMP


def test_blockdata_as_array_field():
    assert dump(bytes.fromhex(BLOCKDATA_ARRAYFIELD_HEX)) == BLOCKDATA_ARRAYFIELD_DUMP


def test_blockdatalong_as_array_field():
    out = dump(bytes.fromhex(BLOCKDATALONG_ARRAYFIELD_HEX))
    assert "            (array)" in out
    assert "              TC_BLOCKDATALONG - 0x7a" in out
    assert "                Length - 3 - 0x00 00 00 03" in out
    assert "                Contents - 0x414243" in out
