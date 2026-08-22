"""Tests for the ``Expr`` operator-overloading wrapper and its ``expr()`` entry point.

Nothing here wires ``Expr`` into the operation builders -- that is task 4. These tests only cover
tree construction: that each operator produces the node the plan names, and the asymmetries the
class docstring documents (``==``/``!=`` not overloaded, ``Expr`` unhashable).
"""

from collections.abc import Iterator

import pytest
from pydantic import TypeAdapter

from eq1_pulse.builder import build_sequence, var, var_decl
from eq1_pulse.builder._expressions import Expr, expr
from eq1_pulse.models.basic_types import Amplitude, Frequency, Time
from eq1_pulse.models.expressions import (
    BinaryExpr,
    CallExpr,
    CompareExpr,
    Expression,
    LiteralExpr,
    LogicalExpr,
    SymbolExpr,
    UnaryExpr,
)
from eq1_pulse.models.reference_types import VariableRef


@pytest.fixture
def a() -> Iterator[Expr]:
    """A declared variable ``"a"``, wrapped in ``Expr``."""
    with build_sequence():
        var_decl("a", "float", unit="mV")
        yield expr(var("a"))


class TestExprConstruction:
    """``expr()``'s normalization of each accepted input kind."""

    def test_wraps_a_symbol_ref(self):
        with build_sequence():
            var_decl("a", "float")
            node = expr(var("a")).unwrap()
        assert isinstance(node, SymbolExpr)
        assert node.symbol == VariableRef("a")

    def test_wraps_a_raw_value_as_a_literal(self):
        node = expr(3.5).unwrap()
        assert isinstance(node, LiteralExpr)
        assert node.value == 3.5

    def test_wraps_a_bool_as_a_literal(self):
        node = expr(True).unwrap()
        assert isinstance(node, LiteralExpr)
        assert node.value is True

    def test_wraps_an_amplitude_instance_as_a_literal(self):
        """The complex-voltage member task 1's ``SymbolValue`` fix added is reachable through ``expr()``."""
        node = expr(Amplitude("80mV")).unwrap()
        assert isinstance(node, LiteralExpr)
        assert isinstance(node.value, Amplitude)
        assert node.value == Amplitude("80mV")

    def test_wraps_a_dimensional_quantity_as_a_literal(self):
        node = expr(Frequency(GHz=5)).unwrap()
        assert isinstance(node, LiteralExpr)
        assert isinstance(node.value, Frequency)
        assert node.value == Frequency(GHz=5)

    def test_identity_on_an_expr(self):
        wrapped = expr(3)
        assert expr(wrapped) is wrapped

    def test_identity_on_a_bare_node(self):
        node = BinaryExpr(op="+", left=LiteralExpr(value=1), right=LiteralExpr(value=2))
        assert expr(node).unwrap() is node

    def test_expr_of_expr_is_expr_of_x(self):
        once = expr(3)
        twice = expr(expr(3))
        assert once.unwrap() == twice.unwrap()


class TestArithmeticOperators:
    """``+ - * / %`` and their reflected variants, and unary ``-``/``abs()``."""

    @pytest.mark.parametrize(
        ("op", "symbol"),
        [
            (lambda x, y: x + y, "+"),
            (lambda x, y: x - y, "-"),
            (lambda x, y: x * y, "*"),
            (lambda x, y: x / y, "/"),
            (lambda x, y: x % y, "%"),
        ],
    )
    def test_binary_op_produces_the_right_node(self, a, op, symbol):
        node = op(a, 2).unwrap()
        assert isinstance(node, BinaryExpr)
        assert node.op == symbol
        assert node.left == a.unwrap()
        assert node.right == expr(2).unwrap()

    def test_reflected_forms_differ_only_in_operand_order(self, a):
        left = (a * 2).unwrap()
        right = (2 * a).unwrap()
        assert isinstance(left, BinaryExpr)
        assert isinstance(right, BinaryExpr)
        assert left.op == right.op == "*"
        assert left.left == right.right == a.unwrap()
        assert left.right == right.left == expr(2).unwrap()

    @pytest.mark.parametrize(
        ("op", "symbol"),
        [
            (lambda x, y: x.__radd__(y), "+"),
            (lambda x, y: x.__rsub__(y), "-"),
            (lambda x, y: x.__rmul__(y), "*"),
            (lambda x, y: x.__rtruediv__(y), "/"),
            (lambda x, y: x.__rmod__(y), "%"),
        ],
    )
    def test_reflected_op_puts_other_on_the_left(self, a, op, symbol):
        node = op(a, 2).unwrap()
        assert isinstance(node, BinaryExpr)
        assert node.op == symbol
        assert node.left == expr(2).unwrap()
        assert node.right == a.unwrap()

    def test_unary_negation(self, a):
        node = (-a).unwrap()
        assert isinstance(node, UnaryExpr)
        assert node.op == "-"
        assert node.operand == a.unwrap()

    def test_abs_is_a_call_expr(self, a):
        node = abs(a).unwrap()
        assert isinstance(node, CallExpr)
        assert node.function == "abs"
        assert node.args == [a.unwrap()]


