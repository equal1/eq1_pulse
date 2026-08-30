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
keeping them distinct makes "is this a predicate?" answerable from the wire key alone --
``{"compare_op": {"op": "<", ...}}`` / ``{"not_op": {"rhs": ...}}`` / ``{"logical_op": {"op": "and", ...}}``
versus ``{"unary_op": {"op": "-", ...}}`` / ``{"binary_op": {"op": "+", ...}}`` -- as well as in Python.
:class:`NotExpr` and :class:`LogicalExpr` are themselves split by arity, the same way
:class:`UnaryExpr` and :class:`BinaryExpr` are: ``not`` is unary, ``and``/``or`` are binary, and a
single node type spanning both would need an optional field and a validator to enforce which
operator requires which -- exactly the awkwardness arity-specific node types elsewhere in this
module avoid.

Nodes are split by *result kind* above; they are not split by **rank**. A sweep is a list of values
and a symbol is a scalar, but both are read by the same nodes: :class:`SweepExpr` is a leaf like
:class:`SymbolExpr`, and every operator over it is the operator already documented here, applied
elementwise. Rank is therefore a property of a *tree* rather than of a node type, computed by
:func:`sweep_names_in` -- a tree is rank-1 when it reads a sweep anywhere, and rank-0 otherwise.
:class:`IndexExpr` and :class:`LenExpr` are where rank comes back down: each takes a sweep-valued
operand and produces a scalar, so both are rank-0 whatever they read, exactly as :func:`len` of a
list is an :class:`int`. The two annotated aliases :data:`ScalarExpression` and :data:`SweepSource`
apply the walk at the boundaries that care -- every value site accepts the first, every sweep site
the second -- and nothing checks rank in between, which is what lets a sweep leaf sit under a
:class:`BinaryExpr` at all.
"""

from __future__ import annotations

import contextvars
from collections.abc import Iterator, Mapping
from typing import TYPE_CHECKING, Annotated, Any, ClassVar, Final, Literal, Self

from pydantic import AfterValidator, Discriminator, Field, Tag, model_serializer, model_validator

from .base_models import NestedWireModel
from .identifier_str import IdentifierStr
from .reference_types import SymbolRef

if TYPE_CHECKING:
    from .data_ops import SymbolValueLike
    from .reference_types import SymbolRefLike

__all__ = (
    "MAX_EXPRESSION_DEPTH",
    "BinaryExpr",
    "CallExpr",
    "CompareExpr",
    "ExprBase",
    "Expression",
    "IndexExpr",
    "LenExpr",
    "LiteralExpr",
    "LogicalExpr",
    "NotExpr",
    "ScalarExpression",
    "SweepExpr",
    "SweepSource",
    "SymbolExpr",
    "UnaryExpr",
    "ValueRef",
    "ValueRefLike",
    "sweep_names_in",
)


MAX_EXPRESSION_DEPTH: Final = 32
"""The deepest expression tree that may be built.

The cap is on the **serialization** path, not the validation one: pydantic-core has its own recursion
guard while validating, so a deep tree already fails there with a
:exc:`~pydantic.ValidationError`. The serializer has no such guard -- past its recursion limit
``model_dump_json()`` degrades into a storm of ``PydanticSerializationUnexpectedValue`` *warnings*
and emits wrong output. Rejecting a too-deep tree on the way in means one can never be built to
serialize. Hand-written expressions do not approach 32.

The cap is on *Python* nesting, which :func:`_expression_depth` measures and which the eight nodes'
:class:`~.base_models.NestedWireModel` opt-in does not change. The serialized JSON gains one level
per operator node, so a maximal tree is ~64 JSON levels deep instead of ~32 -- still an order of
magnitude under the serializer's recursion limit, which is what this cap exists to protect.
"""


_wire_serializing: contextvars.ContextVar[frozenset[int]] = contextvars.ContextVar(
    "_wire_serializing", default=frozenset()
)
"""Object ids of :class:`ExprBase` instances whose :meth:`~ExprBase._wrap_serializer` is currently
on the call stack.

