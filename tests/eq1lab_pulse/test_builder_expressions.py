"""Tests for the ``Expr`` operator-overloading wrapper and its ``expr()`` entry point.

The first classes cover tree construction alone: that each operator produces the node the plan
names, and the asymmetries the class docstring documents (``==``/``!=`` not overloaded, ``Expr``
unhashable). :class:`TestExprWiredIntoBuilders` at the end covers task 4: builder functions
accepting ``Expr``/``Expression`` and checking their leaves.
"""

import re
from collections.abc import Iterator

import pytest
from pydantic import TypeAdapter, ValidationError

from eq1_pulse.builder import build_sequence, ext, extern_decl, if_, set_frequency, square_pulse, var, var_decl, wait
from eq1_pulse.builder._expressions import Expr, call_expr_, expr
from eq1_pulse.models.basic_types import Amplitude, Frequency, Time
from eq1_pulse.models.expressions import (
    BinaryExpr,
    CallExpr,
    CompareExpr,
    Expression,
    LiteralExpr,
    LogicalExpr,
    NotExpr,
    SymbolExpr,
    UnaryExpr,
)
from eq1_pulse.models.reference_types import ExternalRef, VariableRef


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
        node = BinaryExpr(binary_op="+", lhs=LiteralExpr(value=1), rhs=LiteralExpr(value=2))
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
        assert node.binary_op == symbol
        assert node.lhs == a.unwrap()
        assert node.rhs == expr(2).unwrap()

    def test_reflected_forms_differ_only_in_operand_order(self, a):
        left_expr = (a * 2).unwrap()
        right_expr = (2 * a).unwrap()
        assert isinstance(left_expr, BinaryExpr)
        assert isinstance(right_expr, BinaryExpr)
        assert left_expr.binary_op == right_expr.binary_op == "*"
        assert left_expr.lhs == right_expr.rhs == a.unwrap()
        assert left_expr.rhs == right_expr.lhs == expr(2).unwrap()

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
        assert node.binary_op == symbol
        assert node.lhs == expr(2).unwrap()
        assert node.rhs == a.unwrap()

    def test_unary_negation(self, a):
        node = (-a).unwrap()
        assert isinstance(node, UnaryExpr)
        assert node.unary_op == "-"
        assert node.rhs == a.unwrap()

    def test_abs_is_a_call_expr(self, a):
        node = abs(a).unwrap()
        assert isinstance(node, CallExpr)
        assert node.function == "abs"
        assert node.args == [a.unwrap()]


class TestCallExpr:
    """The free ``call_expr_()`` entry point for :class:`~.expressions.CallExpr`."""

    @pytest.mark.parametrize("function", ["abs", "sqrt", "sin", "cos", "tan", "exp", "log"])
    def test_unary_function_is_a_call_expr(self, a, function):
        node = call_expr_(function, a).unwrap()
        assert isinstance(node, CallExpr)
        assert node.function == function
        assert node.args == [a.unwrap()]

    def test_min_is_a_call_expr(self, a):
        node = call_expr_("min", a, 2, 3).unwrap()
        assert isinstance(node, CallExpr)
        assert node.function == "min"
        assert node.args == [a.unwrap(), expr(2).unwrap(), expr(3).unwrap()]

    def test_max_is_a_call_expr(self, a):
        node = call_expr_("max", a, 2).unwrap()
        assert isinstance(node, CallExpr)
        assert node.function == "max"
        assert node.args == [a.unwrap(), expr(2).unwrap()]

    def test_min_rejects_a_single_operand(self, a):
        with pytest.raises(ValidationError, match="at least 2 arguments"):
            call_expr_("min", a)


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
        assert node.compare_op == symbol
        assert node.lhs == a.unwrap()
        assert node.rhs == expr(2).unwrap()

    def test_eq_produces_a_compare_expr(self, a):
        node = a.eq(2).unwrap()
        assert isinstance(node, CompareExpr)
        assert node.compare_op == "=="
        assert node.lhs == a.unwrap()
        assert node.rhs == expr(2).unwrap()

    def test_ne_produces_a_compare_expr(self, a):
        node = a.ne(2).unwrap()
        assert isinstance(node, CompareExpr)
        assert node.compare_op == "!="

    def test_dunder_eq_does_not_build_a_compare_expr(self, a):
        """The asymmetry the class docstring documents: ``==`` is identity, not a node builder."""
        other = expr(var("a"))
        assert not isinstance(a == other, Expr)
        assert (a == other) is False
        assert (a == a) is True


