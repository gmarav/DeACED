"""Text renderer: the hierarchical dump, byte-for-byte like the patched jar.

This renderer owns the dump *format*: it walks the semantic AST and emits the
exact lines, including the presentation-only groupings (``Contents``, ``values``,
``(object)``, ``(array)``, ``CLASS X`` ...) that are not nodes in the model.

For ``--offsets`` it keeps a single byte cursor that flows through the whole tree
in the same order the parser consumed bytes; every emitted line is tagged with
the cursor value at that point (matching the parser position after the bytes for
that line were read). The cursor advances via :meth:`_consume`, whose calls are
ordered to mirror the parser exactly.
"""

from __future__ import annotations

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
    FieldValue,
    Node,
    Null,
    ObjectInstance,
    Primitive,
    ProxyClassDesc,
    Reference,
    Reset,
    Stream,
    StringVal,
    Utf,
)
from ._safe import safe

_RMI = {
    0x50: "RMI Call - 0x50",
    0x51: "RMI ReturnData - 0x51",
    0x52: "RMI Ping - 0x52",
    0x53: "RMI PingAck - 0x53",
    0x54: "RMI DgcAck - 0x54",
}
_FIELD_TYPE = {
    "B": "Byte - B",
    "C": "Char - C",
    "D": "Double - D",
    "F": "Float - F",
    "I": "Int - I",
    # 'J' is the JVM type code for long (JVMS 4.3.2); NickstaDB upstream mislabels
    # it "Long - L". The patched reference jar and DeACED both emit the spec-correct
    # "Long - J" (see NOTICE / SerializationDumper CHANGES.patch). Golden-tested.
    "J": "Long - J",
    "S": "Short - S",
    "Z": "Boolean - Z",
    "[": "Array - [",
    "L": "Object - L",
}


def _b2h(b: int) -> str:
    return f"{b:02x}"


def _spaced(bs: bytes) -> str:
    return " ".join(f"{b:02x}" for b in bs)


def _spaced_int(value: int, nbytes: int) -> str:
    return _spaced(value.to_bytes(nbytes, "big"))


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")


def _flagstr(flags: int) -> str:
    parts = []
    if flags & 0x01:
        parts.append("SC_WRITE_METHOD")
    if flags & 0x02:
        parts.append("SC_SERIALIZABLE")
    if flags & 0x04:
        parts.append("SC_EXTERNALIZABLE")
    if flags & 0x08:
        parts.append("SC_BLOCK_DATA")
    return " | ".join(parts)


