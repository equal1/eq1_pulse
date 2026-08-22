"""Tests for the expression node models."""

import json
from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from eq1_pulse.models.basic_types import Amplitude, ComplexVoltage
from eq1_pulse.models.expressions import (
    MAX_EXPRESSION_DEPTH,
    BinaryExpr,
    CallExpr,
    CompareExpr,
    Expression,
    LiteralExpr,
    LogicalExpr,
    SymbolExpr,
    UnaryExpr,
)
from eq1_pulse.models.reference_types import ExternalRef, VariableRef


def expression_adapter() -> TypeAdapter[Any]:
    """The ``Expression`` union as a validator."""
    return TypeAdapter(Expression)


def nested_negations(levels: int) -> Any:
    """Build a tree *levels* nodes deep: a literal under ``levels - 1`` negations."""
    expression: Any = LiteralExpr(value=1)
    for _ in range(levels - 1):
        expression = UnaryExpr(op="-", operand=expression)
    return expression


@pytest.mark.parametrize(
    "node",
    [
        pytest.param(LiteralExpr(value=1.5), id="literal"),
        pytest.param(SymbolExpr(symbol=VariableRef("scale")), id="symbol"),
        pytest.param(UnaryExpr(op="-", operand=LiteralExpr(value=1)), id="unary"),
        pytest.param(
            BinaryExpr(op="*", left=SymbolExpr(symbol=VariableRef("scale")), right=LiteralExpr(value=2)),
            id="binary",
        ),
        pytest.param(
            CompareExpr(op=">=", left=SymbolExpr(symbol=VariableRef("count")), right=LiteralExpr(value=3)),
            id="compare",
        ),
        pytest.param(
            LogicalExpr(
                op="and",
                operands=[
                    CompareExpr(op="<", left=SymbolExpr(symbol=VariableRef("x")), right=LiteralExpr(value=1)),
                    SymbolExpr(symbol=VariableRef("flag")),
                ],
            ),
            id="logical",
        ),
        pytest.param(CallExpr(function="abs", args=[SymbolExpr(symbol=VariableRef("x"))]), id="call"),
    ],
)
def test_each_node_round_trips(node: Any):
    """Every node type dumps to a document that validates back to the same node."""
    document = node.model_dump()
    reloaded = expression_adapter().validate_python(document)
    assert type(reloaded) is type(node)
    assert reloaded == node
    assert reloaded.model_dump() == document


@pytest.mark.parametrize(
    ("expr_type", "node_type"),
    [
        ("literal", LiteralExpr),
        ("symbol", SymbolExpr),
        ("unary", UnaryExpr),
        ("binary", BinaryExpr),
        ("compare", CompareExpr),
        ("logical", LogicalExpr),
        ("call", CallExpr),
    ],
)
def test_union_discriminates_on_expr_type(expr_type: str, node_type: type):
    """Each ``expr_type`` routes to its own node type, from a plain dict."""
    operand = {"expr_type": "literal", "value": 1}
    documents: dict[str, dict[str, Any]] = {
        "literal": {"value": 1},
        "symbol": {"symbol": {"var": "x"}},
        "unary": {"op": "-", "operand": operand},
        "binary": {"op": "+", "left": operand, "right": operand},
        "compare": {"op": "<", "left": operand, "right": operand},
        "logical": {"op": "or", "operands": [operand, operand]},
        "call": {"function": "sqrt", "args": [operand]},
    }
    node: Any = expression_adapter().validate_python({"expr_type": expr_type, **documents[expr_type]})
    assert node.expr_type == expr_type
    assert type(node) is node_type


def test_nested_tree_validates_from_a_plain_dict():
    """A three-level tree validates from a plain dict and round-trips through JSON.

    This is what a missed :meth:`~pydantic.BaseModel.model_rebuild` shows up as: a recursive
    discriminated union with an unresolved forward reference degrades its operands to plain
    :obj:`dict` instead of failing.
    """
    document = {
        "expr_type": "compare",
        "op": "<",
        "left": {
            "expr_type": "binary",
            "op": "+",
            "left": {"expr_type": "symbol", "symbol": {"var": "x"}},
            "right": {"expr_type": "literal", "value": 1},
        },
        "right": {"expr_type": "literal", "value": 2},
    }
    node: Any = expression_adapter().validate_python(document)
    assert isinstance(node, CompareExpr)
    assert isinstance(node.left, BinaryExpr)
    assert isinstance(node.left.left, SymbolExpr)
    assert isinstance(node.left.right, LiteralExpr)
    assert json.loads(node.model_dump_json()) == document


