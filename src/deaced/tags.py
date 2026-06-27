"""Constants from the Java Object Serialization Stream Protocol.

`TC` holds the type-code marker bytes; `SC` holds the class-description flag
bits. Using named enums in place of bare ``0x73``/``0x02`` literals makes the
parser self-documenting and lets the type checker catch typos.

Reference: java.io.ObjectStreamConstants.
"""

from __future__ import annotations

from enum import IntEnum

#: Stream header magic (``0xAC 0xED``).
STREAM_MAGIC = 0xACED
#: Stream protocol version this port targets.
STREAM_VERSION = 5
#: First object handle assigned in a stream.
BASE_WIRE_HANDLE = 0x7E0000


class TC(IntEnum):
    """Type-code marker bytes (``TC_*`` in the spec)."""

    NULL = 0x70
    REFERENCE = 0x71
    CLASSDESC = 0x72
    OBJECT = 0x73
    STRING = 0x74
    ARRAY = 0x75
    CLASS = 0x76
    BLOCKDATA = 0x77
    ENDBLOCKDATA = 0x78
    RESET = 0x79
    BLOCKDATALONG = 0x7A
    EXCEPTION = 0x7B
    LONGSTRING = 0x7C
    PROXYCLASSDESC = 0x7D
    ENUM = 0x7E


class SC(IntEnum):
    """Class-description flag bits (``SC_*`` in the spec)."""

    WRITE_METHOD = 0x01
    SERIALIZABLE = 0x02
    EXTERNALIZABLE = 0x04
    BLOCK_DATA = 0x08
    ENUM = 0x10