class TextRenderer:
    """Render a :class:`~deaced.model.Stream` to the hierarchical text dump."""

    def __init__(self, offsets: bool = False) -> None:
        self.offsets = offsets
        self.depth = 0
        self.cursor = 0
        self.out: list[str] = []

    # --- low-level ---
    def _emit(self, label: str) -> None:
        indent = "  " * self.depth
        self.out.append(f"@{self.cursor}|{indent}{label}" if self.offsets else f"{indent}{label}")

    def _consume(self, n: int) -> None:
        self.cursor += n

    def _i2h(self, handle: int) -> str:
        return _spaced_int(handle, 4)

    # --- entry ---
    def render(self, s: Stream) -> str:
        self.cursor = 0
        if s.rmi is not None:
            self._consume(1)
            self._emit(_RMI.get(s.rmi, "Unknown RMI packet type - 0x" + _b2h(s.rmi)))
        self._consume(2)
        self._emit(f"STREAM_MAGIC - 0x{_b2h(s.magic[0])} {_b2h(s.magic[1])}")
        if not s.magic_valid:
            self._emit("Invalid STREAM_MAGIC, should be 0xac ed")
            return self._finish()
        assert s.version is not None
        self._consume(2)
        self._emit(f"STREAM_VERSION - 0x{_b2h(s.version[0])} {_b2h(s.version[1])}")
        if not s.version_valid:
            self._emit("Invalid STREAM_VERSION, should be 0x00 05")
        self._emit("Contents")
        self.depth += 1
        for c in s.contents:
            self.render_node(c)
        self.depth -= 1
        return self._finish()

    def _finish(self) -> str:
        return "\n".join([""] + self.out) + "\n"

    # --- dispatch ---
    def render_node(self, node: Node) -> None:
        match node:
            case Null():
                self._consume(1)
                self._emit("TC_NULL - 0x70")
            case Reference():
                self._render_reference(node)
            case StringVal():
                self._render_string(node)
            case Primitive():
                self._render_primitive(node)
            case BlockData():
                self._render_blockdata(node)
            case Reset():
                self._consume(1)
                self._emit("TC_RESET - 0x79")
            case ExceptionObj():
                self._render_exception(node)
            case ClassObj():
                self._render_class_obj(node)
            case EnumObj():
                self._render_enum(node)
            case ArrayObj():
                self._render_array(node)
            case ObjectInstance():
                self._render_object(node)
            case ClassDesc():
                self._render_class_desc(node)
            case ProxyClassDesc():
                self._render_proxy_class_desc(node)
            case _:  # pragma: no cover - defensive
                raise TypeError(f"cannot render node {type(node).__name__}")

    # --- leaves ---
    def _render_reference(self, node: Reference) -> None:
        self._consume(1)
        self._emit("TC_REFERENCE - 0x71")
        self.depth += 1
        self._consume(4)
        self._emit(f"Handle - {node.handle} - 0x{self._i2h(node.handle)}")
        self.depth -= 1

    def _emit_utf(self, value: str, raw: bytes, long: bool) -> None:
        if long:
            self._consume(8)
            self._emit(f"Length - {len(raw)} - 0x{_spaced_int(len(raw), 8)}")
        else:
            self._consume(2)
            self._emit(f"Length - {len(raw)} - 0x{_spaced_int(len(raw), 2)}")
        self._consume(len(raw))
        self._emit(f"Value - {_esc(value)} - 0x{raw.hex()}")

    def _render_utf(self, utf: Utf) -> None:
        self._emit_utf(utf.value, utf.raw, long=False)

    def _render_string(self, node: StringVal) -> None:
        self._consume(1)
        self._emit("TC_LONGSTRING - 0x7c" if node.long else "TC_STRING - 0x74")
        self.depth += 1
        self._emit("newHandle 0x" + self._i2h(node.handle))
        self._emit_utf(node.value, node.raw, long=node.long)
        self.depth -= 1

    def _render_primitive(self, node: Primitive) -> None:
        raw = node.raw
        self._consume(len(raw))
        v = node.value
        match node.tc:
            case "B":
                b = raw[0]
                ascii_note = f" (ASCII: {chr(b)})" if 0x20 <= b <= 0x7E else ""
                self._emit(f"(byte){v}{ascii_note} - 0x{_b2h(b)}")
            case "C":
                self._emit(f"(char){chr(int(v))} - 0x{_b2h(raw[0])} {_b2h(raw[1])}")
            case "D":
                self._emit(f"(double){double_to_string(float(v))} - 0x{_spaced(raw)}")
            case "F":
                self._emit(f"(float){float_to_string(float(v))} - 0x{_spaced(raw)}")
            case "I":
                self._emit(f"(int){v} - 0x{_spaced(raw)}")
            case "J":
                self._emit(f"(long){v} - 0x{_spaced(raw)}")
            case "S":
                self._emit(f"(short){v} - 0x{_b2h(raw[0])} {_b2h(raw[1])}")
            case "Z":
                self._emit(f"(boolean){'true' if v else 'false'} - 0x{_b2h(raw[0])}")

    def _render_blockdata(self, node: BlockData) -> None:
        self._consume(1)
        self._emit("TC_BLOCKDATALONG - 0x7a" if node.long else "TC_BLOCKDATA - 0x77")
        self.depth += 1
        ln = len(node.data)
        if node.long:
            self._consume(4)
            self._emit(f"Length - {ln} - 0x{_spaced_int(ln, 4)}")
        else:
            self._consume(1)
            self._emit(f"Length - {ln} - 0x{_b2h(ln & 0xFF)}")
        self._consume(ln)
        self._emit("Contents - 0x" + node.data.hex())
        self.depth -= 1

    def _render_exception(self, node: ExceptionObj) -> None:
        self._consume(1)
        self._emit("TC_EXCEPTION - 0x7b")
        self.depth += 1
        self.render_node(node.throwable)
        self.depth -= 1

    # --- objects / classes ---
    def _render_class_obj(self, node: ClassObj) -> None:
        self._consume(1)
        self._emit("TC_CLASS - 0x76")
        self.depth += 1
        self.render_node(node.class_desc)
        self.depth -= 1
        self._emit("newHandle 0x" + self._i2h(node.handle))

    def _render_enum(self, node: EnumObj) -> None:
        self._consume(1)
        self._emit("TC_ENUM - 0x7e")
        self.depth += 1
        self.render_node(node.class_desc)
        self._emit("newHandle 0x" + self._i2h(node.handle))
        self.render_node(node.constant)
        self.depth -= 1

    def _render_array(self, node: ArrayObj) -> None:
        self._consume(1)
        self._emit("TC_ARRAY - 0x75")
        self.depth += 1
        self.render_node(node.class_desc)
        self._emit("newHandle 0x" + self._i2h(node.handle))
        self._consume(4)
        self._emit(f"Array size - {node.size} - 0x{_spaced_int(node.size, 4)}")
        if node.component == "B":
            self._consume(node.size)
            self._emit("Value " + node.byte_values.hex())
        else:
            self._emit("Values")
            self.depth += 1
            for i, el in enumerate(node.elements):
                self._emit(f"Index {i}:")
                self.depth += 1
                self._render_value(node.component, el)
                self.depth -= 1
            self.depth -= 1
        self.depth -= 1

    def _render_object(self, node: ObjectInstance) -> None:
        self._consume(1)
        self._emit("TC_OBJECT - 0x73")
        self.depth += 1
        self.render_node(node.class_desc)
        self._emit("newHandle 0x" + self._i2h(node.handle))
        self._render_class_data(node)
        self.depth -= 1

    def _render_class_data(self, node: ObjectInstance) -> None:
        self._emit("classdata")
        self.depth += 1
        if node.na:
            self._emit("N/A")
        else:
            for cd in node.data:
                self._render_one_class_data(cd)
        self.depth -= 1

    def _render_one_class_data(self, cd: ClassData) -> None:
        self._emit("CLASS " + cd.class_name)
        self.depth += 1
        if cd.serializable:
            self._emit("values")
            self.depth += 1
            for fv in cd.values:
                self._render_field(fv)
            self.depth -= 1
        if cd.has_annotation:
            self._emit("objectAnnotation")
            self.depth += 1
            for ann in cd.annotations:
                self.render_node(ann)
            self._consume(1)
            self._emit("TC_ENDBLOCKDATA - 0x78")
            self.depth -= 1
        self.depth -= 1

    def _render_field(self, fv: FieldValue) -> None:
        self._emit("FIELD " + fv.name)
        self.depth += 1
        self._render_value(fv.declared_tc, fv.value)
        self.depth -= 1

    def _render_value(self, tc: str, node: Node) -> None:
        match tc:
            case "L" | "[":
                self._emit("(object)" if tc == "L" else "(array)")
                self.depth += 1
                self.render_node(node)
                self.depth -= 1
            case _:
                self.render_node(node)

    # --- class descriptions ---
    def _render_class_desc(self, node: ClassDesc) -> None:
        self._consume(1)
        self._emit("TC_CLASSDESC - 0x72")
        self.depth += 1
        self._emit("className")
        self.depth += 1
        self._render_utf(node.name)
        self.depth -= 1
        self._consume(8)
        self._emit("serialVersionUID - 0x" + _spaced(node.svuid))
        self._emit("newHandle 0x" + self._i2h(node.handle))
        self._consume(1)
        self._emit(f"classDescFlags - 0x{_b2h(node.flags)} - {_flagstr(node.flags)}")
        self._render_fields(node.fields)
        self._render_annotations(node.annotations)
        self._emit("superClassDesc")
        self.depth += 1
        assert node.super_desc is not None
        self.render_node(node.super_desc)
        self.depth -= 1
        self.depth -= 1

    def _render_fields(self, fields: list[FieldDesc]) -> None:
        n = len(fields)
        self._consume(2)
        self._emit(f"fieldCount - {n} - 0x{_spaced_int(n, 2)}")
        if n > 0:
            self._emit("Fields")
            self.depth += 1
            for i, fd in enumerate(fields):
                self._emit(f"{i}:")
                self.depth += 1
                self._render_field_desc(fd)
                self.depth -= 1
            self.depth -= 1

    def _render_field_desc(self, fd: FieldDesc) -> None:
        self._consume(1)
        self._emit(f"{_FIELD_TYPE[fd.tc]} - 0x{_b2h(ord(fd.tc))}")
        self._emit("fieldName")
        self.depth += 1
        self._render_utf(fd.name)
        self.depth -= 1
        if fd.tc in ("[", "L"):
            self._emit("className1")
            self.depth += 1
            assert fd.class_name1 is not None
            self.render_node(fd.class_name1)
            self.depth -= 1

    def _render_annotations(self, annotations: list[Node]) -> None:
        self._emit("classAnnotations")
        self.depth += 1
        for ann in annotations:
            self.render_node(ann)
        self._consume(1)
        self._emit("TC_ENDBLOCKDATA - 0x78")
        self.depth -= 1

    def _render_proxy_class_desc(self, node: ProxyClassDesc) -> None:
        self._consume(1)
        self._emit("TC_PROXYCLASSDESC - 0x7d")
        self.depth += 1
        self._emit("newHandle 0x" + self._i2h(node.handle))
        count = len(node.interfaces)
        self._consume(4)
        self._emit(f"Interface count - {count} - 0x{_spaced_int(count, 4)}")
        self._emit("proxyInterfaceNames")
        self.depth += 1
        for i, utf in enumerate(node.interfaces):
            self._emit(f"{i}:")
            self.depth += 1
            self._render_utf(utf)
            self.depth -= 1
        self.depth -= 1
        self._render_annotations(node.annotations)
        self._emit("superClassDesc")
        self.depth += 1
        assert node.super_desc is not None
        self.render_node(node.super_desc)
        self.depth -= 1
        self.depth -= 1


def render_text(root: Stream, *, offsets: bool = False) -> str:
    """Render the parsed ``root`` stream as the text dump."""
    return safe(TextRenderer(offsets=offsets).render(root))