def test_unary_op_is_serialized():
    """``UnaryExpr.op`` survives serialization despite having exactly one possible value.

    A default on it would be elided by :class:`~.base_models.LeanModel` -- ordinary default elision,
    not the discriminator rule -- and the operator would vanish from the wire.
    """
    assert UnaryExpr(op="-", operand=LiteralExpr(value=1)).model_dump() == {
        "expr_type": "unary",
        "op": "-",
        "operand": {"expr_type": "literal", "value": 1},
    }


@pytest.mark.parametrize(
    ("function", "count"),
    [("min", 2), ("min", 3), ("max", 2), ("abs", 1), ("sqrt", 1), ("sin", 1), ("log", 1)],
)
def test_call_arity_accepted(function: Any, count: int):
    """``min``/``max`` take two or more arguments; every other function takes exactly one."""
    args: list[Expression] = [LiteralExpr(value=index) for index in range(count)]
    assert len(CallExpr(function=function, args=args).args) == count


@pytest.mark.parametrize(("function", "count"), [("min", 0), ("min", 1), ("max", 1), ("abs", 0), ("cos", 2)])
def test_call_arity_rejected(function: Any, count: int):
    """A wrong argument count is a validation error naming the function."""
    args: list[Expression] = [LiteralExpr(value=index) for index in range(count)]
    with pytest.raises(ValidationError, match=function):
        CallExpr(function=function, args=args)


@pytest.mark.parametrize(("op", "count"), [("not", 1), ("and", 2), ("and", 3), ("or", 2)])
def test_logical_operand_count_accepted(op: Any, count: int):
    """``not`` takes exactly one operand; ``and``/``or`` take two or more."""
    operands: list[Expression] = [LiteralExpr(value=index) for index in range(count)]
    assert len(LogicalExpr(op=op, operands=operands).operands) == count


@pytest.mark.parametrize(("op", "count"), [("not", 0), ("not", 2), ("and", 1), ("or", 0)])
def test_logical_operand_count_rejected(op: Any, count: int):
    """A wrong operand count is a validation error naming the connective."""
    operands: list[Expression] = [LiteralExpr(value=index) for index in range(count)]
    with pytest.raises(ValidationError, match=op):
        LogicalExpr(op=op, operands=operands)


def test_tree_at_the_depth_limit_builds_and_serializes():
    """A tree exactly ``MAX_EXPRESSION_DEPTH`` deep is accepted and serializes."""
    node = nested_negations(MAX_EXPRESSION_DEPTH)
    assert json.loads(node.model_dump_json())["expr_type"] == "unary"


def test_tree_past_the_depth_limit_is_rejected():
    """One level past the cap is a ValidationError naming the limit.

    Not "a :exc:`RecursionError` became a :exc:`~pydantic.ValidationError`" -- pydantic-core's own
    guard already does that on the validation path. The cap exists so that a tree the *serializer*
    cannot handle can never be built in the first place.
    """
    with pytest.raises(ValidationError, match=str(MAX_EXPRESSION_DEPTH)):
        nested_negations(MAX_EXPRESSION_DEPTH + 1)


def test_deep_tree_is_rejected_from_the_wire_too():
    """A too-deep document is rejected on validation, not only on construction."""
    document = json.loads(nested_negations(MAX_EXPRESSION_DEPTH).model_dump_json())
    with pytest.raises(ValidationError, match=str(MAX_EXPRESSION_DEPTH)):
        expression_adapter().validate_python({"expr_type": "unary", "op": "-", "operand": document})


def test_symbol_expr_keeps_the_external_reference_form():
    """A SymbolExpr over an ExternalRef round-trips with its ``{"ext": ...}`` object intact."""
    node = SymbolExpr(symbol=ExternalRef("q0.f01"))
    assert node.model_dump() == {"expr_type": "symbol", "symbol": {"ext": "q0.f01"}}
    reloaded: Any = expression_adapter().validate_python(node.model_dump())
    assert isinstance(reloaded.symbol, ExternalRef)
    assert reloaded.symbol.ext == "q0.f01"


def test_literal_expr_holds_a_complex_amplitude():
    """A LiteralExpr carries an Amplitude -- the consumer of the complex-voltage union member.

    The value narrows to :class:`~.basic_types.ComplexVoltage` on the way back in, the same
    dimension-level narrowing every refinement gets in an open value union; the document is
    unchanged.
    """
    node = LiteralExpr(value=Amplitude(mV=1 + 2j))
    assert isinstance(node.value, Amplitude)
    document = node.model_dump()
    assert document == {"expr_type": "literal", "value": {"mV": (1.0, 2.0)}}
    reloaded: Any = expression_adapter().validate_python(document)
    assert isinstance(reloaded.value, ComplexVoltage)
    assert reloaded.value.mV == 1 + 2j
    assert reloaded.model_dump() == document
