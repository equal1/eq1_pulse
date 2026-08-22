"""Tests for the control-flow base models, focused on the widened ``ValueRef`` fields."""

from typing import Any

import pytest
from pydantic import ValidationError

from eq1_pulse.models.expressions import BinaryExpr, CompareExpr, LiteralExpr, LogicalExpr, SymbolExpr
from eq1_pulse.models.reference_types import ExternalRef, VariableRef
from eq1_pulse.models.sequence import Conditional, OpSequence, Repetition


def test_repetition_count_accepts_expression():
    """``RepetitionBase.count`` accepts an ``Expression``, like the rest of the widened fields."""
    count = BinaryExpr(binary_op="+", left=SymbolExpr(symbol=VariableRef("n")), right=LiteralExpr(value=1))
    rep = Repetition(count=count, body=OpSequence([]))
    assert isinstance(rep.count, BinaryExpr)


def test_conditional_accepts_bare_symbol_ref():
    """``ConditionalBase.var`` still accepts a bare ``SymbolRef``, the pre-widening form."""
    cond = Conditional(var=VariableRef("flag"), body=OpSequence([]))
    assert isinstance(cond.var, VariableRef)

    cond = Conditional(var=ExternalRef("q0.flag"), body=OpSequence([]))
    assert isinstance(cond.var, ExternalRef)


def test_conditional_accepts_compare_expr():
    """``ConditionalBase.var`` accepts a ``CompareExpr``."""
    predicate = CompareExpr(compare_op=">", left=SymbolExpr(symbol=VariableRef("x")), right=LiteralExpr(value=1))
    cond = Conditional(var=predicate, body=OpSequence([]))
    assert isinstance(cond.var, CompareExpr)


def test_conditional_accepts_logical_expr():
    """``ConditionalBase.var`` accepts a ``LogicalExpr``."""
    predicate = LogicalExpr(
        logical_op="and",
        operands=[
            CompareExpr(compare_op="<", left=SymbolExpr(symbol=VariableRef("x")), right=LiteralExpr(value=1)),
            SymbolExpr(symbol=VariableRef("flag")),
        ],
    )
    cond = Conditional(var=predicate, body=OpSequence([]))
    assert isinstance(cond.var, LogicalExpr)


@pytest.mark.parametrize(
    "node",
    [
        pytest.param(
            BinaryExpr(binary_op="+", left=SymbolExpr(symbol=VariableRef("x")), right=LiteralExpr(value=1)), id="binary"
        ),
        pytest.param(LiteralExpr(value=1), id="literal"),
    ],
)
def test_conditional_rejects_arithmetic_expressions(node: Any):
    """``ConditionalBase.var`` rejects an arithmetic node, naming what was passed."""
    with pytest.raises(ValidationError, match="is not a predicate"):
        Conditional(var=node, body=OpSequence([]))