Works around a pydantic-core defect in recursive models with a ``@model_serializer(mode="wrap")``
(upstream `pydantic#11812 <https://github.com/pydantic/pydantic/issues/11812>`_ and the related
`pydantic#11563 <https://github.com/pydantic/pydantic/issues/11563>`_): when such a model is
reached *through another model's field* and the model's own schema is also self-referential --
exactly the shape :data:`Expression` has, recursing directly through operand fields with no
intervening container -- pydantic-core inserts the wrap serializer twice in series for that outer
reference. The spurious second call receives the *same* instance, not its sibling operands, so it
is detectable by object identity and made a no-op: only the outer (first) call performs the tag
lift, the inner one passes the plain field dump straight through.

Kept here rather than on :class:`~.base_models.NestedWireModel` itself: :class:`ExprBase` is the
only subclass shaped this way today -- reached through a field *and* self-referential -- so every
other ``NestedWireModel`` (every operation, every pulse) pays nothing for a defect that cannot
reach it. A future subclass with the same shape needs this same guard, copied here rather than
reintroduced silently on the shared base.
"""


class ExprBase(NestedWireModel):
    """Base class for all expression nodes.

    Each node is keyed on a field it already needs -- the operator for the seven operator nodes, and
    the single payload field for the other four -- rather than on a separate discriminator field.
    Eight of the eleven opt into :class:`~.base_models.NestedWireModel`'s ``{tag: payload}`` wire
    form by setting its class vars; :class:`LiteralExpr`, :class:`SymbolExpr` and :class:`SweepExpr`
    leave them unset and stay flat, since each has exactly one field already.
    """

    if TYPE_CHECKING:

        def __init__(self, *args, **kwargs): ...  # noqa: D107

    @model_serializer(mode="wrap")
    def _wrap_serializer(self, wrapped) -> Any:
        key = id(self)
        in_progress = _wire_serializing.get()
        if key in in_progress:
            # The pydantic-core duplicate-call defect described at `_wire_serializing`: this is the
            # spurious inner invocation for the instance the outer call is already wrapping.
            return wrapped(self)

        token = _wire_serializing.set(in_progress | {key})
        try:
            return self._wrap_payload(wrapped)
        finally:
            _wire_serializing.reset(token)

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

    .. note::

       The walk visits *structure*, not distinct objects, so it is exponential in depth when the
       same operand instance is reused at both sides of a node -- ``n = BinaryExpr(lhs=n, rhs=n)``
       repeated builds a DAG whose expansion doubles per level. Pydantic does not copy submodels
       (``revalidate_instances`` is never), so an author can construct one in Python; it slows to a
       crawl around 21 levels, well under :data:`MAX_EXPRESSION_DEPTH`. Deserialized documents
       cannot hit it, since JSON has no sharing and every node arrives as its own object.

       Left as it is deliberately: memoizing on :func:`id` would fix both this and
       :func:`sweep_names_in`, which inherits the same shape, but it changes the meaning of "depth"
       for a shared subtree and is not something to decide while a feature is landing on top. To be
       investigated once the sweeps plan closes; see its execution breakdown, *Deferred*.

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


class SweepExpr(ExprBase):
    """A reference to a declared sweep appearing in an expression.

    Flat, like :class:`LiteralExpr` and :class:`SymbolExpr` -- one field, so there is nothing to
    wrap and the wire form is ``{"sweep": "vg"}`` everywhere, in a union or out of one.

    **It is the only leaf that is rank-1**, and the only node whose rank is not read off its
    operands: a tree reads a sweep exactly when one of these is somewhere in it, below any
    :class:`IndexExpr` or :class:`LenExpr`. See :func:`sweep_names_in`.
    """

    sweep: IdentifierStr
    """The name of the declared sweep being read."""

    if TYPE_CHECKING:

        def __init__(self, /, *, sweep: str, **data): ...  # noqa: D107


class UnaryExpr(ExprBase):
    """Negation of a single operand.

    Negation is the only unary operator: ``abs`` is :class:`CallExpr` with ``function="abs"``, where
    every other named mathematical operation lives.
    """

    _wire_tag_source_: ClassVar[str] = "unary_op"
    _wire_tag_from_: ClassVar[Literal["value", "name"]] = "name"
    _wire_payload_key_: ClassVar[str | None] = "op"

    unary_op: Literal["-"]
    """The operator applied to :attr:`rhs`.

    Declared without a default even though it has exactly one possible value: it is the
    discriminator for this node now, first in the class, so :class:`~.base_models.LeanModel`
    serializes it always regardless of whether it has one.
    """
    rhs: Expression
    """The expression being negated."""


class BinaryExpr(ExprBase):
    """An arithmetic operation on two operands."""

    _wire_tag_source_: ClassVar[str] = "binary_op"
    _wire_tag_from_: ClassVar[Literal["value", "name"]] = "name"
    _wire_payload_key_: ClassVar[str | None] = "op"

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

    _wire_tag_source_: ClassVar[str] = "compare_op"
    _wire_tag_from_: ClassVar[Literal["value", "name"]] = "name"
    _wire_payload_key_: ClassVar[str | None] = "op"

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

    _wire_tag_source_: ClassVar[str] = "not_op"
    _wire_tag_from_: ClassVar[Literal["value", "name"]] = "name"
    _wire_payload_key_: ClassVar[str | None] = None

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

    _wire_tag_source_: ClassVar[str] = "logical_op"
    _wire_tag_from_: ClassVar[Literal["value", "name"]] = "name"
    _wire_payload_key_: ClassVar[str | None] = "op"

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

    _wire_tag_source_: ClassVar[str] = "function"
    _wire_tag_from_: ClassVar[Literal["value", "name"]] = "name"
    _wire_payload_key_: ClassVar[str | None] = "name"

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


class IndexExpr(ExprBase):
    """One item of a sweep, as a scalar.

    Modelled on :class:`NotExpr` -- a single-valued :obj:`~typing.Literal` tag field read off the
    field *name*, so the wire form is
    ``{"index_op": {"operand": {"sweep": "vg"}, "indices": [{"symbol": {"var": "i"}}]}}``.

    :attr:`operand` is :data:`SweepSource`, so any sweep-valued tree is indexable, and the node
    **produces a scalar** whatever that tree reads -- which is what makes
    ``amplitude=sweep("vg")[var("i")]`` legal at a :data:`ValueRef` field. :attr:`indices` is
    :data:`ScalarExpression`: an index is a position, and a sweep of positions would be a gather,
    which nothing downstream could schedule. Being a list, ``a[i, j]`` needs no second node.

    Structure and depth are validated; bounds are not, and the indices are not checked against a
    declaration's ``shape``. Same *declare, never enforce* line the rest of the IR sits on.
    """

    _wire_tag_source_: ClassVar[str] = "index_op"
    _wire_tag_from_: ClassVar[Literal["value", "name"]] = "name"
    _wire_payload_key_: ClassVar[str | None] = None

    index_op: Literal["[]"]
    """The operator, declared first and without a default so it discriminates the node and is its
    wire tag besides -- read off the field *name*, since ``"[]"`` is its only possible value."""
    operand: SweepSource
    """The sweep-valued expression being indexed."""
    indices: Annotated[list[ScalarExpression], Field(min_length=1)]
    """The position of the wanted item, one entry per dimension.

    At least one: ``a[]`` names no item, and arity is the one structural thing this module does
    check -- the same line :meth:`CallExpr._validate_arity` draws.
    """


class LenExpr(ExprBase):
    """The number of items in a sweep, as an int.

    Its own node rather than a member of :data:`ExpressionFunction`, on the precedent
    :class:`CompareExpr` sets: that split is by **result kind**, and ``len`` is the one operation
    returning an :class:`int` from something that is not a number. Keeping it out also leaves
    :class:`CallExpr` honest -- every remaining member there is a scalar mathematical function,
    which over a sweep is that function applied elementwise.

    Like :class:`IndexExpr`, it takes a sweep and returns a scalar, so it is rank-0 whatever its
    operand reads.
    """

    _wire_tag_source_: ClassVar[str] = "len_op"
    _wire_tag_from_: ClassVar[Literal["value", "name"]] = "name"
    _wire_payload_key_: ClassVar[str | None] = None

    len_op: Literal["len"]
    """The operator, declared first and without a default, for the reason
    :attr:`IndexExpr.index_op` gives."""
    operand: SweepSource
    """The sweep-valued expression whose length is taken."""


_EXPRESSION_TAGS: Final[dict[type[ExprBase], str]] = {
    LiteralExpr: "value",
    SymbolExpr: "symbol",
    SweepExpr: "sweep",
    UnaryExpr: "unary_op",
    BinaryExpr: "binary_op",
    CompareExpr: "compare_op",
    NotExpr: "not_op",
    LogicalExpr: "logical_op",
    CallExpr: "function",
    IndexExpr: "index_op",
    LenExpr: "len_op",
}
"""Expression node type -> the sole wire key that discriminates it."""


def expression_tag_of(value: Any) -> str | None:
    """Return the wire key that discriminates *value* as an expression node, or :obj:`None`.

    A mapping is tagged by its **sole** key, if that key is one of :data:`_EXPRESSION_TAGS`'
    values -- every node's wire object, nested or flat, has exactly one key naming its type, so a
    mapping with any other number of keys, or a single key that names something else, carries no
    tag. Returning :obj:`None` in both cases is load-bearing: :func:`~.pulse_types._external_param_value_tag`
    depends on it to fall through to its unit and reference branches.

    A node whose payload is empty is spelled as the bare tag string by
    :class:`~.base_models.NestedWireModel`, so a string naming a node key is tagged by *being* that
    key; any other string -- a unit-suffixed quantity, a channel name -- still carries no tag.

    :param value: A mapping or a bare tag (raw input), or an :class:`ExprBase` instance
    :return: The discriminating key, or :obj:`None` if *value* is neither
    """
    if isinstance(value, str):
        return value if value in _EXPRESSION_TAGS.values() else None
    if isinstance(value, Mapping):
        if len(value) == 1:
            key = next(iter(value))
            return key if key in _EXPRESSION_TAGS.values() else None
        return None
    for node_type, tag in _EXPRESSION_TAGS.items():
        if isinstance(value, node_type):
            return tag
    return None


type Expression = Annotated[
    Annotated[LiteralExpr, Tag("value")]
    | Annotated[SymbolExpr, Tag("symbol")]
    | Annotated[SweepExpr, Tag("sweep")]
    | Annotated[UnaryExpr, Tag("unary_op")]
    | Annotated[BinaryExpr, Tag("binary_op")]
    | Annotated[CompareExpr, Tag("compare_op")]
    | Annotated[NotExpr, Tag("not_op")]
    | Annotated[LogicalExpr, Tag("logical_op")]
    | Annotated[CallExpr, Tag("function")]
    | Annotated[IndexExpr, Tag("index_op")]
    | Annotated[LenExpr, Tag("len_op")],
    Discriminator(expression_tag_of),
]
"""Any expression node, discriminated by the wire key naming its type."""


def sweep_names_in(expression: Expression) -> frozenset[str]:
    """Return the names of every sweep read anywhere in *expression*, empty for a scalar tree.

    Walked with the same :func:`_operands_of` iterator :func:`_expression_depth` uses, so a node
    type added later is walked without registering it anywhere -- with one exception, which is the
    whole subtlety of the walk: it **does not descend into** :class:`IndexExpr` or
    :class:`LenExpr`. Both take a sweep and produce a scalar, so a tree containing one reads no
    sweep *through* it, exactly as :func:`len` of a list is an :class:`int`. Without that stop,
    ``play("g", step_pulse(amplitude=sweep("vg")[var("i")]))`` -- index iteration, one of the two
    loop forms sweeps exist for -- would be rejected as rank-1 by the :data:`ValueRef` guard.

    Iterative rather than recursive, for the reason :func:`_expression_depth` is: the depth cap
    bounds any tree that has validated, but this also runs on trees mid-validation. It inherits that
    function's behaviour on a tree whose operand instances are shared -- see the note there -- and
    is unreachable for the same reason: such a tree cannot be built past ~21 levels, and cannot be
    deserialized at all.

    :param expression: The root of the tree to inspect
    :return: The sweep names read, or an empty set if the tree is rank-0
    """
    names: set[str] = set()
    pending: list[ExprBase] = [expression]
    while pending:
        node = pending.pop()
        if isinstance(node, IndexExpr | LenExpr):
            continue
        if isinstance(node, SweepExpr):
            # `sweep` is a `str`, so it is invisible to `_operands_of` and read here instead.
            names.add(node.sweep)
            continue
        pending.extend(_operands_of(node))
    return frozenset(names)


def _reject_sweeps(expression: Expression) -> Expression:
    """Validate that *expression* reads no sweep, naming the offenders if it does.

    :param expression: The expression being validated
    :return: *expression* unchanged
    :raises ValueError: If the tree reads a sweep at any depth
    """
    names = sweep_names_in(expression)
    if names:
        offenders = ", ".join(sorted(names))
        raise ValueError(
            f"a value may not read a sweep, but this expression reads {offenders}; "
            "index it (sweep(name)[i]) or iterate it with for_()"
        )
    return expression


def _require_sweep(expression: Expression) -> Expression:
    """Validate that *expression* reads at least one sweep, naming what it got instead.

    There are no sweeps to name here -- their absence is the fault -- so the message names the node
    the tree is rooted at instead. "This is not a sweep" alone is unactionable: the author needs to
    see that the tree they wrote is the rank-0 one, and that :class:`IndexExpr` and :class:`LenExpr`
    are rank-0 however deep a sweep sits under them, which is the usual way to arrive here by
    accident.

    :param expression: The expression being validated
    :return: *expression* unchanged
    :raises ValueError: If the tree reads no sweep
    """
    if not sweep_names_in(expression):
        tag = expression_tag_of(expression) or "expression"
        raise ValueError(
            f"a sweep is required here, but this {tag} tree reads none; reference a declared sweep with sweep(name)"
        )
    return expression


type ScalarExpression = Annotated[Expression, AfterValidator(_reject_sweeps)]
"""An expression that reads no sweep. What every value site accepts.

