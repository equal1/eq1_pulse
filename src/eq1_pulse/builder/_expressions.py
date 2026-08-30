"""Operator-overloading wrapper that builds :data:`~eq1_pulse.models.expressions.Expression` trees.

:func:`expr` is the sole entry point. Nothing outside this module reads the string/dict/zero
authoring grammars again -- the raw-value branch of :class:`Expr`'s constructor delegates to
:func:`~eq1_pulse.builder._coerce.as_symbol_value`, the one place those grammars live since #10.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Never

from ..models.expressions import (
    BinaryExpr,
    CallExpr,
    CompareExpr,
    ExprBase,
    IndexExpr,
    LenExpr,
    LiteralExpr,
    LogicalExpr,
    NotExpr,
    SymbolExpr,
    UnaryExpr,
    expression_tag_of,
    sweep_names_in,
)
from ..models.reference_types import ExternalRef, VariableRef
from ._coerce import as_symbol_value

if TYPE_CHECKING:
    from ..models.data_ops import SymbolValueLike
    from ..models.expressions import Expression, ExpressionFunction
    from ..models.reference_types import SymbolRef

__all__ = (
    "Expr",
    "ExprLike",
    "call_expr_",
    "expr",
    "len_",
)


type _ExprOperand = Expr | Expression | SymbolRef | SymbolValueLike
"""Anything an operator or :class:`Expr`'s constructor accepts on either side."""

type ExprLike = Expr | Expression
"""An already-wrapped :class:`Expr` or a bare :data:`~.expressions.Expression` node.

What every builder function that widened for expressions accepts in addition to its existing
:data:`~.reference_types.SymbolRefLike`: a value already run through :func:`expr`, or a fragment
deserialized straight into an :data:`~.expressions.Expression` model.
"""


