"""Renderers turn a parsed stream (:class:`~deaced.model.Stream`) into output.

Each renderer is a visitor over the semantic AST:

* :mod:`deaced.render.text` -- the hierarchical text dump (default format,
  byte-for-byte compatible with the patched upstream jar);
* :mod:`deaced.render.json` -- a structured, machine-readable JSON view;
* :mod:`deaced.render.pretty` -- a compact, human-readable data tree.
"""

from __future__ import annotations

from .json import render_json
from .pretty import render_pretty
from .text import render_text

__all__ = ["render_text", "render_json", "render_pretty"]
