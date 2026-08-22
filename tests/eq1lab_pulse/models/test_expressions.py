"""Tests for the expression node models."""

import json
import warnings
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
    ValueRef,
    expression_tag_of,
)
from eq1_pulse.models.reference_types import ExternalRef, VariableRef


def expression_adapter() -> TypeAdapter[Any]:
    """The ``Expression`` union as a validator."""
    return TypeAdapter(Expression)


def nested_negations(levels: int) -> Any:
    """Build a tree *levels* nodes deep: a literal under ``levels - 1`` negations."""
    expression: Any = LiteralExpr(value=1)
    for _ in range(levels - 1):
        expression = UnaryExpr(unary_op="-", operand=expression)
    return expression


@pytest.mark.parametrize(
    "node",
    [
        pytest.param(LiteralExpr(value=1.5), id="literal"),
        pytest.param(SymbolExpr(symbol=VariableRef("scale")), id="symbol"),
        pytest.param(UnaryExpr(unary_op="-", operand=LiteralExpr(value=1)), id="unary"),
        pytest.param(
            BinaryExpr(binary_op="*", left=SymbolExpr(symbol=VariableRef("scale")), right=LiteralExpr(value=2)),
            id="binary",
        ),
        pytest.param(
            CompareExpr(compare_op=">=", left=SymbolExpr(symbol=VariableRef("count")), right=LiteralExpr(value=3)),
            id="compare",
        ),
        pytest.param(
            LogicalExpr(
                logical_op="and",
                operands=[
                    CompareExpr(compare_op="<", left=SymbolExpr(symbol=VariableRef("x")), right=LiteralExpr(value=1)),
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
    ("key", "node_type"),
    [
        ("value", LiteralExpr),
        ("symbol", SymbolExpr),
        ("unary_op", UnaryExpr),
        ("binary_op", BinaryExpr),
        ("compare_op", CompareExpr),
        ("logical_op", LogicalExpr),
        ("function", CallExpr),
    ],
)
def test_union_discriminates_on_node_key(key: str, node_type: type):
    """Each node key routes to its own node type, from a plain dict."""
    operand = {"value": 1}
    documents: dict[str, dict[str, Any]] = {
        "value": {"value": 1},
        "symbol": {"symbol": {"var": "x"}},
        "unary_op": {"unary_op": "-", "operand": operand},
        "binary_op": {"binary_op": "+", "left": operand, "right": operand},
        "compare_op": {"compare_op": "<", "left": operand, "right": operand},
        "logical_op": {"logical_op": "or", "operands": [operand, operand]},
        "function": {"function": "sqrt", "args": [operand]},
    }
    node: Any = expression_adapter().validate_python(documents[key])
    assert isinstance(node, node_type)


def test_nested_tree_validates_from_a_plain_dict():
    """A three-level tree validates from a plain dict and round-trips through JSON.

    This is what a missed :meth:`~pydantic.BaseModel.model_rebuild` shows up as: a recursive
    discriminated union with an unresolved forward reference degrades its operands to plain
    :obj:`dict` instead of failing.
    """
    document = {
        "compare_op": "<",
        "left": {
            "binary_op": "+",
            "left": {"symbol": {"var": "x"}},
            "right": {"value": 1},
        },
        "right": {"value": 2},
    }
    node: Any = expression_adapter().validate_python(document)
    assert isinstance(node, CompareExpr)
    assert isinstance(node.left, BinaryExpr)
    assert isinstance(node.left.left, SymbolExpr)
    assert isinstance(node.left.right, LiteralExpr)
    assert json.loads(node.model_dump_json()) == document


def test_unary_op_is_serialized():
    """``UnaryExpr.unary_op`` survives serialization despite having exactly one possible value.

    A default on it would be elided by :class:`~.base_models.LeanModel` -- ordinary default elision,
    not the discriminator rule -- and the operator would vanish from the wire.
    """
    assert UnaryExpr(unary_op="-", operand=LiteralExpr(value=1)).model_dump() == {
        "unary_op": "-",
        "operand": {"value": 1},
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


@pytest.mark.parametrize(("logical_op", "count"), [("not", 1), ("and", 2), ("and", 3), ("or", 2)])
def test_logical_operand_count_accepted(logical_op: Any, count: int):
    """``not`` takes exactly one operand; ``and``/``or`` take two or more."""
    operands: list[Expression] = [LiteralExpr(value=index) for index in range(count)]
    assert len(LogicalExpr(logical_op=logical_op, operands=operands).operands) == count


@pytest.mark.parametrize(("logical_op", "count"), [("not", 0), ("not", 2), ("and", 1), ("or", 0)])
def test_logical_operand_count_rejected(logical_op: Any, count: int):
    """A wrong operand count is a validation error naming the connective."""
    operands: list[Expression] = [LiteralExpr(value=index) for index in range(count)]
    with pytest.raises(ValidationError, match=logical_op):
        LogicalExpr(logical_op=logical_op, operands=operands)


def test_tree_at_the_depth_limit_builds_and_serializes():
    """A tree exactly ``MAX_EXPRESSION_DEPTH`` deep is accepted and serializes."""
    node = nested_negations(MAX_EXPRESSION_DEPTH)
    assert json.loads(node.model_dump_json())["unary_op"] == "-"


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
        expression_adapter().validate_python({"unary_op": "-", "operand": document})


def test_symbol_expr_keeps_the_external_reference_form():
    """A SymbolExpr over an ExternalRef round-trips with its ``{"ext": ...}`` object intact."""
    node = SymbolExpr(symbol=ExternalRef("q0.f01"))
    assert node.model_dump() == {"symbol": {"ext": "q0.f01"}}
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
    assert document == {"value": {"mV": (1.0, 2.0)}}
    reloaded: Any = expression_adapter().validate_python(document)
    assert isinstance(reloaded.value, ComplexVoltage)
    assert reloaded.value.mV == 1 + 2j
    assert reloaded.model_dump() == document


def test_exact_serialization_of_mixed_tree_with_warnings_as_errors():
    """A mixed tree containing all seven node types validates and round-trips exactly.

    Warnings emitted during serialization (a sign of union member mismatch) are treated as errors
    so the test fails if the union picks the wrong member.
    """
    compare_node = CompareExpr(
        compare_op="<",
        left=BinaryExpr(
            binary_op="+",
            left=SymbolExpr(symbol=VariableRef("x")),
            right=LiteralExpr(value=1),
        ),
        right=CallExpr(function="abs", args=[UnaryExpr(unary_op="-", operand=LiteralExpr(value=2))]),
    )
    tree = LogicalExpr(
        logical_op="and",
        operands=[compare_node, SymbolExpr(symbol=VariableRef("flag"))],
    )

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        document = tree.model_dump()
        reloaded = expression_adapter().validate_python(document)
        assert reloaded == tree
        json_str = tree.model_dump_json()
        json_reloaded = json.loads(json_str)
        assert json_reloaded == document


def test_binary_and_compare_expr_do_not_collide():
    """BinaryExpr and CompareExpr differ only in operator key and do not confuse the union."""
    binary = BinaryExpr(binary_op="+", left=LiteralExpr(value=1), right=LiteralExpr(value=2))
    compare = CompareExpr(compare_op="<", left=LiteralExpr(value=1), right=LiteralExpr(value=2))

    binary_in_compare = CompareExpr(
        compare_op="<",
        left=binary,
        right=LiteralExpr(value=3),
    )
    compare_in_binary = BinaryExpr(
        binary_op="+",
        left=compare,
        right=LiteralExpr(value=3),
    )

    binary_doc = binary_in_compare.model_dump()
    binary_reloaded: Any = expression_adapter().validate_python(binary_doc)
    assert isinstance(binary_reloaded.left, BinaryExpr)
    assert binary_reloaded.left == binary

    compare_doc = compare_in_binary.model_dump()
    compare_reloaded: Any = expression_adapter().validate_python(compare_doc)
    assert isinstance(compare_reloaded.left, CompareExpr)
    assert compare_reloaded.left == compare


@pytest.mark.parametrize(
    ("key", "document", "node_type"),
    [
        pytest.param("value", {"value": 1}, LiteralExpr, id="literal"),
        pytest.param("symbol", {"symbol": {"var": "x"}}, SymbolExpr, id="symbol"),
        pytest.param(
            "unary_op",
            {"unary_op": "-", "operand": {"value": 1}},
            UnaryExpr,
            id="unary",
        ),
        pytest.param(
            "binary_op",
            {"binary_op": "+", "left": {"value": 1}, "right": {"value": 2}},
            BinaryExpr,
            id="binary",
        ),
        pytest.param(
            "compare_op",
            {"compare_op": "<", "left": {"value": 1}, "right": {"value": 2}},
            CompareExpr,
            id="compare",
        ),
        pytest.param(
            "logical_op",
            {"logical_op": "not", "operands": [{"value": 1}]},
            LogicalExpr,
            id="logical",
        ),
        pytest.param(
            "function",
            {"function": "abs", "args": [{"value": 1}]},
            CallExpr,
            id="call",
        ),
    ],
)
def test_expression_tag_of_identifies_all_nodes(
    key: str,
    document: dict[str, Any],
    node_type: type,
):
    """``expression_tag_of`` returns the expected key for every node, and the union validates it."""
    assert expression_tag_of(document) == key
    node: Any = expression_adapter().validate_python(document)
    assert isinstance(node, node_type)


def test_expression_tag_of_returns_none_for_non_expressions():
    """``expression_tag_of`` returns None for mappings and values that are not expressions."""
    assert expression_tag_of({"var": "x"}) is None
    assert expression_tag_of({}) is None
    assert expression_tag_of(5) is None


def test_valueref_still_disambiguates():
    """ValueRef resolves expressions, variable refs, and external refs correctly."""
    adapter: TypeAdapter[Any] = TypeAdapter(ValueRef)
    assert isinstance(adapter.validate_python({"var": "x"}), VariableRef)
    assert isinstance(adapter.validate_python({"ext": "q0.f01"}), ExternalRef)
    binary_doc = {"binary_op": "+", "left": {"value": 1}, "right": {"value": 2}}
    node: Any = adapter.validate_python(binary_doc)
    assert isinstance(node, BinaryExpr)


def test_no_expr_type_survives_in_dumped_tree():
    """The string 'expr_type' does not appear anywhere in a serialized tree."""
    tree = CompareExpr(
        compare_op="<",
        left=BinaryExpr(
            binary_op="+",
            left=SymbolExpr(symbol=VariableRef("scale")),
            right=LiteralExpr(value={"mV": 80}),
        ),
        right=LiteralExpr(value=2),
    )
    json_str = tree.model_dump_json()
    assert "expr_type" not in json_str
