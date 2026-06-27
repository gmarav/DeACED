"""Java "modified UTF-8" -- the string encoding used by serialization.

``DataOutput.writeUTF`` / ``DataInput.readUTF`` (and therefore the Object
Serialization Stream Protocol) encode strings in a variant of UTF-8 that differs
from the standard in exactly two ways:

* ``U+0000`` is written as the two bytes ``C0 80`` (never a bare ``00``);
* characters outside the Basic Multilingual Plane are written as a UTF-16
  surrogate pair, each surrogate emitted in its 3-byte form (i.e. CESU-8), rather
  than as one 4-byte UTF-8 sequence.

For every other (BMP, non-zero) character it is identical to standard UTF-8.
Decoding is tolerant: malformed sequences yield U+FFFD rather than raising.
"""

from __future__ import annotations

_REPLACEMENT = 0xFFFD


def decode(data: bytes) -> str:
    """Decode modified-UTF-8 ``data`` into a string."""
    units = bytearray()  # UTF-16 code units, big-endian
    i = 0
    n = len(data)
    while i < n:
        a = data[i]
        if a < 0x80:
            unit = a
            i += 1
        elif (a & 0xE0) == 0xC0:
            if i + 1 < n and (data[i + 1] & 0xC0) == 0x80:
                unit = ((a & 0x1F) << 6) | (data[i + 1] & 0x3F)
                i += 2
            else:
                unit = _REPLACEMENT
                i += 1
        elif (a & 0xF0) == 0xE0:
            if i + 2 < n and (data[i + 1] & 0xC0) == 0x80 and (data[i + 2] & 0xC0) == 0x80:
                unit = ((a & 0x0F) << 12) | ((data[i + 1] & 0x3F) << 6) | (data[i + 2] & 0x3F)
                i += 3
            else:
                unit = _REPLACEMENT
                i += 1
        else:
            unit = _REPLACEMENT
            i += 1
        units += unit.to_bytes(2, "big")
    # Combine surrogate pairs; keep lone surrogates as-is (Java permits them).
    return units.decode("utf-16-be", errors="surrogatepass")


def encode(text: str) -> bytes:
    """Encode ``text`` as modified UTF-8."""
    b16 = text.encode("utf-16-be", errors="surrogatepass")
    out = bytearray()
    for j in range(0, len(b16), 2):
        unit = (b16[j] << 8) | b16[j + 1]
        if unit == 0x0000:
            out += b"\xc0\x80"
        elif unit <= 0x7F:
            out.append(unit)
        elif unit <= 0x7FF:
            out.append(0xC0 | (unit >> 6))
            out.append(0x80 | (unit & 0x3F))
        else:
            out.append(0xE0 | (unit >> 12))
            out.append(0x80 | ((unit >> 6) & 0x3F))
            out.append(0x80 | (unit & 0x3F))
    return bytes(out)
