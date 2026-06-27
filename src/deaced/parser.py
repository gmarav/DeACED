#!/usr/bin/env python3
"""Parser for Java Object Serialization streams (the ``0xAC 0xED`` format).

The parser walks a stream and builds a semantic AST (:mod:`deaced.model`): nodes
mirror protocol entities, carry their source ``offset`` and the raw bytes of
their primitives, and references are resolved against a handle table. The text /
JSON / pretty renderers in :mod:`deaced.render` turn that AST into output.

An internal :class:`ClassDataDesc` chain (the field layout of a class and its
superclasses) is kept alongside the node tree purely to decode object class data;
it never reaches the output.

This is a Python port of SerializationDumper by Nicky Bloor (MIT); see NOTICE.
Notable fixes over upstream: correct (long)/(double) decoding (no int-shift bug),
TC_LONGSTRING in object fields, TC_BLOCKDATA(LONG) in array fields, and proper
Java modified-UTF-8 string decoding (see :mod:`deaced.mutf8`).
"""

from __future__ import annotations

import struct
import sys
import threading
from collections.abc import Callable
from typing import TypeVar

from . import mutf8
from .errors import IllegalStateError, UnknownTagError
from .model import (
    ArrayObj,
    BlockData,
    ClassData,
    ClassDesc,
    ClassDescLike,
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
from .reader import Reader
from .tags import BASE_WIRE_HANDLE, SC, STREAM_MAGIC, STREAM_VERSION, TC

T = TypeVar("T")


# --- internal field-layout model (not part of the output AST) ---


class ClassField:
    """A field declaration used for class-data layout."""

    def __init__(self, tc: int) -> None:
        self.type_code = tc
        self.name = ""
        self.cn1 = ""


class ClassDetails:
    """One class in a (possibly inherited) layout chain."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.handle = -1
        self.flags = 0
        self.fields: list[ClassField] = []

    def is_serializable(self) -> bool:
        return (self.flags & SC.SERIALIZABLE) == SC.SERIALIZABLE

    def is_externalizable(self) -> bool:
        return (self.flags & SC.EXTERNALIZABLE) == SC.EXTERNALIZABLE

    def has_write_method(self) -> bool:
        return (self.flags & SC.WRITE_METHOD) == SC.WRITE_METHOD

    def has_block_data(self) -> bool:
        return (self.flags & SC.BLOCK_DATA) == SC.BLOCK_DATA


class ClassDataDesc:
    """An ordered chain of class layouts (a class and its superclasses)."""

    def __init__(self, lst: list[ClassDetails] | None = None) -> None:
        self.cd: list[ClassDetails] = lst if lst is not None else []

    def from_index(self, i: int) -> ClassDataDesc:
        return ClassDataDesc(self.cd[i:])

    def add_super(self, scdd: ClassDataDesc | None) -> None:
        if scdd is not None:
            self.cd.extend(scdd.cd)

    def add_class(self, name: str) -> None:
        self.cd.append(ClassDetails(name))

    def set_handle(self, h: int) -> None:
        self.cd[-1].handle = h

    def set_flags(self, f: int) -> None:
        self.cd[-1].flags = f

    def add_field(self, tc: int) -> None:
        self.cd[-1].fields.append(ClassField(tc))

    def set_fname(self, n: str) -> None:
        self.cd[-1].fields[-1].name = n

    def set_fcn1(self, c: str) -> None:
        self.cd[-1].fields[-1].cn1 = c

    def count(self) -> int:
        return len(self.cd)

    def details(self, i: int) -> ClassDetails:
        return self.cd[i]


class Parser:
    """Walk a serialization stream and build a semantic AST."""

    def __init__(self, data: bytes) -> None:
        self.r = Reader(data)
        self.handle = BASE_WIRE_HANDLE
        self.cdds: list[ClassDataDesc] = []
        self.handles: dict[int, Node] = {}
        self._field_readers: dict[str, Callable[[], Node]] = {
            "B": self.read_byte,
            "C": self.read_char,
            "D": self.read_double,
            "F": self.read_float,
            "I": self.read_int,
            "J": self.read_long,
            "S": self.read_short,
            "Z": self.read_bool,
            "[": self.read_array_field,
            "L": self.read_object_field,
        }

    # --- handles ---
    def new_handle(self) -> int:
        h = self.handle
        self.handle += 1
        return h

    @staticmethod
    def _signed(u: int, bits: int) -> int:
        return u - (1 << bits) if u >= (1 << (bits - 1)) else u

    @staticmethod
    def _tag(t: int | None) -> str:
        """Format a peeked tag byte for error messages (``EOF`` at end of stream)."""
        return "EOF" if t is None else f"0x{t:02x}"

    def _checked_size(self, value: int, what: str) -> int:
        """Reject a negative (malformed) length/count; real streams never write one."""
        if value < 0:
            raise IllegalStateError(f"negative {what} ({value}) -- malformed stream", self.r.pos)
        return value

    # --- entry point ---
    def parse(self) -> Stream:
        # An RMI packet prefixes the stream with a one-byte type; a bare
        # serialization stream instead starts with the magic's high byte.
        if self.r.peek() != (STREAM_MAGIC >> 8):
            rmi = self.r.u8()
        else:
            rmi = None
        magic = self.r.read(2)
        if int.from_bytes(magic, "big") != STREAM_MAGIC:
            return Stream(0, magic=magic, magic_valid=False, rmi=rmi)
        version = self.r.read(2)
        version_valid = int.from_bytes(version, "big") == STREAM_VERSION
        contents: list[Node] = []
        while self.r.remaining() > 0:
            contents.append(self.read_content())
        return Stream(
            0,
            magic=magic,
            magic_valid=True,
            version=version,
            version_valid=version_valid,
            rmi=rmi,
            contents=contents,
            handles=self.handles,
        )

    def read_content(self) -> Node:
        t = self.r.peek()
        match t:
            case TC.OBJECT:
                return self.read_new_object()
            case TC.CLASS:
                return self.read_new_class()
            case TC.ARRAY:
                return self.read_new_array()
            case TC.STRING | TC.LONGSTRING:
                return self.read_new_string()
            case TC.ENUM:
                return self.read_new_enum()
            case TC.CLASSDESC | TC.PROXYCLASSDESC:
                return self.read_new_class_desc()[0]
            case TC.REFERENCE:
                return self.read_prev_object()
            case TC.NULL:
                return self.read_null()
            case TC.BLOCKDATA:
                return self.read_block_data()
            case TC.BLOCKDATALONG:
                return self.read_long_block_data()
            case TC.RESET:
                return self.read_reset()
            case TC.EXCEPTION:
                return self.read_exception()
            case _:
                raise UnknownTagError(f"Illegal content element type {self._tag(t)}", self.r.pos)

    # --- objects ---
    def read_new_object(self) -> ObjectInstance:
        start = self.r.pos
        tag = self.r.u8()
        if tag != TC.OBJECT:
            raise IllegalStateError("Illegal value for TC_OBJECT (should be 0x73)", self.r.pos)
        class_desc, cdd = self.read_class_desc()
        handle = self.new_handle()
        node = ObjectInstance(start, handle=handle, class_desc=class_desc, na=cdd is None)
        self.handles[handle] = node
        node.data = self.read_class_data(cdd)
        return node

    def read_class_data(self, cdd: ClassDataDesc | None) -> list[ClassData]:
        result: list[ClassData] = []
        if cdd is None:
            return result
        for ci in range(cdd.count() - 1, -1, -1):
            cd = cdd.details(ci)
            values: list[FieldValue] = []
            annotations: list[Node] = []
            if cd.is_serializable():
                for cf in cd.fields:
                    values.append(self.read_class_data_field(cf))
            has_block = cd.is_serializable() and cd.has_write_method()
            if cd.is_externalizable():
                if cd.has_block_data():
                    has_block = True
                else:
                    raise IllegalStateError("Unable to parse externalContents element.", self.r.pos)
            if has_block:
                while self.r.peek() != TC.ENDBLOCKDATA:
                    annotations.append(self.read_content())
                self.r.u8()  # consume TC_ENDBLOCKDATA
            result.append(
                ClassData(
                    class_name=cd.name,
                    serializable=cd.is_serializable(),
                    values=values,
                    has_annotation=has_block,
                    annotations=annotations,
                )
            )
        return result

    def read_class_data_field(self, cf: ClassField) -> FieldValue:
        value = self.read_field_value(cf.type_code)
        return FieldValue(name=cf.name, declared_tc=chr(cf.type_code), value=value)

    def read_field_value(self, tc: int) -> Node:
        fn = self._field_readers.get(chr(tc))
        if fn is None:
            raise IllegalStateError(
                f"Illegal field type code ('{chr(tc)}', 0x{tc:02x})", self.r.pos
            )
        return fn()

    def read_object_field(self) -> Node:
        t = self.r.peek()
        match t:
            case TC.OBJECT:
                return self.read_new_object()
            case TC.REFERENCE:
                return self.read_prev_object()
            case TC.NULL:
                return self.read_null()
            case TC.STRING:
                return self.read_tc_string()
            case TC.LONGSTRING:
                return self.read_tc_longstring()
            case TC.CLASS:
                return self.read_new_class()
            case TC.ARRAY:
                return self.read_new_array()
            case TC.ENUM:
                return self.read_new_enum()
            case _:
                raise UnknownTagError(
                    f"Unexpected identifier for object field value {self._tag(t)}", self.r.pos
                )

    def read_array_field(self) -> Node:
        t = self.r.peek()
        match t:
            case TC.NULL:
                return self.read_null()
            case TC.ARRAY:
                return self.read_new_array()
            case TC.REFERENCE:
                return self.read_prev_object()
            case TC.BLOCKDATA:
                return self.read_block_data()
            case TC.BLOCKDATALONG:
                return self.read_long_block_data()
            case _:
                raise UnknownTagError(
                    f"Unexpected array field value type {self._tag(t)}", self.r.pos
                )

    # --- arrays / classes / enums ---
    def read_new_array(self) -> ArrayObj:
        start = self.r.pos
        tag = self.r.u8()
        if tag != TC.ARRAY:
            raise IllegalStateError("Illegal value for TC_ARRAY (should be 0x75)", self.r.pos)
        class_desc, cdd = self.read_class_desc()
        if cdd is None or cdd.count() != 1:
            raise IllegalStateError(
                "Array class description made up of more than one class.", self.r.pos
            )
        name = cdd.details(0).name
        if name[0] != "[":
            raise IllegalStateError("Array class name does not begin with '['.", self.r.pos)
        handle = self.new_handle()
        component = name[1]
        node = ArrayObj(start, handle=handle, class_desc=class_desc, component=component, size=0)
        self.handles[handle] = node
        size = self._checked_size(self._signed(self.r.u32(), 32), "array size")
        node.size = size
        if component == "B":
            node.byte_values = self.r.read(size)
        else:
            node.elements = [self.read_field_value(ord(component)) for _ in range(size)]
        return node

    def read_new_class(self) -> ClassObj:
        start = self.r.pos
        tag = self.r.u8()
        if tag != TC.CLASS:
            raise IllegalStateError("Illegal value for TC_CLASS (should be 0x76)", self.r.pos)
        class_desc, _ = self.read_class_desc()
        handle = self.new_handle()
        node = ClassObj(start, handle=handle, class_desc=class_desc)
        self.handles[handle] = node
        return node

    def read_new_enum(self) -> EnumObj:
        start = self.r.pos
        tag = self.r.u8()
        if tag != TC.ENUM:
            raise IllegalStateError("Illegal value for TC_ENUM (should be 0x7e)", self.r.pos)
        class_desc, _ = self.read_class_desc()
        handle = self.new_handle()
        constant = self.read_new_string()
        node = EnumObj(start, handle=handle, class_desc=class_desc, constant=constant)
        self.handles[handle] = node
        return node

    # --- class descriptions ---
    def read_class_desc(self) -> tuple[ClassDescLike, ClassDataDesc | None]:
        t = self.r.peek()
        match t:
            case TC.CLASSDESC | TC.PROXYCLASSDESC:
                return self.read_new_class_desc()
            case TC.NULL:
                return self.read_null(), None
            case TC.REFERENCE:
                node = self.read_prev_object()
                for cdd in self.cdds:
                    for ci in range(cdd.count()):
                        if cdd.details(ci).handle == node.handle:
                            return node, cdd.from_index(ci)
                raise IllegalStateError(
                    f"Invalid classDesc reference (0x{node.handle:08x})", self.r.pos
                )
            case _:
                raise UnknownTagError(f"illegal classDesc type {self._tag(t)}", self.r.pos)

    def read_new_class_desc(self) -> tuple[ClassDesc | ProxyClassDesc, ClassDataDesc]:
        t = self.r.peek()
        match t:
            case TC.CLASSDESC:
                return self.read_tc_classdesc()
            case TC.PROXYCLASSDESC:
                return self.read_tc_proxyclassdesc()
            case _:
                raise UnknownTagError(f"illegal newClassDesc type {self._tag(t)}", self.r.pos)

    def read_tc_classdesc(self) -> tuple[ClassDesc, ClassDataDesc]:
        start = self.r.pos
        cdd = ClassDataDesc()
        self.r.u8()  # TC_CLASSDESC
        name = self.read_utf()
        cdd.add_class(name.value)
        svuid = self.r.read(8)
        handle = self.new_handle()
        cdd.set_handle(handle)
        flags = self.r.u8()
        cdd.set_flags(flags)
        self._validate_flags(flags)
        fields = self.read_fields(cdd)
        annotations = self.read_class_annotation()
        super_desc, super_cdd = self.read_super_class_desc()
        cdd.add_super(super_cdd)
        node = ClassDesc(
            start,
            name=name,
            svuid=svuid,
            handle=handle,
            flags=flags,
            fields=fields,
            annotations=annotations,
            super_desc=super_desc,
        )
        self.handles[handle] = node
        self.cdds.append(cdd)
        return node, cdd

    def read_tc_proxyclassdesc(self) -> tuple[ProxyClassDesc, ClassDataDesc]:
        start = self.r.pos
        cdd = ClassDataDesc()
        self.r.u8()  # TC_PROXYCLASSDESC
        cdd.add_class("<Dynamic Proxy Class>")
        handle = self.new_handle()
        cdd.set_handle(handle)
        count = self._checked_size(self._signed(self.r.u32(), 32), "proxy interface count")
        interfaces = [self.read_utf() for _ in range(count)]
        annotations = self.read_class_annotation()
        super_desc, super_cdd = self.read_super_class_desc()
        cdd.add_super(super_cdd)
        node = ProxyClassDesc(
            start,
            handle=handle,
            interfaces=interfaces,
            annotations=annotations,
            super_desc=super_desc,
        )
        self.handles[handle] = node
        self.cdds.append(cdd)
        return node, cdd

    def _validate_flags(self, b1: int) -> None:
        if b1 & SC.SERIALIZABLE:
            if b1 & SC.EXTERNALIZABLE:
                raise IllegalStateError(
                    "Illegal classDescFlags, SC_SERIALIZABLE is not compatible with "
                    "SC_EXTERNALIZABLE.",
                    self.r.pos,
                )
            if b1 & SC.BLOCK_DATA:
                raise IllegalStateError(
                    "Illegal classDescFlags, SC_SERIALIZABLE is not compatible with SC_BLOCK_DATA.",
                    self.r.pos,
                )
        elif b1 & SC.EXTERNALIZABLE:
            if b1 & SC.WRITE_METHOD:
                raise IllegalStateError(
                    "Illegal classDescFlags, SC_EXTERNALIZABLE is not compatible with "
                    "SC_WRITE_METHOD.",
                    self.r.pos,
                )
        elif b1 != 0x00:
            raise IllegalStateError(
                "Illegal classDescFlags, must include either SC_SERIALIZABLE or SC_EXTERNALIZABLE.",
                self.r.pos,
            )

    def read_fields(self, cdd: ClassDataDesc) -> list[FieldDesc]:
        count = self._checked_size(self._signed(self.r.u16(), 16), "field count")
        fields: list[FieldDesc] = []
        for _ in range(count):
            fields.append(self.read_field_desc(cdd))
        return fields

    def read_field_desc(self, cdd: ClassDataDesc) -> FieldDesc:
        tc = self.r.u8()
        cdd.add_field(tc)
        c = chr(tc)
        if c not in "BCDFIJSZ[L":
            raise IllegalStateError(f"Illegal field type code ('{c}', 0x{tc:02x})", self.r.pos)
        name = self.read_utf()
        cdd.set_fname(name.value)
        class_name1: StringVal | Reference | None = None
        if c in ("[", "L"):
            class_name1 = self.read_new_string()
            cdd.set_fcn1(class_name1.value if isinstance(class_name1, StringVal) else "[TC_REF]")
        return FieldDesc(tc=c, name=name, class_name1=class_name1)

    def read_class_annotation(self) -> list[Node]:
        annotations: list[Node] = []
        while self.r.peek() != TC.ENDBLOCKDATA:
            annotations.append(self.read_content())
        self.r.u8()  # consume TC_ENDBLOCKDATA
        return annotations

    def read_super_class_desc(self) -> tuple[ClassDescLike | None, ClassDataDesc | None]:
        node, cdd = self.read_class_desc()
        return node, cdd

    # --- strings ---
    def read_new_string(self) -> StringVal | Reference:
        t = self.r.peek()
        match t:
            case TC.STRING:
                return self.read_tc_string()
            case TC.LONGSTRING:
                return self.read_tc_longstring()
            case TC.REFERENCE:
                return self.read_prev_object()
            case _:
                raise UnknownTagError(f"illegal newString type {self._tag(t)}", self.r.pos)

    def read_tc_string(self) -> StringVal:
        start = self.r.pos
        self.r.u8()  # TC_STRING
        handle = self.new_handle()
        utf = self.read_utf()
        node = StringVal(start, handle=handle, value=utf.value, raw=utf.raw, long=False)
        self.handles[handle] = node
        return node

    def read_tc_longstring(self) -> StringVal:
        start = self.r.pos
        self.r.u8()  # TC_LONGSTRING
        handle = self.new_handle()
        utf = self.read_long_utf()
        node = StringVal(start, handle=handle, value=utf.value, raw=utf.raw, long=True)
        self.handles[handle] = node
        return node

    def read_utf(self) -> Utf:
        ln = self.r.u16()
        raw = self.r.read(ln)
        return Utf(value=mutf8.decode(raw), raw=raw)

    def read_long_utf(self) -> Utf:
        ln = self._checked_size(self._signed(self.r.u64(), 64), "long string length")
        raw = self.r.read(ln)
        return Utf(value=mutf8.decode(raw), raw=raw)

    # --- references / null / block data ---
    def read_prev_object(self) -> Reference:
        start = self.r.pos
        self.r.u8()  # TC_REFERENCE
        handle = self.r.u32()
        return Reference(start, handle=handle, target=self.handles.get(handle))

    def read_null(self) -> Null:
        start = self.r.pos
        self.r.u8()  # TC_NULL
        return Null(start)

    def _reset_handles(self) -> None:
        """Reset the wire-handle table (TC_RESET semantics)."""
        self.handle = BASE_WIRE_HANDLE
        self.cdds = []
        self.handles = {}

    def read_reset(self) -> Reset:
        start = self.r.pos
        self.r.u8()  # TC_RESET
        self._reset_handles()
        return Reset(start)

    def read_exception(self) -> ExceptionObj:
        # TC_EXCEPTION resets the handle table, writes the Throwable, then resets
        # again. (The reference jar does not implement this; behaviour is verified
        # by hand in tests/test_protocol.py.)
        start = self.r.pos
        self.r.u8()  # TC_EXCEPTION
        self._reset_handles()
        throwable = self.read_content()
        self._reset_handles()
        return ExceptionObj(start, throwable=throwable)

    def read_block_data(self) -> BlockData:
        start = self.r.pos
        self.r.u8()  # TC_BLOCKDATA
        ln = self.r.u8()
        return BlockData(start, data=self.r.read(ln), long=False)

    def read_long_block_data(self) -> BlockData:
        start = self.r.pos
        self.r.u8()  # TC_BLOCKDATALONG
        ln = self._checked_size(self._signed(self.r.u32(), 32), "block data length")
        return BlockData(start, data=self.r.read(ln), long=True)

    # --- primitives ---
    def read_byte(self) -> Primitive:
        start = self.r.pos
        raw = self.r.read(1)
        return Primitive(start, tc="B", value=self._signed(raw[0], 8), raw=raw)

    def read_char(self) -> Primitive:
        start = self.r.pos
        raw = self.r.read(2)
        return Primitive(start, tc="C", value=(raw[0] << 8) + raw[1], raw=raw)

    def read_double(self) -> Primitive:
        start = self.r.pos
        raw = self.r.read(8)
        return Primitive(start, tc="D", value=float(struct.unpack(">d", raw)[0]), raw=raw)

    def read_float(self) -> Primitive:
        start = self.r.pos
        raw = self.r.read(4)
        return Primitive(start, tc="F", value=float(struct.unpack(">f", raw)[0]), raw=raw)

    def read_int(self) -> Primitive:
        start = self.r.pos
        raw = self.r.read(4)
        return Primitive(start, tc="I", value=self._signed(int.from_bytes(raw, "big"), 32), raw=raw)

    def read_long(self) -> Primitive:
        # Correct big-endian signed 64-bit read (upstream's int-shift bug fixed).
        start = self.r.pos
        raw = self.r.read(8)
        return Primitive(start, tc="J", value=self._signed(int.from_bytes(raw, "big"), 64), raw=raw)

    def read_short(self) -> Primitive:
        start = self.r.pos
        raw = self.r.read(2)
        return Primitive(start, tc="S", value=self._signed((raw[0] << 8) + raw[1], 16), raw=raw)

    def read_bool(self) -> Primitive:
        start = self.r.pos
        raw = self.r.read(1)
        return Primitive(start, tc="Z", value=raw[0] != 0, raw=raw)


_RECURSION_LIMIT = 400_000
_STACK_BYTES = 512 * 1024 * 1024


def run_deep(fn: Callable[[], T]) -> T:
    """Run ``fn`` in a worker thread with a large C stack and a high recursion
    limit, so a deeply nested stream cannot overflow the interpreter's C stack
    (only ~1 MiB on the main thread on Windows). Exhausting even that budget
    raises a clean :class:`IllegalStateError` instead of crashing the process.
    """
    result: list[T] = []
    failure: list[BaseException] = []

    def target() -> None:
        limit = sys.getrecursionlimit()
        sys.setrecursionlimit(_RECURSION_LIMIT)
        try:
            result.append(fn())
        except BaseException as exc:  # noqa: BLE001 - re-raised on the calling thread
            failure.append(exc)
        finally:
            sys.setrecursionlimit(limit)

    try:
        prev = threading.stack_size(_STACK_BYTES)
    except (ValueError, RuntimeError, OverflowError):
        prev = 0
    try:
        worker = threading.Thread(target=target, name="deaced-parse")
        worker.start()
        worker.join()
    finally:
        try:
            threading.stack_size(prev)
        except (ValueError, RuntimeError, OverflowError):
            pass

    if failure:
        exc = failure[0]
        if isinstance(exc, RecursionError):
            raise IllegalStateError("maximum nesting depth exceeded") from exc
        raise exc
    return result[0]


def parse(data: bytes) -> Stream:
    """Parse ``data`` and return the stream as a semantic AST (:class:`Stream`).

    Parsing runs in a worker thread with an enlarged stack (see :func:`run_deep`)
    so that deeply nested streams raise a clean error rather than crashing.
    """
    return run_deep(lambda: Parser(data).parse())