class Expr:
    """Operator-overloading wrapper that builds an :data:`~eq1_pulse.models.expressions.Expression`.

    Wraps a single expression node and returns new :class:`Expr` instances from its operators,
    rather than being a pydantic model itself. :func:`expr` is the normal way to obtain one.

    ``<``, ``<=``, ``>`` and ``>=`` build a :class:`~.expressions.CompareExpr` as expected. ``==``
    and ``!=`` do **not** -- :class:`~.reference_types.Reference`'s ``__eq__`` already means value
    comparison and pydantic relies on it, so overloading it here would make the same operator mean
    two different things depending on what it is applied to. Use :meth:`eq` / :meth:`ne` instead.
    ``and``, ``or`` and ``not`` cannot be overloaded in Python at all -- they coerce their operands
    to :class:`bool` -- so :meth:`and_`, :meth:`or_` and :meth:`not_` stand in for them. Because
    ``__eq__`` is not overloaded, instances are compared and hashed by identity; :attr:`__hash__` is
    set to :obj:`None` regardless, since a wrapper with working ``<`` but object-identity ``==``
    would otherwise be silently hashable in a way that looks meaningful but is not.
    """

    __hash__ = None  # type: ignore[assignment]

    _node: Expression

    def __init__(self, value: _ExprOperand) -> None:
        """Wrap *value* as an expression node.

        :param value: An :class:`Expr` (kept as-is), an already-built
            :data:`~.expressions.Expression` node (kept as-is), a :data:`~.reference_types.SymbolRef`
            (wrapped as a :class:`~.expressions.SymbolExpr`), or a raw value in any of
            :data:`~.data_ops.SymbolValueLike`'s authoring forms (wrapped as a
            :class:`~.expressions.LiteralExpr`).
        """
        if isinstance(value, Expr):
            self._node = value._node
        elif isinstance(value, ExprBase):
            self._node = value
        elif isinstance(value, VariableRef | ExternalRef):
            self._node = SymbolExpr(symbol=value)
        else:
            self._node = LiteralExpr(value=as_symbol_value(value))

    def unwrap(self) -> Expression:
        """Return the wrapped expression node.

        :return: The :data:`~.expressions.Expression` this :class:`Expr` wraps.
        """
        return self._node

    def __getitem__(self, index: _ExprOperand | tuple[_ExprOperand, ...]) -> Expr:
        """Build an :class:`~.expressions.IndexExpr` reading one item of this sweep.

        A tuple index becomes one entry of :attr:`~.expressions.IndexExpr.indices` per dimension,
        so ``s[i, j]`` needs no second node.

        ``__len__`` has deliberately **no** counterpart here: :func:`len` runs ``__index__`` on
        whatever it is given and rejects anything that is not a non-negative :class:`int`, which an
        expression tree can never be. :func:`len_` is the whole story.

        :param index: The position(s) of the wanted item, each passed through :func:`expr`.
        :return: An :class:`Expr` wrapping the indexing.
        :raises TypeError: If this expression reads no sweep, and so has no items to index.
        """
        node = self.unwrap()
        if not sweep_names_in(node):
            raise TypeError(
                f"cannot index this {expression_tag_of(node) or 'expression'} tree: it reads no sweep, "
                "and only a sweep has items to index"
            )
        positions = index if isinstance(index, tuple) else (index,)
        return Expr(IndexExpr(index_op="[]", operand=node, indices=[expr(p).unwrap() for p in positions]))

    def __iter__(self) -> Never:
        """Refuse iteration, which :meth:`__getitem__` would otherwise make silently infinite.

        Python falls back to the legacy sequence protocol for a class that defines
        ``__getitem__`` and no ``__iter__``: it calls ``self[0]``, ``self[1]``, ... and stops at
        :exc:`IndexError`. Every index here *succeeds*, building one more
        :class:`~.expressions.IndexExpr`, so ``list(sweep("vg"))``, ``for v in sweep("vg")`` and
        ``[*sweep("vg")]`` would each run until memory ran out. A sweep has no length at authoring
        time (:func:`len_` is a node, not a number), so there is nothing to iterate here even in
        principle -- iteration over a sweep is what :func:`~eq1_pulse.builder.core.for_` is.

        :return: Never returns.
        :raises TypeError: Always.
        """
        raise TypeError(
            "an expression cannot be iterated in Python: it has no length until the program is "
            "invoked. Iterate a sweep with for_(v, sweep(name)), its positions with "
            "for_(i, indices(len_(sweep(name)))), or index one item with sweep(name)[i]."
        )

    def __add__(self, other: _ExprOperand) -> Expr:
        return Expr(BinaryExpr(binary_op="+", lhs=self.unwrap(), rhs=expr(other).unwrap()))

    def __radd__(self, other: _ExprOperand) -> Expr:
        return Expr(BinaryExpr(binary_op="+", lhs=expr(other).unwrap(), rhs=self.unwrap()))

    def __sub__(self, other: _ExprOperand) -> Expr:
        return Expr(BinaryExpr(binary_op="-", lhs=self.unwrap(), rhs=expr(other).unwrap()))

    def __rsub__(self, other: _ExprOperand) -> Expr:
        return Expr(BinaryExpr(binary_op="-", lhs=expr(other).unwrap(), rhs=self.unwrap()))

    def __mul__(self, other: _ExprOperand) -> Expr:
        return Expr(BinaryExpr(binary_op="*", lhs=self.unwrap(), rhs=expr(other).unwrap()))

    def __rmul__(self, other: _ExprOperand) -> Expr:
        return Expr(BinaryExpr(binary_op="*", lhs=expr(other).unwrap(), rhs=self.unwrap()))

    def __truediv__(self, other: _ExprOperand) -> Expr:
        return Expr(BinaryExpr(binary_op="/", lhs=self.unwrap(), rhs=expr(other).unwrap()))

    def __rtruediv__(self, other: _ExprOperand) -> Expr:
        return Expr(BinaryExpr(binary_op="/", lhs=expr(other).unwrap(), rhs=self.unwrap()))

    def __mod__(self, other: _ExprOperand) -> Expr:
        return Expr(BinaryExpr(binary_op="%", lhs=self.unwrap(), rhs=expr(other).unwrap()))

    def __rmod__(self, other: _ExprOperand) -> Expr:
        return Expr(BinaryExpr(binary_op="%", lhs=expr(other).unwrap(), rhs=self.unwrap()))

    def __neg__(self) -> Expr:
        return Expr(UnaryExpr(unary_op="-", rhs=self.unwrap()))

    def __abs__(self) -> Expr:
        return Expr(CallExpr(function="abs", args=[self.unwrap()]))

    def __lt__(self, other: _ExprOperand) -> Expr:
        return Expr(CompareExpr(compare_op="<", lhs=self.unwrap(), rhs=expr(other).unwrap()))

    def __le__(self, other: _ExprOperand) -> Expr:
        return Expr(CompareExpr(compare_op="<=", lhs=self.unwrap(), rhs=expr(other).unwrap()))

    def __gt__(self, other: _ExprOperand) -> Expr:
        return Expr(CompareExpr(compare_op=">", lhs=self.unwrap(), rhs=expr(other).unwrap()))

    def __ge__(self, other: _ExprOperand) -> Expr:
        return Expr(CompareExpr(compare_op=">=", lhs=self.unwrap(), rhs=expr(other).unwrap()))

    def eq(self, other: _ExprOperand) -> Expr:
        """Build a :class:`~.expressions.CompareExpr` testing equality with *other*.

        Not spelled ``==``; see the class docstring.

        :param other: The value to compare against.
        :return: An :class:`Expr` wrapping the comparison.
        """
        return Expr(CompareExpr(compare_op="==", lhs=self.unwrap(), rhs=expr(other).unwrap()))

    def ne(self, other: _ExprOperand) -> Expr:
        """Build a :class:`~.expressions.CompareExpr` testing inequality with *other*.

        Not spelled ``!=``; see the class docstring.

        :param other: The value to compare against.
        :return: An :class:`Expr` wrapping the comparison.
        """
        return Expr(CompareExpr(compare_op="!=", lhs=self.unwrap(), rhs=expr(other).unwrap()))

    def and_(self, other: _ExprOperand) -> Expr:
        """Build a :class:`~.expressions.LogicalExpr` ANDing this expression with *other*.

        Not spelled ``and``; Python's ``and`` cannot be overloaded.

        :param other: The other operand.
        :return: An :class:`Expr` wrapping the conjunction.
        """
        return Expr(LogicalExpr(logical_op="and", lhs=self.unwrap(), rhs=expr(other).unwrap()))

    def or_(self, other: _ExprOperand) -> Expr:
        """Build a :class:`~.expressions.LogicalExpr` ORing this expression with *other*.

        Not spelled ``or``; Python's ``or`` cannot be overloaded.

        :param other: The other operand.
        :return: An :class:`Expr` wrapping the disjunction.
        """
        return Expr(LogicalExpr(logical_op="or", lhs=self.unwrap(), rhs=expr(other).unwrap()))

    def not_(self) -> Expr:
        """Build a :class:`~.expressions.NotExpr` negating this expression.

        Not spelled ``not``; Python's ``not`` cannot be overloaded.

        :return: An :class:`Expr` wrapping the negation.
        """
        return Expr(NotExpr(not_op="not", rhs=self.unwrap()))