class TestLogicalOperators:
    """``.and_()`` / ``.or_()`` build ``LogicalExpr``; ``.not_()`` builds ``NotExpr``.

    ``and``/``or``/``not`` cannot be overloaded in Python, hence the method spellings.
    """

    def test_and(self, a):
        node = a.and_(True).unwrap()
        assert isinstance(node, LogicalExpr)
        assert node.logical_op == "and"
        assert node.lhs == a.unwrap()
        assert node.rhs == expr(True).unwrap()

    def test_or(self, a):
        node = a.or_(True).unwrap()
        assert isinstance(node, LogicalExpr)
        assert node.logical_op == "or"
        assert node.lhs == a.unwrap()
        assert node.rhs == expr(True).unwrap()

    def test_not(self, a):
        node = a.not_().unwrap()
        assert isinstance(node, NotExpr)
        assert node.not_op == "not"
        assert node.rhs == a.unwrap()


def test_expr_is_unhashable(a):
    with pytest.raises(TypeError, match="unhashable"):
        hash(a)


def test_a_deep_expression_round_trips(a):
    """Operators compose into a multi-level tree, same as the model layer's own depth tests."""
    tree = ((a + 1) * 2 - abs(-a)) / (a % 3)
    node = tree.unwrap()
    assert isinstance(node, BinaryExpr)
    assert node.binary_op == "/"
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


class TestExprWiredIntoBuilders:
    """Task 4: builder functions accept ``Expr``/``Expression`` and check their leaves."""

    def test_pulse_parameter_accepts_an_expression(self):
        with build_sequence():
            var_decl("scale", "float")
            pulse = square_pulse(duration="25ns", amplitude=expr(var("scale")) * Amplitude("80mV"))
        assert isinstance(pulse.amplitude, BinaryExpr)

    def test_wait_duration_accepts_an_expression(self):
        with build_sequence():
            var_decl("step", "int")
            var_decl("tau_step", "int")
            wait("ch1", duration=expr(var("step")) * expr(var("tau_step")))

    def test_set_frequency_accepts_an_expression(self):
        with build_sequence():
            extern_decl("q0.f01", "float", unit="GHz")
            var_decl("detuning", "float", unit="MHz")
            set_frequency("q0_drive", expr(ext("q0.f01")) + expr(var("detuning")))

    def test_undeclared_variable_leaf_raises(self):
        # VariableRef built directly, bypassing var()'s own declaration check, so the RuntimeError
        # below is verifiably the leaf walker's, not var()'s.
        undeclared_b = expr(SymbolExpr(symbol=VariableRef(var="b")))
        with build_sequence():
            var_decl("a", "int")
            with pytest.raises(RuntimeError, match="Variable 'b' has not been declared"):
                wait("ch1", duration=expr(var("a")) + undeclared_b)

    def test_undeclared_external_leaf_raises(self):
        # Built directly from ExternalRef, bypassing ext()'s own declaration check, so the
        # RuntimeError below is verifiably the leaf walker's, not ext()'s.
        undeclared = expr(SymbolExpr(symbol=ExternalRef(ext="q0.f01")))
        with build_sequence():
            with pytest.raises(RuntimeError, match=re.escape("External symbol 'q0.f01' has not been declared")):
                wait("ch1", duration=undeclared)

    def test_undeclared_leaf_three_levels_deep_raises(self):
        # VariableRef built directly, bypassing var()'s own declaration check, so the leaf is
        # undeclared only three BinaryExpr levels deep -- exactly what the walker exists to catch.
        undeclared_c = expr(SymbolExpr(symbol=VariableRef(var="c")))
        with build_sequence():
            var_decl("a", "int")
            var_decl("b", "int")
            tree = ((expr(var("a")) + expr(var("b"))) * 2) - undeclared_c
            with pytest.raises(RuntimeError, match="Variable 'c' has not been declared"):
                wait("ch1", duration=tree)

    def test_if_accepts_a_comparison_expression(self):
        with build_sequence():
            var_decl("count", "int")
            with if_(expr(var("count")) > 5):
                pass

    def test_if_rejects_an_arithmetic_expression(self):
        with build_sequence():
            var_decl("count", "int")
            with pytest.raises(ValidationError, match="not a predicate"):
                with if_(expr(var("count")) + 1):
                    pass

    def test_bare_expression_model_is_accepted_unwrapped(self):
        with build_sequence():
            node = expr("10us").unwrap()
            wait("ch1", duration=node)
