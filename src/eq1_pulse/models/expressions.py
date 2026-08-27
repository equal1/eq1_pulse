"""Expression trees over symbols and literal values.

An expression records *what the author wrote*: ``var("t1") + ext("q0.t2")`` is a tree of nodes, not a
number. eq1_pulse validates that the tree is well formed -- correct arity, bounded depth -- and
nothing else. It does not evaluate, type, simplify, or dimension-check it: units are declared here
and enforced by the consuming framework (issue #6), and an expression type-checker would have to do
unit conversion to decide whether ``ext("q0.f01") + var("detuning")`` is legal. That is the job the
IR hands outwards.

There is one node type per *arity and result kind* rather than one per operator --
:class:`BinaryExpr` with ``op="+"``, not an ``AddExpr``. :class:`CompareExpr`, :class:`NotExpr` and
:class:`LogicalExpr` are split out of :class:`UnaryExpr`/:class:`BinaryExpr` for the same reason
applied one level up: all three yield booleans, all are valid where an arithmetic node is not, and
keeping them distinct makes "is this a predicate?" answerable from the node type alone, as well as
in Python. :class:`NotExpr` and :class:`LogicalExpr` are themselves split by arity, the same way
:class:`UnaryExpr` and :class:`BinaryExpr` are: ``not`` is unary, ``and``/``or`` are binary, and a
single node type spanning both would need an optional field and a validator to enforce which
operator requires which -- exactly the awkwardness arity-specific node types elsewhere in this
module avoid.

**Wire form.** Every node is a JSON array, ``[<tag>, <operand>, ...]``, not an object. For the six
operator nodes (:class:`UnaryExpr` through :class:`CallExpr`) ``<tag>`` is the operator itself --
``"+"``, ``"<"``, ``"abs"`` -- and the rest of the array is its operand(s), in declaration order.
:class:`LiteralExpr` and :class:`SymbolExpr` hold no operator, only a single payload field, so
``<tag>`` there is that field's own name -- ``"value"`` or ``"symbol"`` -- and the array holds
exactly one operand. :class:`ExprBase` implements the array encoding once, generically over each
node's declared fields, rather than per class: adding a node type means declaring its fields, not
hand-writing its wire form.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Annotated, Any, Final, Literal, Self, cast, get_args, get_origin

from pydantic import Discriminator, Tag, model_serializer, model_validator
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema

from .base_models import NoExtrasModel
from .reference_types import SymbolRef

if TYPE_CHECKING:
    from pydantic import GetJsonSchemaHandler

    from .data_ops import SymbolValueLike
    from .reference_types import SymbolRefLike

__all__ = (
    "MAX_EXPRESSION_DEPTH",
    "BinaryExpr",
    "CallExpr",
    "CompareExpr",
    "ExprBase",
    "Expression",
    "LiteralExpr",
    "LogicalExpr",
    "NotExpr",
    "SymbolExpr",
    "UnaryExpr",
    "ValueRef",
    "ValueRefLike",
)


MAX_EXPRESSION_DEPTH: Final = 32
"""The deepest expression tree that may be built.

The cap is on the **serialization** path, not the validation one: pydantic-core has its own recursion
guard while validating, so a deep tree already fails there with a
:exc:`~pydantic.ValidationError`. The serializer has no such guard -- past its recursion limit
``model_dump_json()`` degrades into a storm of ``PydanticSerializationUnexpectedValue`` *warnings*
and emits wrong output. Rejecting a too-deep tree on the way in means one can never be built to
serialize. Hand-written expressions do not approach 32.

