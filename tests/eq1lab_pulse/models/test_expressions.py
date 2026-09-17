"""Tests for the expression node models."""

import json
import warnings
from typing import Any, cast

import pytest
from pydantic import TypeAdapter, ValidationError

from eq1_pulse.models.basic_types import Amplitude, ComplexVoltage
from eq1_pulse.models.expressions import (
    MAX_EXPRESSION_DEPTH,
    BinaryExpr,
    CallExpr,
    CompareExpr,
    Expression,
    IndexExpr,
    LenExpr,
    LiteralExpr,
    LogicalExpr,
    NotExpr,
    SweepExpr,
    SweepSource,
    SymbolExpr,
    UnaryExpr,
    ValueRef,
    expression_tag_of,
    sweep_names_in,
)
from eq1_pulse.models.reference_types import ExternalRef, VariableRef


def expression_adapter() -> TypeAdapter[Any]:
    """The ``Expression`` union as a validator."""
    return TypeAdapter(Expression)


def dump_wire(node: Any) -> list[Any]:
    """``node.model_dump()``, typed as the array it actually returns.

    Every ``ExprBase``'s ``model_dump()`` returns a :obj:`list`; pydantic's stub still says
    ``dict[str, Any]`` regardless of the model's own serializer, which makes ``mypy`` flag a direct
    ``model_dump() == [...]`` comparison as non-overlapping. *node* is untyped here, so this
    forwards whatever ``model_dump()`` actually returns without mypy re-deriving its stubbed type.
    """
    return cast(list[Any], node.model_dump())


def nested_negations(levels: int) -> Any:
    """Build a tree *levels* nodes deep: a literal under ``levels - 1`` negations."""
    expression: Any = LiteralExpr(value=1)
    for _ in range(levels - 1):
        expression = UnaryExpr(unary_op="-", rhs=expression)
    return expression


