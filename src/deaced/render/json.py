"""JSON renderer: a structured, machine-readable view of the parsed stream.

The shape mirrors the semantic AST: each node becomes a tagged object (a
``type`` field plus its data), primitives become bare JSON scalars, and arrays
become JSON arrays. References are emitted as ``{"type": "reference", ...}`` and
are *not* expanded, so the result is always a finite tree.
"""

from __future__ import annotations

import json
import math
from typing import Any

from ..jfloat import double_to_string, float_to_string
from ..model import (
    ArrayObj,
    BlockData,
    ClassData,
    ClassDesc,
    ClassObj,
    EnumObj,
    ExceptionObj,
    FieldDesc,
    Node,
    Null,
    ObjectInstance,
    Primitive,
    ProxyClassDesc,
    Reference,
    Reset,
    Stream,
    StringVal,
)
from ._safe import safe


def _desc_name(node: Node | None) -> str | None:
    if isinstance(node, ClassDesc):
        return node.name.value
    if isinstance(node, ProxyClassDesc):
        return "<Dynamic Proxy Class>"
    return None


def _desc(node: Node | None) -> Any:
    match node:
        case ClassDesc():
            return {
                "name": node.name.value,
                "serialVersionUID": node.svuid.hex(),
                "flags": node.flags,
                "fields": [_field_desc(f) for f in node.fields],
                "annotations": [_value(a) for a in node.annotations],
                "super": _desc(node.super_desc),
            }
        case ProxyClassDesc():
            return {
                "proxy": True,
                "interfaces": [i.value for i in node.interfaces],
                "annotations": [_value(a) for a in node.annotations],
                "super": _desc(node.super_desc),
            }
        case Reference():
            return {"type": "reference", "handle": node.handle}
        case _:
            return None


def _field_desc(f: FieldDesc) -> dict[str, Any]:
    d: dict[str, Any] = {"name": f.name.value, "type": f.tc}
    if f.class_name1 is not None:
        d["className"] = _value(f.class_name1)
    return d


def _class_data(cd: ClassData) -> dict[str, Any]:
    d: dict[str, Any] = {
        "class": cd.class_name,
        "fields": {fv.name: _value(fv.value) for fv in cd.values},
    }
    if cd.has_annotation:
        d["annotations"] = [_value(a) for a in cd.annotations]
    return d


def _value(node: Node) -> Any:
    match node:
        case Null():
            return None
        case Primitive(tc="C", value=v):
            return chr(int(v))
        case Primitive(tc="D" | "F", value=v) if not math.isfinite(float(v)):
            # NaN/Infinity are not valid JSON numbers -> emit Java's string form.
            fn = double_to_string if node.tc == "D" else float_to_string
            return fn(float(v))
        case Primitive(value=v):
            return v
        case StringVal():
            out: dict[str, Any] = {"type": "string", "handle": node.handle, "value": node.value}
            if node.long:
                out["long"] = True
            return out
        case Reference():
            return {"type": "reference", "handle": node.handle}
        case BlockData():
            return {"type": "blockData", "hex": node.data.hex(), "long": node.long}
        case Reset():
            return {"type": "reset"}
        case ExceptionObj():
            return {"type": "exception", "throwable": _value(node.throwable)}
        case ClassObj():
            return {"type": "class", "handle": node.handle, "classDesc": _desc(node.class_desc)}
        case EnumObj():
            return {
                "type": "enum",
                "handle": node.handle,
                "class": _desc_name(node.class_desc),
                "constant": _value(node.constant),
            }
        case ArrayObj():
            arr: dict[str, Any] = {
                "type": "array",
                "handle": node.handle,
                "elementType": node.component,
            }
            if node.component == "B":
                arr["hex"] = node.byte_values.hex()
            else:
                arr["elements"] = [_value(e) for e in node.elements]
            return arr
        case ObjectInstance():
            return {
                "type": "object",
                "handle": node.handle,
                "class": _desc_name(node.class_desc) if node.na else node.data[-1].class_name,
                "classData": None if node.na else [_class_data(cd) for cd in node.data],
            }
        case _:
            raise TypeError(f"cannot render node {type(node).__name__}")


def render_json(stream: Stream, *, indent: int | None = 2) -> str:
    """Render the parsed ``stream`` as JSON."""
    obj: dict[str, Any] = {}
    if stream.rmi is not None:
        obj["rmi"] = stream.rmi
    obj["streamMagicValid"] = stream.magic_valid
    obj["streamVersionValid"] = stream.version_valid
    obj["contents"] = [_value(c) for c in stream.contents]
    return safe(json.dumps(obj, indent=indent, ensure_ascii=False) + "\n")