The cap is on *Python* nesting, which :func:`_expression_depth` measures. The array wire form nests
one level of JSON per level of Python -- an operand is the array element directly, not wrapped in an
intervening tag/payload object -- so the serialized JSON stays proportional to this cap rather than
doubling it.
"""


class ExprBase(NoExtrasModel):
    """Base class for all expression nodes; see the module docstring for the array wire form.

    The encoding is generic over each subclass's declared fields: the first field is the tag
    (an operator, or -- for the two single-field leaf nodes -- the field's own name), and every
    field after it is an operand, either one-per-field or, for the two nodes with a variable
    number of operands, gathered from a single ``list[Expression]`` field.
    """

    if TYPE_CHECKING:

        def __init__(self, *args, **kwargs): ...  # noqa: D107

    @classmethod
    def _tag_field(cls) -> str:
        """The name of this node's first declared field: its operator, or its sole payload field."""
        return next(iter(cls.model_fields))

    @classmethod
    def _operand_fields(cls) -> list[str]:
        """The names of the fields after :meth:`_tag_field`, in declaration order.

        Empty for :class:`LiteralExpr` and :class:`SymbolExpr`, whose one field *is* the tag field.
        """
        return list(cls.model_fields)[1:]

    @classmethod
    def _variadic_field(cls) -> str | None:
        """The name of this node's single ``list[Expression]`` operand field, if it has one.

        :class:`LogicalExpr` and :class:`CallExpr` hold a variable number of operands in one such
        field; every other operator node has exactly one field per operand instead.
        """
        fields = cls._operand_fields()
        if len(fields) == 1 and get_origin(cls.model_fields[fields[0]].annotation) is list:
            return fields[0]
        return None

    @model_validator(mode="before")
    @classmethod
    def _from_wire(cls, data: Any) -> Any:
        if not isinstance(data, list | tuple):
            return data
        tag_field = cls._tag_field()
        operand_fields = cls._operand_fields()
        if not operand_fields:
            if len(data) != 2:
                raise ValueError(f'{cls.__name__} wire form is ["{tag_field}", <value>], got {len(data)} elements')
            return {tag_field: data[1]}
        if not data:
            raise ValueError(f"{cls.__name__} wire form is a non-empty array")
        if (variadic_field := cls._variadic_field()) is not None:
            return {tag_field: data[0], variadic_field: list(data[1:])}
        if len(data) - 1 != len(operand_fields):
            raise ValueError(f"{cls.__name__} wire form takes {len(operand_fields)} operand(s), got {len(data) - 1}")
        return {tag_field: data[0], **dict(zip(operand_fields, data[1:], strict=True))}

    @model_serializer(mode="plain")
    def _to_wire(self) -> list[Any]:
        tag_field = self._tag_field()
        operand_fields = self._operand_fields()
        if not operand_fields:
            return [tag_field, getattr(self, tag_field)]
        tag = getattr(self, tag_field)
        if (variadic_field := self._variadic_field()) is not None:
            return [tag, *getattr(self, variadic_field)]
        return [tag, *(getattr(self, field) for field in operand_fields)]

    @staticmethod
    def _field_core_schemas(core_schema: CoreSchema) -> dict[str, Any]:
        """Find *core_schema*'s per-field core schemas, keyed by field name.

        Walked out of the actual core schema rather than rebuilt from the field annotations with a
        fresh :class:`~pydantic.TypeAdapter`: every operand field is typed :data:`Expression`, which
        names this very class back, and a fresh ``TypeAdapter(Expression)`` built *while* this
        class's own schema is still being generated recurses without ever finding a base case. The
        schema already being built has that recursion resolved -- each such field is a
        ``"definition-ref"`` into the surrounding document's shared definitions -- so this walks
        down to it instead of re-deriving it.

        :param core_schema: This node's own core schema, however many validator layers deep.
        :return: Each declared field's core schema, by field name.
        """

        def find_fields(schema: Any) -> dict[str, Any] | None:
            if isinstance(schema, dict):
                if schema.get("type") == "model-fields":
                    return cast(dict[str, Any], schema["fields"])
                for value in schema.values():
                    if (found := find_fields(value)) is not None:
                        return found
            elif isinstance(schema, list):
                for item in schema:
                    if (found := find_fields(item)) is not None:
                        return found
            return None

        fields = find_fields(core_schema)
        if fields is None:
            raise KeyError("no model-fields schema found")
        return {name: field["schema"] for name, field in fields.items()}

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler) -> JsonSchemaValue:
        """Describe this node's array wire form, in both validation and serialization mode.

        The default schema handler renders a ``model_validator(mode="before")``-wrapped model as if
        the validator were not there: the plain field-keyed object shape, not the array the wire
        form actually is. Rebuilt here from the field core schemas instead -- the same fix
        :class:`~.base_models.LeanModel` applies to the equivalent problem on the serialization
        side, needed on both sides here because the array shape holds in both directions.

        :param core_schema: this node's own core schema, walked by :meth:`_field_core_schemas` to
            find each field's schema.
        :param handler: the handler producing the default JSON schema, reused so refs land in the
            same ``$defs``/``components.schemas`` collection as the rest of the document.
        :return: the JSON schema describing this node's ``[<tag>, <operand>, ...]`` array form.
        """
        field_schemas = cls._field_core_schemas(core_schema)
        tag_field = cls._tag_field()
        operand_fields = cls._operand_fields()
        tag_schema = handler(field_schemas[tag_field])
        if not operand_fields:
            return {
                "type": "array",
                "prefixItems": [{"const": tag_field}, tag_schema],
                "minItems": 2,
                "maxItems": 2,
                "title": cls.__name__,
            }
        if (variadic_field := cls._variadic_field()) is not None:
            return {
                "type": "array",
                "prefixItems": [tag_schema],
                "items": handler(field_schemas[variadic_field]["items_schema"]),
                "minItems": 2,
                "title": cls.__name__,
            }
        prefix_items = [tag_schema, *(handler(field_schemas[f]) for f in operand_fields)]
        return {
            "type": "array",
            "prefixItems": prefix_items,
            "minItems": len(prefix_items),
            "maxItems": len(prefix_items),
            "title": cls.__name__,
        }

    @model_validator(mode="after")
    def _validate_depth(self) -> Self:
        depth = _expression_depth(self)
        if depth > MAX_EXPRESSION_DEPTH:
            raise ValueError(f"expression nests {depth} levels deep, exceeding the limit of {MAX_EXPRESSION_DEPTH}")
        return self


