"""Pretty renderer: a compact, human-readable view of the data.

Unlike the text dump, this drops the byte-level detail (hex columns, lengths,
class descriptors) and shows just the logical structure: objects with their
fields, arrays with their elements, references by handle. Wire handles are shown
as small relative ids (``#0``, ``#1`` ...) so back-references are easy to follow.
"""

from __future__ import annotations

from ..jfloat import double_to_string, float_to_string
from ..model import (
    ArrayObj,
    BlockData,
    ClassObj,
    EnumObj,
    ExceptionObj,
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
from ..tags import BASE_WIRE_HANDLE
from ._safe import safe

_MAX_STR = 60


def _hid(handle: int) -> int:
    return handle - BASE_WIRE_HANDLE


def _short(s: str) -> str:
    s = s.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
    return s if len(s) <= _MAX_STR else s[:_MAX_STR] + "..."


def _class_name(node: Node | None) -> str:
    if isinstance(node, ProxyClassDesc):
        return "<Dynamic Proxy Class>"
    name = getattr(node, "name", None)
    return name.value if name is not None else "?"


def _inline(node: Node) -> str | None:
    """Return a one-line rendering, or None if the node needs its own block."""
    match node:
        case Null():
            return "null"
        case Primitive(tc="C", value=v):
            return "'" + chr(int(v)) + "'"
        case Primitive(tc="Z", value=v):
            return "true" if v else "false"
        case Primitive(tc="D", value=v):
            return double_to_string(float(v))
        case Primitive(tc="F", value=v):
            return float_to_string(float(v))
        case Primitive(value=v):
            return str(v)
        case StringVal(value=v):
            return '"' + _short(v) + '"'
        case Reference(handle=h):
            return f"ref #{_hid(h)}"
        case EnumObj(constant=const):
            label = const.value if isinstance(const, StringVal) else "?"
            return f"{_class_name(node.class_desc)}.{label}"
        case BlockData(data=d):
            return f"blockData({len(d)} bytes)"
        case Reset():
            return "(reset)"
        case ArrayObj(component="B", size=sz, byte_values=bv):
            return f"byte[{sz}] 0x{_short(bv.hex())}"
        case _:
            return None


class PrettyRenderer:
    """Render a :class:`~deaced.model.Stream` as a compact data tree."""

    def __init__(self) -> None:
        self.out: list[str] = []

    def render(self, stream: Stream) -> str:
        for c in stream.contents:
            self._emit(c, 0, "")
        return "\n".join(self.out) + "\n"

    def _emit(self, node: Node, depth: int, prefix: str) -> None:
        ind = "  " * depth
        inline = _inline(node)
        if inline is not None:
            self.out.append(f"{ind}{prefix}{inline}")
            return
        match node:
            case ObjectInstance():
                if node.data and not node.na:
                    cls = node.data[-1].class_name
                else:
                    cls = _class_name(node.class_desc)
                self.out.append(f"{ind}{prefix}{cls} #{_hid(node.handle)}")
                for cd in node.data:
                    for fv in cd.values:
                        self._field(fv.name, fv.value, depth + 1)
                    if cd.has_annotation and cd.annotations:
                        self.out.append(f"{'  ' * (depth + 1)}annotations:")
                        for a in cd.annotations:
                            self._emit(a, depth + 2, "")
            case ArrayObj():
                self.out.append(f"{ind}{prefix}{node.component}[] #{_hid(node.handle)}")
                for i, e in enumerate(node.elements):
                    self._field(f"[{i}]", e, depth + 1)
            case ExceptionObj():
                self.out.append(f"{ind}{prefix}exception")
                self._emit(node.throwable, depth + 1, "")
            case ClassObj():
                self.out.append(
                    f"{ind}{prefix}class {_class_name(node.class_desc)} #{_hid(node.handle)}"
                )
            case _:  # pragma: no cover - defensive
                self.out.append(f"{ind}{prefix}{type(node).__name__}")

    def _field(self, name: str, value: Node, depth: int) -> None:
        inline = _inline(value)
        if inline is not None:
            self.out.append(f"{'  ' * depth}{name} = {inline}")
        else:
            self._emit(value, depth, f"{name}: ")


def render_pretty(stream: Stream) -> str:
    """Render the parsed ``stream`` as a compact, human-readable tree."""
    return safe(PrettyRenderer().render(stream))
