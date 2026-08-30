"""Tests for the control-flow base models, focused on the widened ``ValueRef`` fields."""

from typing import Any

import pytest
from pydantic import ValidationError

from eq1_pulse.models.control_flow import Indices
from eq1_pulse.models.expressions import (
    BinaryExpr,
    CompareExpr,
    LenExpr,
    LiteralExpr,
    LogicalExpr,
    NotExpr,
    SweepExpr,
    SymbolExpr,
)
from eq1_pulse.models.reference_types import ExternalRef, VariableRef
from eq1_pulse.models.sequence import Conditional, Iteration, OpSequence, Repetition


def test_repetition_count_accepts_expression():
    """``RepetitionBase.count`` accepts an ``Expression``, like the rest of the widened fields."""
    count = BinaryExpr(binary_op="+", lhs=SymbolExpr(symbol=VariableRef("n")), rhs=LiteralExpr(value=1))
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
    predicate = CompareExpr(compare_op=">", lhs=SymbolExpr(symbol=VariableRef("x")), rhs=LiteralExpr(value=1))
    cond = Conditional(var=predicate, body=OpSequence([]))
    assert isinstance(cond.var, CompareExpr)


def test_conditional_accepts_logical_expr():
    """``ConditionalBase.var`` accepts a ``LogicalExpr``."""
    predicate = LogicalExpr(
        logical_op="and",
        lhs=CompareExpr(compare_op="<", lhs=SymbolExpr(symbol=VariableRef("x")), rhs=LiteralExpr(value=1)),
        rhs=SymbolExpr(symbol=VariableRef("flag")),
    )
    cond = Conditional(var=predicate, body=OpSequence([]))
    assert isinstance(cond.var, LogicalExpr)


def test_conditional_accepts_not_expr():
    """``ConditionalBase.var`` accepts a ``NotExpr``."""
    predicate = NotExpr(not_op="not", rhs=SymbolExpr(symbol=VariableRef("flag")))
    cond = Conditional(var=predicate, body=OpSequence([]))
    assert isinstance(cond.var, NotExpr)


@pytest.mark.parametrize(
    "node",
    [
        pytest.param(
            BinaryExpr(binary_op="+", lhs=SymbolExpr(symbol=VariableRef("x")), rhs=LiteralExpr(value=1)), id="binary"
        ),
        pytest.param(LiteralExpr(value=1), id="literal"),
    ],
)
def test_conditional_rejects_arithmetic_expressions(node: Any):
    """``ConditionalBase.var`` rejects an arithmetic node, naming what was passed."""
    with pytest.raises(ValidationError, match="is not a predicate"):
        Conditional(var=node, body=OpSequence([]))


def test_iteration_accepts_bare_sweep_reference():
    """``IterationBase.items`` accepts a bare ``SweepExpr``, the identity case of ``SweepSource``."""
    it = Iteration(var=VariableRef("v"), items=SweepExpr(sweep="vg"), body=OpSequence([]))
    assert isinstance(it.items, SweepExpr)


def test_iteration_accepts_a_transform_of_a_sweep():
    """``IterationBase.items`` accepts a tree reading a sweep, not just a bare reference."""
    transform = BinaryExpr(binary_op="*", lhs=SweepExpr(sweep="vg"), rhs=LiteralExpr(value=2))
    it = Iteration(var=VariableRef("p"), items=transform, body=OpSequence([]))
    assert isinstance(it.items, BinaryExpr)


def test_iteration_accepts_indices():
    """``IterationBase.items`` accepts ``Indices``, binding the position rather than an item."""
    it = Iteration(
        var=VariableRef("i"),
        items=Indices(count=LenExpr(len_op="len", operand=SweepExpr(sweep="vg"))),
        body=OpSequence([]),
    )
    assert isinstance(it.items, Indices)
    assert isinstance(it.items.count, LenExpr)


def test_iteration_rejects_a_rank_0_tree_as_items():
    """``IterationBase.items`` is a ``SweepSource``: a tree reading no sweep is rejected."""
    with pytest.raises(ValidationError):
        Iteration(var=VariableRef("i"), items=LiteralExpr(value=1), body=OpSequence([]))


def test_iteration_rejects_list_of_str():
    """``list[str]`` is removed from ``IterableSequence`` -- nothing could consume it, and never will."""
    with pytest.raises(ValidationError):
        Iteration(var=VariableRef("s"), items=["a", "b", "c"], body=OpSequence([]))
