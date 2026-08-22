"""Expression trees over symbols and literal values.

An expression records *what the author wrote*: ``var("t1") + ext("q0.t2")`` is a tree of nodes, not a
number. eq1_pulse validates that the tree is well formed -- correct arity, bounded depth -- and
nothing else. It does not evaluate, type, simplify, or dimension-check it: units are declared here
and enforced by the consuming framework (issue #6), and an expression type-checker would have to do
unit conversion to decide whether ``ext("q0.f01") + var("detuning")`` is legal. That is the job the
IR hands outwards.

There is one node type per *arity and result kind* rather than one per operator --
:class:`BinaryExpr` with ``op="+"``, not an ``AddExpr``. :class:`CompareExpr` and
:class:`LogicalExpr` are split out of :class:`BinaryExpr` for the same reason applied one level up:
both yield booleans, both are valid where an arithmetic node is not, and keeping them distinct makes
"is this a predicate?" answerable from :attr:`~ExprBase.expr_type` alone without inspecting ``op``.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Annotated, Any, Final, Literal, Self

from pydantic import Discriminator, model_validator

from .base_models import LeanModel
from .data_ops import SymbolValue
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
    "LiteralExpr",
    "LogicalExpr",
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
"""


class ExprBase(LeanModel):
    """Base class for all expression nodes.

    The ``expr_type`` field is a literal string naming the node type, overridden in subclasses. It
    is declared first in every one of them, which is what makes it the discriminator
    :class:`LeanModel` always serializes.
    """

    if TYPE_CHECKING:

        def __init__(self, *args, **kwargs): ...  # noqa: D107

    expr_type: Any  # str
    """The type discriminator for expression nodes."""

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

    expr_type: Literal["literal"] = "literal"
    """The type discriminator, always "literal"."""
    value: SymbolValue
    """The value itself: dimensional, boolean, or plain numeric."""

    if TYPE_CHECKING:

        def __init__(self, /, *, value: SymbolValueLike, **data): ...  # noqa: D107


class SymbolExpr(ExprBase):
    """A reference to a declared symbol appearing in an expression.

    ``symbol`` is :data:`~.reference_types.SymbolRef`, so a variable, a parameter and an external
    constant are all spelled the same way here.
    """

    expr_type: Literal["symbol"] = "symbol"
    """The type discriminator, always "symbol"."""
    symbol: SymbolRef
    """The referenced variable, parameter, or external constant."""

    if TYPE_CHECKING:

        def __init__(self, /, *, symbol: SymbolRefLike, **data): ...  # noqa: D107


class UnaryExpr(ExprBase):
    """Negation of a single operand.

    Negation is the only unary operator: ``abs`` is :class:`CallExpr` with ``function="abs"``, where
    every other named mathematical operation lives.
    """

    expr_type: Literal["unary"] = "unary"
    """The type discriminator, always "unary"."""
    op: Literal["-"]
    """The operator applied to :attr:`operand`.

    Declared without a default even though it has exactly one possible value. A default would make
    :class:`~.base_models.LeanModel` elide the field from the wire -- ordinary default elision, not
    the discriminator rule, which strips only the *first* literal field -- and the operator would
    disappear from the serialized node.
    """
    operand: Expression
    """The expression being negated."""


class BinaryExpr(ExprBase):
    """An arithmetic operation on two operands."""

    expr_type: Literal["binary"] = "binary"
    """The type discriminator, always "binary"."""
    op: Literal["+", "-", "*", "/", "%"]
    """The arithmetic operator."""
    left: Expression
    """The left-hand operand."""
    right: Expression
    """The right-hand operand."""


class CompareExpr(ExprBase):
    """A comparison of two operands, yielding a boolean.

    Separate from :class:`BinaryExpr` because its result kind is categorically different: a
    comparison is a valid :attr:`~.control_flow.ConditionalBase.var` where an arithmetic node is not.
    """

    expr_type: Literal["compare"] = "compare"
    """The type discriminator, always "compare"."""
    op: Literal["<", "<=", ">", ">=", "==", "!="]
    """The comparison operator."""
    left: Expression
    """The left-hand operand."""
    right: Expression
    """The right-hand operand."""


class LogicalExpr(ExprBase):
    """A boolean connective over one or more operands.

    ``operands`` is a list rather than ``left``/``right`` because ``not`` is unary while ``and`` and
    ``or`` are naturally n-ary. A validator checks the count.
    """

    expr_type: Literal["logical"] = "logical"
    """The type discriminator, always "logical"."""
    op: Literal["and", "or", "not"]
    """The boolean connective."""
    operands: list[Expression]
    """The operands the connective is applied to."""

    @model_validator(mode="after")
    def _validate_operand_count(self) -> Self:
        if self.op == "not":
            if len(self.operands) != 1:
                raise ValueError(f'"not" takes exactly 1 operand, got {len(self.operands)}')
        elif len(self.operands) < 2:
            raise ValueError(f'"{self.op}" takes at least 2 operands, got {len(self.operands)}')
        return self


type ExpressionFunction = Literal["min", "max", "abs", "sqrt", "sin", "cos", "tan", "exp", "log"]
"""The functions :class:`CallExpr` may name.

A closed set rather than an open string: an open one would make the IR unconsumable without an
out-of-band registry, while a closed one is checkable from the schema alone.
"""

_VARIADIC_FUNCTIONS: Final = frozenset({"min", "max"})
"""The functions taking two or more arguments; every other one takes exactly one."""


class CallExpr(ExprBase):
    """A call to one of the named functions in :data:`ExpressionFunction`."""

    expr_type: Literal["call"] = "call"
    """The type discriminator, always "call"."""
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


type Expression = Annotated[
    LiteralExpr | SymbolExpr | UnaryExpr | BinaryExpr | CompareExpr | LogicalExpr | CallExpr,
    Discriminator("expr_type"),
]
"""Any expression node, discriminated by the "expr_type" field."""


type ValueRef = SymbolRef | Expression
"""Anything that stands in for a value at a read site: a symbol, or an expression over symbols.

Defined here rather than in :mod:`~.reference_types` because it names :data:`Expression`, and this
module already imports :mod:`~.reference_types`; the other placement is a cycle. Dependencies point
one way: ``reference_types`` -> ``expressions`` -> the operation modules.

A plain ``|`` union rather than a tagged one in the style of :data:`~.data_ops.SymbolValue`: its
members are unambiguous by wire shape -- a symbol is ``{"var": ...}`` or ``{"ext": ...}``, an
expression carries ``expr_type`` -- so there is no ambiguity for a discriminator to remove.
"""

type ValueRefLike = SymbolRefLike | Expression
"""Acceptable input types for :data:`ValueRef`.

An expression has no authoring spelling of its own -- it is built by the builder's ``expr()`` -- so
this widens only the symbol side.
"""


LiteralExpr.model_rebuild()
SymbolExpr.model_rebuild()
UnaryExpr.model_rebuild()
BinaryExpr.model_rebuild()
CompareExpr.model_rebuild()
LogicalExpr.model_rebuild()
CallExpr.model_rebuild()
