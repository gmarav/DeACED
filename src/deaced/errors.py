"""Exception types for DeACED.

Every error carries the byte offset in the serialization stream where it was
detected, which makes truncated or malformed streams much easier to diagnose.
"""

from __future__ import annotations


class SerDumpError(Exception):
    """Base class for all DeACED parse errors."""

    def __init__(self, message: str, offset: int | None = None) -> None:
        self.offset = offset
        super().__init__(f"{message} (at offset {offset})" if offset is not None else message)


class TruncatedStreamError(SerDumpError):
    """The stream ended before the expected number of bytes was available."""


class UnknownTagError(SerDumpError):
    """An unexpected or illegal type-code byte was encountered."""


class IllegalStateError(SerDumpError):
    """The stream violated a structural rule of the serialization protocol."""
