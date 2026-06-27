"""DeACED - dump and inspect Java Object Serialization (``0xAC 0xED``) streams.

A small, dependency-free library and CLI that turns a Java serialization stream
(and Java RMI packet contents) into a human-readable, hierarchical text dump.

This is a Python port of SerializationDumper by Nicky Bloor (MIT); see NOTICE.
"""

from __future__ import annotations

from .model import Stream
from .parser import Parser, parse, run_deep
from .render import render_json, render_pretty, render_text

__all__ = ["dump", "parse", "__version__"]
__version__ = "0.1.0"

_FORMATS = ("text", "json", "pretty")


def dump(data: bytes, *, format: str = "text", offsets: bool = False) -> str:
    """Parse ``data`` and render it.

    Args:
        data: The raw serialization stream.
        format: Output format -- ``"text"`` (the default hierarchical dump,
            byte-for-byte compatible with the patched upstream jar), ``"json"``
            (a structured machine-readable view), or ``"pretty"`` (a compact
            human-readable data tree).
        offsets: When true (``text`` only), prefix every line with
            ``@<byte-offset>|``.

    Returns:
        The rendered output as a single string.
    """
    if format not in _FORMATS:
        raise ValueError(f"unknown format: {format!r}")
    if offsets and format != "text":
        raise ValueError("offsets are only supported for the 'text' format")

    def render() -> str:
        node: Stream = Parser(data).parse()
        if format == "text":
            return render_text(node, offsets=offsets)
        if format == "json":
            return render_json(node)
        return render_pretty(node)

    return run_deep(render)