@pytest.mark.parametrize(
    "node",
    [
        pytest.param(LiteralExpr(value=1.5), id="literal"),
        pytest.param(SymbolExpr(symbol=VariableRef("scale")), id="symbol"),
        pytest.param(UnaryExpr(unary_op="-", rhs=LiteralExpr(value=1)), id="unary"),
        pytest.param(
            BinaryExpr(binary_op="*", lhs=SymbolExpr(symbol=VariableRef("scale")), rhs=LiteralExpr(value=2)),
            id="binary",
        ),
        pytest.param(
            CompareExpr(compare_op=">=", lhs=SymbolExpr(symbol=VariableRef("count")), rhs=LiteralExpr(value=3)),
            id="compare",
        ),
        pytest.param(
            LogicalExpr(
                logical_op="and",
                lhs=CompareExpr(compare_op="<", lhs=SymbolExpr(symbol=VariableRef("x")), rhs=LiteralExpr(value=1)),
                rhs=SymbolExpr(symbol=VariableRef("flag")),
            ),
            id="logical",
        ),
        pytest.param(NotExpr(not_op="not", rhs=SymbolExpr(symbol=VariableRef("flag"))), id="not"),
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
    ("wire", "node_type"),
    [
        pytest.param(["value", 1], LiteralExpr, id="literal"),
        pytest.param(["symbol", {"var": "x"}], SymbolExpr, id="symbol"),
        pytest.param(["-", ["value", 1]], UnaryExpr, id="unary"),
        pytest.param(["+", ["value", 1], ["value", 1]], BinaryExpr, id="binary"),
        pytest.param(["<", ["value", 1], ["value", 1]], CompareExpr, id="compare"),
        pytest.param(["not", ["value", 1]], NotExpr, id="not"),
        pytest.param(["or", ["value", 1], ["value", 1]], LogicalExpr, id="logical"),
        pytest.param(["sqrt", ["value", 1]], CallExpr, id="call"),
    ],
)
def test_union_discriminates_on_wire_tag(wire: list[Any], node_type: type):
    """Each wire tag routes to its own node type, from a plain list."""
    node: Any = expression_adapter().validate_python(wire)
    assert isinstance(node, node_type)


def test_minus_is_disambiguated_by_arity():
    """``"-"`` alone is unary negation; with two operands it is binary subtraction."""
    unary: Any = expression_adapter().validate_python(["-", ["value", 1]])
    binary: Any = expression_adapter().validate_python(["-", ["value", 1], ["value", 2]])
    assert isinstance(unary, UnaryExpr)
    assert isinstance(binary, BinaryExpr)


def test_nested_tree_validates_from_a_plain_list():
    """A three-level tree validates from a plain list and round-trips through JSON.

    This is what a missed :meth:`~pydantic.BaseModel.model_rebuild` shows up as: a recursive
    discriminated union with an unresolved forward reference degrades its operands to plain
    :obj:`dict`/:obj:`list` instead of failing.
    """
    document = ["<", ["+", ["symbol", {"var": "x"}], ["value", 1]], ["value", 2]]
    node: Any = expression_adapter().validate_python(document)
    assert isinstance(node, CompareExpr)
    assert isinstance(node.lhs, BinaryExpr)
    assert isinstance(node.lhs.lhs, SymbolExpr)
    assert isinstance(node.lhs.rhs, LiteralExpr)
    assert json.loads(node.model_dump_json()) == document


def test_unary_op_is_serialized():
    """``UnaryExpr.unary_op`` survives serialization despite having exactly one possible value."""
    assert dump_wire(UnaryExpr(unary_op="-", rhs=LiteralExpr(value=1))) == ["-", ["value", 1]]


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


def test_not_expr_takes_a_single_operand():
    """``NotExpr`` wraps exactly one operand in ``rhs``, with no ``lhs`` field at all."""
    node = NotExpr(not_op="not", rhs=LiteralExpr(value=1))
    assert node.not_op == "not"
    assert node.rhs == LiteralExpr(value=1)
    assert not hasattr(node, "lhs")


@pytest.mark.parametrize("logical_op", ["and", "or"])
def test_logical_expr_takes_two_operands(logical_op: Any):
    """``and``/``or`` each take exactly ``lhs`` and ``rhs`` -- no arity to validate."""
    node = LogicalExpr(logical_op=logical_op, lhs=LiteralExpr(value=1), rhs=LiteralExpr(value=2))
    assert node.logical_op == logical_op
    assert node.lhs == LiteralExpr(value=1)
    assert node.rhs == LiteralExpr(value=2)


def test_not_op_is_the_only_not_expr_value():
    """``NotExpr.not_op`` accepts only ``"not"`` -- there is no other unary boolean connective."""
    with pytest.raises(ValidationError):
        NotExpr(not_op="and", rhs=LiteralExpr(value=1))  # type: ignore[arg-type]


def test_logical_op_rejects_not():
    """``LogicalExpr.logical_op`` no longer accepts ``"not"`` -- that is :class:`NotExpr` now."""
    with pytest.raises(ValidationError):
        LogicalExpr(logical_op="not", lhs=LiteralExpr(value=1), rhs=LiteralExpr(value=2))  # type: ignore[arg-type]


def test_tree_at_the_depth_limit_builds_and_serializes():
    """A tree exactly ``MAX_EXPRESSION_DEPTH`` deep is accepted and serializes."""
    node = nested_negations(MAX_EXPRESSION_DEPTH)
    assert json.loads(node.model_dump_json())[0] == "-"


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
        expression_adapter().validate_python(["-", document])


def test_symbol_expr_keeps_the_external_reference_form():
    """A SymbolExpr over an ExternalRef round-trips with its ``{"ext": ...}`` object intact."""
    node = SymbolExpr(symbol=ExternalRef("q0.f01"))
    assert dump_wire(node) == ["symbol", {"ext": "q0.f01"}]
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
    document = dump_wire(node)
    assert document == ["value", {"mV": (1.0, 2.0)}]
    reloaded: Any = expression_adapter().validate_python(document)
    assert isinstance(reloaded.value, ComplexVoltage)
    assert reloaded.value.mV == 1 + 2j
    assert dump_wire(reloaded) == document


def test_exact_serialization_of_mixed_tree_with_warnings_as_errors():
    """A mixed tree containing all eight node types validates and round-trips exactly.

    Warnings emitted during serialization (a sign of union member mismatch) are treated as errors
    so the test fails if the union picks the wrong member.
    """
    compare_node = CompareExpr(
        compare_op="<",
        lhs=BinaryExpr(
            binary_op="+",
            lhs=SymbolExpr(symbol=VariableRef("x")),
            rhs=LiteralExpr(value=1),
        ),
        rhs=CallExpr(function="abs", args=[UnaryExpr(unary_op="-", rhs=LiteralExpr(value=2))]),
    )
    tree = LogicalExpr(
        logical_op="and",
        lhs=compare_node,
        rhs=NotExpr(not_op="not", rhs=SymbolExpr(symbol=VariableRef("flag"))),
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
    """BinaryExpr and CompareExpr differ by their operator vocabulary and do not confuse the union."""
    binary = BinaryExpr(binary_op="+", lhs=LiteralExpr(value=1), rhs=LiteralExpr(value=2))
    compare = CompareExpr(compare_op="<", lhs=LiteralExpr(value=1), rhs=LiteralExpr(value=2))

    binary_in_compare = CompareExpr(
        compare_op="<",
        lhs=binary,
        rhs=LiteralExpr(value=3),
    )
    compare_in_binary = BinaryExpr(
        binary_op="+",
        lhs=compare,
        rhs=LiteralExpr(value=3),
    )

    binary_doc = binary_in_compare.model_dump()
    binary_reloaded: Any = expression_adapter().validate_python(binary_doc)
    assert isinstance(binary_reloaded.lhs, BinaryExpr)
    assert binary_reloaded.lhs == binary

    compare_doc = compare_in_binary.model_dump()
    compare_reloaded: Any = expression_adapter().validate_python(compare_doc)
    assert isinstance(compare_reloaded.lhs, CompareExpr)
    assert compare_reloaded.lhs == compare


@pytest.mark.parametrize(
    ("tag", "document", "node_type"),
    [
        pytest.param("value", ["value", 1], LiteralExpr, id="literal"),
        pytest.param("symbol", ["symbol", {"var": "x"}], SymbolExpr, id="symbol"),
        pytest.param("unary_op", ["-", ["value", 1]], UnaryExpr, id="unary"),
        pytest.param("binary_op", ["+", ["value", 1], ["value", 2]], BinaryExpr, id="binary"),
        pytest.param("compare_op", ["<", ["value", 1], ["value", 2]], CompareExpr, id="compare"),
        pytest.param("logical_op", ["and", ["value", 1], ["value", 2]], LogicalExpr, id="logical"),
        pytest.param("not_op", ["not", ["value", 1]], NotExpr, id="not"),
        pytest.param("function", ["abs", ["value", 1]], CallExpr, id="call"),
    ],
)
def test_expression_tag_of_identifies_all_nodes(
    tag: str,
    document: list[Any],
    node_type: type,
):
    """``expression_tag_of`` returns the expected tag for every node, and the union validates it."""
    assert expression_tag_of(document) == tag
    node: Any = expression_adapter().validate_python(document)
    assert isinstance(node, node_type)


def test_expression_tag_of_returns_none_for_non_expressions():
    """``expression_tag_of`` returns None for mappings, empty/unrecognized lists, and other values."""
    assert expression_tag_of({"var": "x"}) is None
    assert expression_tag_of([]) is None
    assert expression_tag_of(["unknown_op", 1]) is None
    assert expression_tag_of(5) is None


def test_valueref_still_disambiguates():
    """ValueRef resolves expressions, variable refs, and external refs correctly."""
    adapter: TypeAdapter[Any] = TypeAdapter(ValueRef)
    assert isinstance(adapter.validate_python({"var": "x"}), VariableRef)
    assert isinstance(adapter.validate_python({"ext": "q0.f01"}), ExternalRef)
    binary_doc = ["+", ["value", 1], ["value", 2]]
    node: Any = adapter.validate_python(binary_doc)
    assert isinstance(node, BinaryExpr)


def test_no_expr_type_survives_in_dumped_tree():
    """The string 'expr_type' does not appear anywhere in a serialized tree."""
    tree = CompareExpr(
        compare_op="<",
        lhs=BinaryExpr(
            binary_op="+",
            lhs=SymbolExpr(symbol=VariableRef("scale")),
            rhs=LiteralExpr(value={"mV": 80}),
        ),
        rhs=LiteralExpr(value=2),
    )
    json_str = tree.model_dump_json()
    assert "expr_type" not in json_str


def sweep_source_adapter() -> TypeAdapter[Any]:
    """The ``SweepSource`` alias as a validator."""
    return TypeAdapter(SweepSource)


def value_ref_adapter() -> TypeAdapter[Any]:
    """The ``ValueRef`` alias as a validator."""
    return TypeAdapter(ValueRef)


@pytest.mark.parametrize(
    ("node", "document"),
    [
        pytest.param(SweepExpr(sweep="vg"), ["sweep", "vg"], id="sweep"),
        pytest.param(
            IndexExpr(
                index_op="[]",
                operand=SweepExpr(sweep="vg"),
                indices=[SymbolExpr(symbol=VariableRef("i"))],
            ),
            ["[]", ["sweep", "vg"], [["symbol", {"var": "i"}]]],
            id="index",
        ),
        pytest.param(
            LenExpr(len_op="len", operand=SweepExpr(sweep="vg")),
            ["len", ["sweep", "vg"]],
            id="len",
        ),
    ],
)
def test_sweep_nodes_match_the_normative_wire_form(node: Any, document: list[Any]):
    """Each new node dumps to the array wire form, literally, and validates back."""
    assert node.model_dump() == document
    reloaded = expression_adapter().validate_python(document)
    assert type(reloaded) is type(node)
    assert reloaded == node
    assert reloaded.model_dump() == document


def test_sweep_names_in_reads_a_bare_sweep():
    """``SweepExpr.sweep`` is a plain string, so the walk reads it off the node itself."""
    assert sweep_names_in(SweepExpr(sweep="vg")) == frozenset({"vg"})


def test_sweep_names_in_is_empty_for_a_scalar_tree():
    """A tree of literals and symbols reads no sweep."""
    tree = BinaryExpr(binary_op="+", lhs=SymbolExpr(symbol=VariableRef("x")), rhs=LiteralExpr(value=1))
    assert sweep_names_in(tree) == frozenset()


def test_sweep_names_in_collects_every_sweep_at_any_depth():
    """Rank is a property of the whole tree: a sweep anywhere in it is read."""
    tree = BinaryExpr(
        binary_op="+",
        lhs=BinaryExpr(binary_op="*", lhs=SweepExpr(sweep="d1"), rhs=LiteralExpr(value=2)),
        rhs=CallExpr(function="abs", args=[UnaryExpr(unary_op="-", rhs=SweepExpr(sweep="d2"))]),
    )
    assert sweep_names_in(tree) == frozenset({"d1", "d2"})


@pytest.mark.parametrize(
    "node",
    [
        pytest.param(
            LenExpr(
                len_op="len",
                operand=BinaryExpr(binary_op="*", lhs=SweepExpr(sweep="vg"), rhs=LiteralExpr(value=2)),
            ),
            id="len",
        ),
        pytest.param(
            IndexExpr(
                index_op="[]",
                operand=UnaryExpr(
                    unary_op="-",
                    rhs=BinaryExpr(binary_op="*", lhs=SweepExpr(sweep="vg"), rhs=LiteralExpr(value=2)),
                ),
                indices=[SymbolExpr(symbol=VariableRef("i"))],
            ),
            id="index",
        ),
    ],
)
def test_index_and_len_stop_the_walk(node: Any):
    """``IndexExpr`` and ``LenExpr`` are rank-0 however deep the sweep sits under them.

    The one subtlety in :func:`sweep_names_in`: both take a sweep and produce a scalar, exactly as
    :func:`len` of a list is an :class:`int`. Without the stop, index iteration -- one of the two
    loop forms sweeps exist for -- would be rejected at every value site.
    """
    assert sweep_names_in(node) == frozenset()
    assert sweep_names_in(BinaryExpr(binary_op="*", lhs=node, rhs=LiteralExpr(value=3))) == frozenset()


def test_index_expr_validates_at_a_value_ref_field():
    """``vg[i] * gate.gain`` is a legal amplitude: the sweep is inside an ``index_op``."""
    document = ["*", ["[]", ["sweep", "vg"], [["symbol", {"var": "i"}]]], ["symbol", {"ext": "gate.gain"}]]
    node: Any = value_ref_adapter().validate_python(document)
    assert isinstance(node, BinaryExpr)
    assert isinstance(node.lhs, IndexExpr)
    assert isinstance(node.lhs.operand, SweepExpr)
    assert dump_wire(node) == document


def test_len_expr_validates_at_a_value_ref_field():
    """A ``len_op`` is an int, so it is a legal count."""
    node: Any = value_ref_adapter().validate_python(["len", ["sweep", "vg"]])
    assert isinstance(node, LenExpr)


@pytest.mark.parametrize(
    "document",
    [
        pytest.param(["sweep", "vg"], id="bare"),
        pytest.param(["+", ["-", ["abs", ["sweep", "vg"]]], ["value", 1]], id="nested"),
    ],
)
def test_value_ref_rejects_a_sweep_naming_it(document: list[Any]):
    """A sweep at a value site is rejected wherever it sits, and the error names it."""
    with pytest.raises(ValidationError, match="vg"):
        value_ref_adapter().validate_python(document)


def test_sweep_source_rejects_a_rank_zero_tree():
    """A tree reading no sweep is not a sweep source."""
    with pytest.raises(ValidationError, match="sweep"):
        sweep_source_adapter().validate_python(["+", ["value", 1], ["value", 2]])


def test_sweep_source_accepts_a_bare_sweep_and_a_transform():
    """A one-node expression and a whole tree over it are both sweep sources."""
    assert isinstance(sweep_source_adapter().validate_python(["sweep", "vg"]), SweepExpr)
    transform = ["+", ["*", ["sweep", "detuning"], ["symbol", {"ext": "vg.m11"}]], ["symbol", {"ext": "vg.o1"}]]
    node: Any = sweep_source_adapter().validate_python(transform)
    assert isinstance(node, BinaryExpr)
    assert dump_wire(node) == transform


def test_index_expr_rejects_a_scalar_operand():
    """``IndexExpr.operand`` is a ``SweepSource``: indexing a scalar is not a thing."""
    with pytest.raises(ValidationError):
        IndexExpr(index_op="[]", operand=SymbolExpr(symbol=VariableRef("x")), indices=[LiteralExpr(value=0)])


def test_index_expr_rejects_a_sweep_index():
    """``IndexExpr.indices`` is ``ScalarExpression``: an index is a position, never a gather."""
    with pytest.raises(ValidationError, match="i_amp"):
        IndexExpr(index_op="[]", operand=SweepExpr(sweep="vg"), indices=[SweepExpr(sweep="i_amp")])


def test_index_expr_takes_several_indices():
    """``a[i, j]`` needs no second node -- ``indices`` is a list."""
    node = IndexExpr(
        index_op="[]",
        operand=SweepExpr(sweep="grid"),
        indices=[SymbolExpr(symbol=VariableRef("i")), SymbolExpr(symbol=VariableRef("j"))],
    )
    assert dump_wire(node) == ["[]", ["sweep", "grid"], [["symbol", {"var": "i"}], ["symbol", {"var": "j"}]]]


@pytest.mark.parametrize(
    "node",
    [
        pytest.param(BinaryExpr(binary_op="+", lhs=SweepExpr(sweep="s"), rhs=LiteralExpr(value=1)), id="add"),
        pytest.param(BinaryExpr(binary_op="-", lhs=LiteralExpr(value=1), rhs=SweepExpr(sweep="s")), id="sub"),
        pytest.param(BinaryExpr(binary_op="*", lhs=SweepExpr(sweep="s"), rhs=SweepExpr(sweep="t")), id="mul"),
        pytest.param(BinaryExpr(binary_op="/", lhs=SweepExpr(sweep="s"), rhs=LiteralExpr(value=2)), id="div"),
        pytest.param(BinaryExpr(binary_op="%", lhs=SweepExpr(sweep="s"), rhs=LiteralExpr(value=3)), id="mod"),
        pytest.param(UnaryExpr(unary_op="-", rhs=SweepExpr(sweep="s")), id="neg"),
        pytest.param(CallExpr(function="abs", args=[SweepExpr(sweep="s")]), id="abs"),
        pytest.param(CompareExpr(compare_op=">", lhs=SweepExpr(sweep="s"), rhs=LiteralExpr(value=0)), id="compare"),
    ],
)
def test_every_operator_takes_a_sweep(node: Any):
    """There is no allow-list: a node is rank-1 exactly when an operand is, comparisons included."""
    assert "s" in sweep_names_in(node)
    document = node.model_dump()
    reloaded = expression_adapter().validate_python(document)
    assert reloaded == node
    assert json.loads(node.model_dump_json()) == document
    assert isinstance(sweep_source_adapter().validate_python(document), type(node))


@pytest.mark.parametrize(
    ("key", "document", "node_type"),
    [
        pytest.param("sweep", ["sweep", "vg"], SweepExpr, id="sweep"),
        pytest.param("index_op", ["[]", ["sweep", "vg"], [["value", 0]]], IndexExpr, id="index"),
        pytest.param("len_op", ["len", ["sweep", "vg"]], LenExpr, id="len"),
    ],
)
def test_expression_tag_of_identifies_the_sweep_nodes(key: str, document: list[Any], node_type: type):
    """``expression_tag_of`` reads the three new tags off the registry, with no edit of its own."""
    assert expression_tag_of(document) == key
    node: Any = expression_adapter().validate_python(document)
    assert isinstance(node, node_type)
    assert expression_tag_of(node) == key


def test_existing_expression_tags_are_unchanged():
    """The eight nodes that were here keep the tags they had."""
    assert expression_tag_of(["value", 1]) == "value"
    assert expression_tag_of(["symbol", {"var": "x"}]) == "symbol"
    assert expression_tag_of(["-", ["value", 1]]) == "unary_op"
    assert expression_tag_of(["+", ["value", 1], ["value", 2]]) == "binary_op"
    assert expression_tag_of(["<", ["value", 1], ["value", 2]]) == "compare_op"
    assert expression_tag_of(["not", ["value", 1]]) == "not_op"
    assert expression_tag_of(["and", ["value", 1], ["value", 2]]) == "logical_op"
    assert expression_tag_of(["abs", ["value", 1]]) == "function"


def test_index_expr_nested_in_a_binary_expr_round_trips_through_json():
    """A nested ``index_op`` survives JSON, not only ``model_dump`` -- a missed rebuild shows here.

    Validated from a plain list, so an unresolved forward reference would leave ``operand`` as a
    :obj:`dict`/:obj:`list` rather than raising anywhere.
    """
    document = ["*", ["[]", ["sweep", "vg"], [["symbol", {"var": "i"}]]], ["len", ["sweep", "vg"]]]
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        node: Any = expression_adapter().validate_python(document)
        assert isinstance(node.lhs, IndexExpr)
        assert isinstance(node.lhs.operand, SweepExpr)
        assert isinstance(node.lhs.indices[0], SymbolExpr)
        assert isinstance(node.rhs, LenExpr)
        assert isinstance(node.rhs.operand, SweepExpr)
        assert json.loads(node.model_dump_json()) == document


def test_depth_validator_counts_the_new_nodes():
    """The new nodes are levels like any other, and a tree past the cap is still rejected."""
    inner = nested_negations(MAX_EXPRESSION_DEPTH - 2)
    node = LenExpr(
        len_op="len",
        operand=BinaryExpr(binary_op="*", lhs=SweepExpr(sweep="vg"), rhs=inner),
    )
    assert node.len_op == "len"
    with pytest.raises(ValidationError, match=str(MAX_EXPRESSION_DEPTH)):
        LenExpr(
            len_op="len",
            operand=BinaryExpr(
                binary_op="*",
                lhs=SweepExpr(sweep="vg"),
                rhs=nested_negations(MAX_EXPRESSION_DEPTH - 1),
            ),
        )


def test_index_expr_needs_at_least_one_index():
    """``a[]`` names no item. Arity is checked here as it is for ``CallExpr``."""
    with pytest.raises(ValidationError):
        IndexExpr(index_op="[]", operand=SweepExpr(sweep="vg"), indices=[])


def test_sweep_source_error_names_the_node_it_got():
    """``_require_sweep`` has no sweep to name, so it names the tree it was handed instead."""
    with pytest.raises(ValidationError, match="binary_op tree reads none"):
        sweep_source_adapter().validate_python(["+", ["value", 1], ["value", 2]])

    with pytest.raises(ValidationError, match="len_op tree reads none"):
        sweep_source_adapter().validate_python(["len", ["sweep", "vg"]])


def test_wire_form_rejects_wrong_arity():
    """A malformed wire array -- wrong element count for the operator's arity -- is rejected."""
    with pytest.raises(ValidationError):
        expression_adapter().validate_python(["+", ["value", 1]])
    with pytest.raises(ValidationError):
        expression_adapter().validate_python(["value", 1, 2])