def expr(value: _ExprOperand) -> Expr:
    """Wrap *value* as an :class:`Expr`, the entry point for building expression trees.

    :param value: An :class:`Expr` (returned as-is), a :data:`~.expressions.Expression` node, a
        :data:`~.reference_types.SymbolRef`, or a raw value in any of
        :data:`~.data_ops.SymbolValueLike`'s authoring forms (including a unit-suffixed string,
        read the same way the rest of the builder reads one).
    :return: *value* wrapped as an :class:`Expr`.
    """
    return value if isinstance(value, Expr) else Expr(value)


def call_expr_(function: ExpressionFunction, *operands: _ExprOperand) -> Expr:
    """Build a :class:`~.expressions.CallExpr` calling *function* with *operands*.

    A free function rather than an :class:`Expr` method: unlike ``+``/``-``/..., which prefer
    their left operand, a function call has no operand that reads naturally as "self" --
    ``call_expr_("min", a, b, c)`` treats its operands symmetrically, where a method would force
    an arbitrary one of them into the receiver position (``a.call_("min", b, c)``) for no
    benefit. The trailing underscore matches :meth:`~Expr.and_`/:meth:`~Expr.or_`/
    :meth:`~Expr.not_`; this function is not itself spelled ``min``/``max``, which are Python
    builtins the builder would otherwise shadow under ``import *``.

    :param function: The function to call.
    :param operands: The call's arguments, each passed through :func:`expr`.
    :return: An :class:`Expr` wrapping the call. :class:`~.expressions.CallExpr` validates the
        argument count against *function*'s arity (exactly 1, except ``"min"``/``"max"`` which
        take 2 or more).
    """
    return Expr(CallExpr(function=function, args=[expr(operand).unwrap() for operand in operands]))


def len_(value: _ExprOperand) -> Expr:
    """Build a :class:`~.expressions.LenExpr` reading the number of items in a sweep.

    A free function rather than ``__len__``: see :meth:`Expr.__getitem__`. It is spelled with the
    trailing underscore the rest of the builder uses for a name Python already owns, matching
    :meth:`~Expr.and_`/:meth:`~Expr.or_`/:meth:`~Expr.not_`.

    :param value: The sweep-valued expression to measure, passed through :func:`expr`.
    :return: An :class:`Expr` wrapping the length.
    :raises TypeError: If *value* reads no sweep, and so has no length.
    """
    node = expr(value).unwrap()
    if not sweep_names_in(node):
        raise TypeError(
            f"cannot take the length of this {expression_tag_of(node) or 'expression'} tree: it reads "
            "no sweep, and only a sweep has a length"
        )
    return Expr(LenExpr(len_op="len", operand=node))