A sweep is a list and a value is a scalar, so the two are told apart by :func:`sweep_names_in` over
the whole tree rather than by union membership -- which could only ever type a leaf, leaving
``amplitude=sweep("vg") * 2`` unrepresentable and therefore unrejectable.
"""

type SweepSource = Annotated[Expression, AfterValidator(_require_sweep)]
"""An expression that reads at least one sweep. What every sweep site accepts.

A bare :class:`SweepExpr` needs no member of its own anywhere this appears: it is a one-node
expression, and this alias already admits it.
"""


type ValueRef = SymbolRef | ScalarExpression
"""Anything that stands in for a value at a read site: a symbol, or an expression over symbols.

Defined here rather than in :mod:`~.reference_types` because it names :data:`Expression`, and this
module already imports :mod:`~.reference_types`; the other placement is a cycle. Dependencies point
one way: ``reference_types`` -> ``expressions`` -> the operation modules.

A plain ``|`` union rather than a tagged one in the style of :data:`~.data_ops.SymbolValue`: its
members are unambiguous by wire shape -- a symbol is ``{"var": ...}`` or ``{"ext": ...}``, an
expression carries one of the node keys -- so there is no ambiguity for a discriminator to
remove.

The expression side is :data:`ScalarExpression` rather than :data:`Expression`, so guarding this
one alias guards every read site typed on it -- :attr:`~.channel_ops.Play.amplitude`,
:attr:`~.control_flow.Repetition.count`, :attr:`~.control_flow.ConditionalBase.var`, all of them --
against a sweep appearing where a scalar belongs, at any depth. A document that put a sweep under
an amplitude is rejected; none can exist, since sweeps are newer than this alias.

That is *nearly* every value site but not quite: :data:`~.pulse_types.ExternalParamValue` offers an
expression as one member of its own union rather than going through this alias, and carries the
same narrowing for the same reason. The two together are the whole of the rank guard on the value
side; a third value site added later must choose one of them deliberately, because neither type
error nor test failure follows from using plain :data:`Expression`.
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
SweepExpr.model_rebuild()
UnaryExpr.model_rebuild()
BinaryExpr.model_rebuild()
CompareExpr.model_rebuild()
NotExpr.model_rebuild()
LogicalExpr.model_rebuild()
CallExpr.model_rebuild()
IndexExpr.model_rebuild()
LenExpr.model_rebuild()