def _operands_of(node: ExprBase) -> Iterator[ExprBase]:
    """Yield the expression nodes directly held by *node*.

    Read off the field values rather than from a per-class list of operand names, so a node type
    added later is walked without registering it anywhere.

    :param node: The expression node whose operands to yield
    :return: An iterator over the direct operands, in field order
    """
    for value in node.__dict__.values():
        if isinstance(value, ExprBase):
            yield value
        elif isinstance(value, list):
            yield from (item for item in value if isinstance(item, ExprBase))


def _expression_depth(expression: ExprBase) -> int:
    """Return how many levels of nodes *expression* is, counting itself as one.

    Walked breadth-first with an explicit queue rather than recursively: this runs on trees that
    have not yet been depth-checked, and a recursive walk would hit the interpreter's own limit
    before reporting the one this is measuring.

    :param expression: The root of the tree to measure
    :return: The number of node levels, at least 1
    """
    depth = 0
    level = [expression]
    while level:
        depth += 1
        level = [operand for node in level for operand in _operands_of(node)]
    return depth


class LiteralExpr(ExprBase):
    """A concrete value appearing in an expression.

    ``value`` is :data:`~.data_ops.SymbolValue` -- the same union that types a declaration's
    ``default``, so there is one notion of "a concrete value" across the IR.
    """

    value: SymbolValue
    """The value itself: dimensional, boolean, or plain numeric."""

    if TYPE_CHECKING:

        def __init__(self, /, *, value: SymbolValueLike, **data): ...  # noqa: D107


class SymbolExpr(ExprBase):
    """A reference to a declared symbol appearing in an expression.

    ``symbol`` is :data:`~.reference_types.SymbolRef`, so a variable, a parameter and an external
    constant are all spelled the same way here.
    """

    symbol: SymbolRef
    """The referenced variable, parameter, or external constant."""

    if TYPE_CHECKING:

        def __init__(self, /, *, symbol: SymbolRefLike, **data): ...  # noqa: D107


