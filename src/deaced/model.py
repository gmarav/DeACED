"""Semantic AST for a parsed Java Object Serialization stream (ADR-0001).

Nodes mirror the entities of the serialization protocol, not the text dump:
there are no presentation-only grouping nodes here -- the text renderer adds
lines like ``Contents``/``values``/``(object)``. Each node keeps the raw bytes
of its primitives -- the renderers use them to reproduce the hex columns and, in
``--offsets`` mode, to advance their own byte cursor -- and records its source
``offset`` (start position in the stream) so callers can map a node back to the
input.

:class:`Stream` is the root; :attr:`Stream.handles` maps wire handles to the
node that owns them, so :class:`Reference` targets can be resolved.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Utf:
    """A plain modified-UTF-8 string (class/field/interface name; no handle)."""

    value: str
    raw: bytes


@dataclass
class Node:
    """Base class for every AST node; ``offset`` is the start byte position."""

    offset: int


# --- values (may appear as stream content, field values or array elements) ---


@dataclass
class Null(Node):
    """``TC_NULL`` -- a null reference."""


@dataclass
class Reference(Node):
    """``TC_REFERENCE`` -- a back-reference to a previously seen handle."""

    handle: int
    target: Node | None = None


@dataclass
class StringVal(Node):
    """``TC_STRING`` / ``TC_LONGSTRING`` -- a string object with a handle."""

    handle: int
    value: str
    raw: bytes
    long: bool = False


@dataclass
class Primitive(Node):
    """A primitive field/array value (type code one of ``BCDFIJSZ``)."""

    tc: str
    value: int | float | bool
    raw: bytes


@dataclass
class BlockData(Node):
    """``TC_BLOCKDATA`` / ``TC_BLOCKDATALONG`` -- an opaque byte block."""

    data: bytes
    long: bool = False


@dataclass
class Reset(Node):
    """``TC_RESET`` -- resets the stream's handle table to the base handle."""


@dataclass
class ExceptionObj(Node):
    """``TC_EXCEPTION`` -- a serialized Throwable describing a serialization abort."""

    throwable: Node


@dataclass
class ClassObj(Node):
    """``TC_CLASS`` -- a Class object."""

    handle: int
    class_desc: ClassDescLike


@dataclass
class EnumObj(Node):
    """``TC_ENUM`` -- an enum constant."""

    handle: int
    class_desc: ClassDescLike
    constant: StringVal | Reference


@dataclass
class ArrayObj(Node):
    """``TC_ARRAY`` -- an array object.

    ``component`` is the element type code (the second char of the array class
    name). For a ``byte[]`` the data is kept in ``byte_values``; otherwise each
    element is a node in ``elements``.
    """

    handle: int
    class_desc: ClassDescLike
    component: str
    size: int
    elements: list[Node] = field(default_factory=list)
    byte_values: bytes = b""


@dataclass
class ObjectInstance(Node):
    """``TC_OBJECT`` -- a serialized object instance."""

    handle: int
    class_desc: ClassDescLike
    data: list[ClassData] = field(default_factory=list)
    na: bool = False


# --- class descriptions (the classDesc slot: one of these or Null/Reference) ---


@dataclass
class FieldDesc:
    """A field declaration inside a class description."""

    tc: str
    name: Utf
    class_name1: StringVal | Reference | None = None


@dataclass
class ClassDesc(Node):
    """``TC_CLASSDESC`` -- a concrete class description."""

    name: Utf
    svuid: bytes
    handle: int
    flags: int
    fields: list[FieldDesc] = field(default_factory=list)
    annotations: list[Node] = field(default_factory=list)
    super_desc: ClassDescLike | None = None


@dataclass
class ProxyClassDesc(Node):
    """``TC_PROXYCLASSDESC`` -- a dynamic proxy class description."""

    handle: int
    interfaces: list[Utf] = field(default_factory=list)
    annotations: list[Node] = field(default_factory=list)
    super_desc: ClassDescLike | None = None


# --- object-instance class data ---


@dataclass
class FieldValue:
    """One field's value within a class's slice of an object's data."""

    name: str
    declared_tc: str
    value: Node


@dataclass
class ClassData:
    """One class's contribution to an object's data (values + annotations)."""

    class_name: str
    serializable: bool
    values: list[FieldValue] = field(default_factory=list)
    has_annotation: bool = False
    annotations: list[Node] = field(default_factory=list)


# --- root ---


@dataclass
class Stream(Node):
    """The parsed stream: optional RMI prefix, header, and top-level contents."""

    magic: bytes
    magic_valid: bool
    version: bytes | None = None
    version_valid: bool = False
    rmi: int | None = None
    contents: list[Node] = field(default_factory=list)
    handles: dict[int, Node] = field(default_factory=dict)


#: Anything that can occupy a ``classDesc`` slot.
ClassDescLike = ClassDesc | ProxyClassDesc | Null | Reference
