"""Operator-overloading wrapper that builds :data:`~eq1_pulse.models.expressions.Expression` trees.

:func:`expr` is the sole entry point. Nothing outside this module reads the string/dict/zero
authoring grammars again -- the raw-value branch of :class:`Expr`'s constructor delegates to
:func:`~eq1_pulse.builder._coerce.as_symbol_value`, the one place those grammars live since #10.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..models.expressions import (
    BinaryExpr,
    CallExpr,
    CompareExpr,
    ExprBase,
    LiteralExpr,
    LogicalExpr,
    SymbolExpr,
    UnaryExpr,
)
from ..models.reference_types import ExternalRef, VariableRef
from ._coerce import as_symbol_value

if TYPE_CHECKING:
    from ..models.data_ops import SymbolValueLike
    from ..models.expressions import Expression
    from ..models.reference_types import SymbolRef

__all__ = (
    "Expr",
    "ExprLike",
    "expr",
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

    def __add__(self, other: _ExprOperand) -> Expr:
        return Expr(BinaryExpr(op="+", left=self.unwrap(), right=expr(other).unwrap()))

    def __radd__(self, other: _ExprOperand) -> Expr:
        return Expr(BinaryExpr(op="+", left=expr(other).unwrap(), right=self.unwrap()))

    def __sub__(self, other: _ExprOperand) -> Expr:
        return Expr(BinaryExpr(op="-", left=self.unwrap(), right=expr(other).unwrap()))

    def __rsub__(self, other: _ExprOperand) -> Expr:
        return Expr(BinaryExpr(op="-", left=expr(other).unwrap(), right=self.unwrap()))

    def __mul__(self, other: _ExprOperand) -> Expr:
        return Expr(BinaryExpr(op="*", left=self.unwrap(), right=expr(other).unwrap()))

    def __rmul__(self, other: _ExprOperand) -> Expr:
        return Expr(BinaryExpr(op="*", left=expr(other).unwrap(), right=self.unwrap()))

    def __truediv__(self, other: _ExprOperand) -> Expr:
        return Expr(BinaryExpr(op="/", left=self.unwrap(), right=expr(other).unwrap()))

    def __rtruediv__(self, other: _ExprOperand) -> Expr:
        return Expr(BinaryExpr(op="/", left=expr(other).unwrap(), right=self.unwrap()))

    def __mod__(self, other: _ExprOperand) -> Expr:
        return Expr(BinaryExpr(op="%", left=self.unwrap(), right=expr(other).unwrap()))

    def __rmod__(self, other: _ExprOperand) -> Expr:
        return Expr(BinaryExpr(op="%", left=expr(other).unwrap(), right=self.unwrap()))

    def __neg__(self) -> Expr:
        return Expr(UnaryExpr(op="-", operand=self.unwrap()))

    def __abs__(self) -> Expr:
        return Expr(CallExpr(function="abs", args=[self.unwrap()]))

    def __lt__(self, other: _ExprOperand) -> Expr:
        return Expr(CompareExpr(op="<", left=self.unwrap(), right=expr(other).unwrap()))

    def __le__(self, other: _ExprOperand) -> Expr:
        return Expr(CompareExpr(op="<=", left=self.unwrap(), right=expr(other).unwrap()))

    def __gt__(self, other: _ExprOperand) -> Expr:
        return Expr(CompareExpr(op=">", left=self.unwrap(), right=expr(other).unwrap()))

    def __ge__(self, other: _ExprOperand) -> Expr:
        return Expr(CompareExpr(op=">=", left=self.unwrap(), right=expr(other).unwrap()))

    def eq(self, other: _ExprOperand) -> Expr:
        """Build a :class:`~.expressions.CompareExpr` testing equality with *other*.

        Not spelled ``==``; see the class docstring.

        :param other: The value to compare against.
        :return: An :class:`Expr` wrapping the comparison.
        """
        return Expr(CompareExpr(op="==", left=self.unwrap(), right=expr(other).unwrap()))

    def ne(self, other: _ExprOperand) -> Expr:
        """Build a :class:`~.expressions.CompareExpr` testing inequality with *other*.

        Not spelled ``!=``; see the class docstring.

        :param other: The value to compare against.
        :return: An :class:`Expr` wrapping the comparison.
        """
        return Expr(CompareExpr(op="!=", left=self.unwrap(), right=expr(other).unwrap()))

    def and_(self, other: _ExprOperand) -> Expr:
        """Build a :class:`~.expressions.LogicalExpr` ANDing this expression with *other*.

        Not spelled ``and``; Python's ``and`` cannot be overloaded.

        :param other: The other operand.
        :return: An :class:`Expr` wrapping the conjunction.
        """
        return Expr(LogicalExpr(op="and", operands=[self.unwrap(), expr(other).unwrap()]))

    def or_(self, other: _ExprOperand) -> Expr:
        """Build a :class:`~.expressions.LogicalExpr` ORing this expression with *other*.

        Not spelled ``or``; Python's ``or`` cannot be overloaded.

        :param other: The other operand.
        :return: An :class:`Expr` wrapping the disjunction.
        """
        return Expr(LogicalExpr(op="or", operands=[self.unwrap(), expr(other).unwrap()]))

    def not_(self) -> Expr:
        """Build a :class:`~.expressions.LogicalExpr` negating this expression.

        Not spelled ``not``; Python's ``not`` cannot be overloaded.

        :return: An :class:`Expr` wrapping the negation.
        """
        return Expr(LogicalExpr(op="not", operands=[self.unwrap()]))


def expr(value: _ExprOperand) -> Expr:
    """Wrap *value* as an :class:`Expr`, the entry point for building expression trees.

    :param value: An :class:`Expr` (returned as-is), a :data:`~.expressions.Expression` node, a
        :data:`~.reference_types.SymbolRef`, or a raw value in any of
        :data:`~.data_ops.SymbolValueLike`'s authoring forms (including a unit-suffixed string,
        read the same way the rest of the builder reads one).
    :return: *value* wrapped as an :class:`Expr`.
    """
    return value if isinstance(value, Expr) else Expr(value)
