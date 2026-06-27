"""Positioned, big-endian byte reader over an in-memory serialization stream.

The reader is the lowest layer: it knows nothing about the serialization
protocol, only how to pull big-endian primitives off the stream while tracking
the current byte offset. It raises :class:`TruncatedStreamError` (with that
offset) the moment a read would run past the end of the buffer.
"""

from __future__ import annotations

from .errors import TruncatedStreamError


class Reader:
    """Read big-endian primitives from ``data``, tracking the byte offset."""

    def __init__(self, data: bytes) -> None:
        self._d = data
        self._i = 0

    # --- position ---
    @property
    def pos(self) -> int:
        """Offset of the next byte to be read."""
        return self._i

    def remaining(self) -> int:
        """Number of unread bytes left in the stream."""
        return len(self._d) - self._i

    def peek(self) -> int | None:
        """Return the next byte without consuming it, or ``None`` at EOF."""
        return self._d[self._i] if self._i < len(self._d) else None

    def _need(self, n: int) -> None:
        if self._i + n > len(self._d):
            raise TruncatedStreamError(
                f"expected {n} more byte(s), only {self.remaining()} left", self._i
            )

    # --- raw bytes ---
    def read(self, n: int) -> bytes:
        """Consume and return the next ``n`` bytes."""
        self._need(n)
        chunk = self._d[self._i : self._i + n]
        self._i += n
        return chunk

    # --- unsigned big-endian integers ---
    def u8(self) -> int:
        self._need(1)
        b = self._d[self._i]
        self._i += 1
        return b

    def u16(self) -> int:
        return int.from_bytes(self.read(2), "big", signed=False)

    def u32(self) -> int:
        return int.from_bytes(self.read(4), "big", signed=False)

    def u64(self) -> int:
        return int.from_bytes(self.read(8), "big", signed=False)