class TestComparisonOperators:
    """``< <= > >=`` work directly; ``==``/``!=`` are ``.eq()``/``.ne()``."""

    @pytest.mark.parametrize(
        ("op", "symbol"),
        [
            (lambda x, y: x < y, "<"),
            (lambda x, y: x <= y, "<="),
            (lambda x, y: x > y, ">"),
            (lambda x, y: x >= y, ">="),
        ],
    )
    def test_comparison_op_produces_the_right_node(self, a, op, symbol):
        node = op(a, 2).unwrap()
        assert isinstance(node, CompareExpr)
        assert node.op == symbol
        assert node.left == a.unwrap()
        assert node.right == expr(2).unwrap()

    def test_eq_produces_a_compare_expr(self, a):
        node = a.eq(2).unwrap()
        assert isinstance(node, CompareExpr)
        assert node.op == "=="
        assert node.left == a.unwrap()
        assert node.right == expr(2).unwrap()

    def test_ne_produces_a_compare_expr(self, a):
        node = a.ne(2).unwrap()
        assert isinstance(node, CompareExpr)
        assert node.op == "!="

    def test_dunder_eq_does_not_build_a_compare_expr(self, a):
        """The asymmetry the class docstring documents: ``==`` is identity, not a node builder."""
        other = expr(var("a"))
        assert not isinstance(a == other, Expr)
        assert (a == other) is False
        assert (a == a) is True


class TestLogicalOperators:
    """``.and_()`` / ``.or_()`` / ``.not_()`` build ``LogicalExpr``; ``and``/``or``/``not`` cannot be overloaded."""

    def test_and(self, a):
        node = a.and_(True).unwrap()
        assert isinstance(node, LogicalExpr)
        assert node.op == "and"
        assert node.operands == [a.unwrap(), expr(True).unwrap()]

    def test_or(self, a):
        node = a.or_(True).unwrap()
        assert isinstance(node, LogicalExpr)
        assert node.op == "or"
        assert node.operands == [a.unwrap(), expr(True).unwrap()]

    def test_not(self, a):
        node = a.not_().unwrap()
        assert isinstance(node, LogicalExpr)
        assert node.op == "not"
        assert node.operands == [a.unwrap()]


def test_expr_is_unhashable(a):
    with pytest.raises(TypeError, match="unhashable"):
        hash(a)


def test_a_deep_expression_round_trips(a):
    """Operators compose into a multi-level tree, same as the model layer's own depth tests."""
    tree = ((a + 1) * 2 - abs(-a)) / (a % 3)
    node = tree.unwrap()
    assert isinstance(node, BinaryExpr)
    assert node.op == "/"
    # Round-trip through the model layer to check the composed tree actually validates.
    dumped = node.model_dump_json()
    TypeAdapter(Expression).validate_json(dumped)


def test_expr_rejects_a_string_that_matches_no_known_unit():
    with pytest.raises(ValueError, match="is not a number followed by one of the known units"):
        expr("not_a_quantity")


def test_expr_wraps_time_from_a_unit_suffixed_string():
    node = expr("10us").unwrap()
    assert isinstance(node, LiteralExpr)
    assert isinstance(node.value, Time)
    assert node.value == Time(us=10)
