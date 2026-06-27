"""Make rendered output safe to encode as UTF-8.

Java strings and ``char`` values may contain lone UTF-16 surrogates
(``U+D800``..``U+DFFF``); DeACED keeps them faithfully in the semantic AST, but
they cannot be encoded as UTF-8, so any renderer output reaching them would crash
the caller on write. The reference jar prints ``?`` for such code points, so we
do the same -- replacing each lone surrogate with ``?`` keeps the output writable
and matches the jar byte-for-byte.
"""

from __future__ import annotations

_SURROGATES = {cp: "?" for cp in range(0xD800, 0xE000)}


def safe(text: str) -> str:
    """Return ``text`` with lone surrogates replaced by ``?`` (UTF-8 encodable)."""
    return text.translate(_SURROGATES)