class UnaryExpr(ExprBase):
    """Negation of a single operand.

    Negation is the only unary operator: ``abs`` is :class:`CallExpr` with ``function="abs"``, where
    every other named mathematical operation lives.
    """

    unary_op: Literal["-"]
    """The operator applied to :attr:`rhs`.

    Declared without a default even though it has exactly one possible value: it is
    :meth:`ExprBase._tag_field`, and must appear as this node's wire-array first element,
    ``["-", operand]``, on every dump.
    """
    rhs: Expression
    """The expression being negated."""


class BinaryExpr(ExprBase):
    """An arithmetic operation on two operands."""

    binary_op: Literal["+", "-", "*", "/", "%"]
    """The arithmetic operator."""
    lhs: Expression
    """The left-hand operand."""
    rhs: Expression
    """The right-hand operand."""


class CompareExpr(ExprBase):
    """A comparison of two operands, yielding a boolean.

    Separate from :class:`BinaryExpr` because its result kind is categorically different: a
    comparison is a valid :attr:`~.control_flow.ConditionalBase.var` where an arithmetic node is not.
    """

    compare_op: Literal["<", "<=", ">", ">=", "==", "!="]
    """The comparison operator."""
    lhs: Expression
    """The left-hand operand."""
    rhs: Expression
    """The right-hand operand."""


class NotExpr(ExprBase):
    """Boolean negation of a single operand.

    Split out from :class:`LogicalExpr` by arity, the same way :class:`UnaryExpr` is split from
    :class:`BinaryExpr`: ``not`` is the only unary boolean connective, so it gets its own node
    instead of an optional ``lhs`` on a node shared with the binary ones.
    """

    not_op: Literal["not"]
    """The operator applied to :attr:`rhs`.

    Declared without a default even though it has exactly one possible value: it is the
    discriminator for this node, first in the class, and its wire tag besides -- read off the
    field *name* rather than repeated inside the payload, since ``"not"`` is its only possible
    value and the tag already says so. Recovered on the way back in from this field's sole
    :obj:`~typing.Literal` argument.
    """
    rhs: Expression
    """The expression being negated."""


class LogicalExpr(ExprBase):
    """A boolean connective over two operands.

    ``and``/``or`` only -- ``not`` is :class:`NotExpr`. For n-ary ``and``/``or``, nest the
    expressions (e.g., ``and(and(a, b), c)``).
    """

    logical_op: Literal["and", "or"]
    """The boolean connective."""
    lhs: Expression
    """The left operand."""
    rhs: Expression
    """The right operand."""


type ExpressionFunction = Literal["min", "max", "abs", "sqrt", "sin", "cos", "tan", "exp", "log"]
"""The functions :class:`CallExpr` may name.

A closed set rather than an open string: an open one would make the IR unconsumable without an
out-of-band registry, while a closed one is checkable from the schema alone.
"""

_VARIADIC_FUNCTIONS: Final = frozenset({"min", "max"})
"""The functions taking two or more arguments; every other one takes exactly one."""


class CallExpr(ExprBase):
    """A call to one of the named functions in :data:`ExpressionFunction`."""

    function: ExpressionFunction
    """The function being called."""
    args: list[Expression]
    """The arguments to the call."""

    @model_validator(mode="after")
    def _validate_arity(self) -> Self:
        if self.function in _VARIADIC_FUNCTIONS:
            if len(self.args) < 2:
                raise ValueError(f'"{self.function}" takes at least 2 arguments, got {len(self.args)}')
        elif len(self.args) != 1:
            raise ValueError(f'"{self.function}" takes exactly 1 argument, got {len(self.args)}')
        return self


_EXPRESSION_TAGS: Final[dict[type[ExprBase], str]] = {
    LiteralExpr: "value",
    SymbolExpr: "symbol",
    UnaryExpr: "unary_op",
    BinaryExpr: "binary_op",
    CompareExpr: "compare_op",
    NotExpr: "not_op",
    LogicalExpr: "logical_op",
    CallExpr: "function",
}
"""Expression node type -> its internal discriminator tag (see :data:`Expression`'s ``Tag``s)."""


def _operator_values(node_type: type[ExprBase]) -> tuple[str, ...]:
    """The wire-array tags *node_type* is picked out by: its operators, or its field name.

    :param node_type: One of :data:`_EXPRESSION_TAGS`' keys.
    :return: For an operator node, every value its operator field's ``Literal`` accepts. For a leaf
        node (no operand fields), a single-element tuple holding its one field's name.
    """
    tag_field = node_type._tag_field()
    if not node_type._operand_fields():
        return (tag_field,)
    annotation = node_type.model_fields[tag_field].annotation
    # CallExpr.function is spelled as the ExpressionFunction alias rather than a literal Literal[...]
    # in its field annotation, and get_args() does not see through a PEP 695 type statement.
    annotation = getattr(annotation, "__value__", annotation)
    return get_args(annotation)


_OPERATOR_TAGS: Final[dict[str, str]] = {
    operator: tag
    for node_type, tag in _EXPRESSION_TAGS.items()
    for operator in _operator_values(node_type)
    if operator != "-"  # shared by UnaryExpr and BinaryExpr; expression_tag_of resolves it by arity
}
"""Every node's wire-array first element (its operator, or a leaf's field name) -> its tag.

Excludes ``"-"``: negation and subtraction share it, and array length -- 2 elements vs. 3 -- is
what tells them apart, not the operator string alone.
"""


def expression_tag_of(value: Any) -> str | None:
    """Return the tag that discriminates *value* as an expression node, or :obj:`None`.

    :param value: A wire-form array (raw input) or an :class:`ExprBase` instance
    :return: The discriminating tag, or :obj:`None` if *value* is neither
    """
    if isinstance(value, list | tuple):
        if not value:
            return None
        operator = value[0]
        if operator == "-":
            return "unary_op" if len(value) == 2 else "binary_op"
        return _OPERATOR_TAGS.get(operator)
    for node_type, tag in _EXPRESSION_TAGS.items():
        if isinstance(value, node_type):
            return tag
    return None


type Expression = Annotated[
    Annotated[LiteralExpr, Tag("value")]
    | Annotated[SymbolExpr, Tag("symbol")]
    | Annotated[UnaryExpr, Tag("unary_op")]
    | Annotated[BinaryExpr, Tag("binary_op")]
    | Annotated[CompareExpr, Tag("compare_op")]
    | Annotated[NotExpr, Tag("not_op")]
    | Annotated[LogicalExpr, Tag("logical_op")]
    | Annotated[CallExpr, Tag("function")],
    Discriminator(expression_tag_of),
]
"""Any expression node, discriminated by its wire-array tag (see :func:`expression_tag_of`)."""


type ValueRef = SymbolRef | Expression
"""Anything that stands in for a value at a read site: a symbol, or an expression over symbols.

Defined here rather than in :mod:`~.reference_types` because it names :data:`Expression`, and this
module already imports :mod:`~.reference_types`; the other placement is a cycle. Dependencies point
one way: ``reference_types`` -> ``expressions`` -> the operation modules.

A plain ``|`` union rather than a tagged one in the style of :data:`~.data_ops.SymbolValue`: its
members are unambiguous by wire shape -- a symbol is an object, ``{"var": ...}`` or ``{"ext":
...}``, an expression is an array, ``[<tag>, <operand>, ...]`` -- so there is no ambiguity for a
discriminator to remove.
"""

type ValueRefLike = SymbolRefLike | Expression
"""Acceptable input types for :data:`ValueRef`.

An expression has no authoring spelling of its own -- it is built by the builder's ``expr()`` -- so
this widens only the symbol side.
"""


# Imported here, not at module top, because :mod:`data_ops` needs :data:`ValueRef` back (its own
# operations widen to it too) -- a real two-way edge, not just a forward reference. By the time this
# runs, `Expression`/`ValueRef` already exist in this module's namespace, so `data_ops`'s own import
# of them (below) succeeds regardless of which of the two modules is imported first.
from .data_ops import SymbolValue  # noqa: E402

LiteralExpr.model_rebuild()
SymbolExpr.model_rebuild()
UnaryExpr.model_rebuild()
BinaryExpr.model_rebuild()
CompareExpr.model_rebuild()
NotExpr.model_rebuild()
LogicalExpr.model_rebuild()
CallExpr.model_rebuild()
