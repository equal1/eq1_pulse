"""Tests for :func:`~eq1_pulse.utilities.affine_form.affine_form` (parameter sweeps plan, task T5).

The recogniser is advisory and nothing calls it, so these tests are the whole specification of what
it recognises. Every case in the plan's recognisable set appears twice over: once as a tree that
decomposes, with its exact terms and offset asserted, and once in the shape that must come back
:obj:`None`. The last class builds plan §13's example C, the case the utility exists for -- two
affine transforms of one supplied sweep, which a generator uploads as three numbers per gate rather
than one float per item.

Expressions are built through the builder and compared as dumped wire objects: the same spelling
:file:`test_builder_sweeps.py` uses, and readable in a failure.
"""

from collections.abc import Iterator

import pytest

from eq1_pulse.builder import (
    build_sequence,
    call_expr_,
    expr,
    ext,
    extern_decl,
    len_,
    sweep,
    var,
    var_decl,
)
from eq1_pulse.builder._expressions import Expr
from eq1_pulse.utilities.affine_form import AffineForm, affine_form


@pytest.fixture
def context() -> Iterator[None]:
    """Enter a build context declaring the externals and variables these trees read.

    ``ext()`` and ``var()`` check their name against the surrounding context, so even a fragment
    that is never added to a sequence needs one.

    :return: An iterator yielding once, inside the context
    """
    with build_sequence():
        extern_decl("vg.m11", "float")
        extern_decl("vg.m21", "float")
        extern_decl("vg.o1", "float", unit="mV")
        extern_decl("vg.o2", "float", unit="mV")
        var_decl("i", "int")
        yield


def _form(expression: Expr) -> AffineForm:
    """Decompose *expression*, failing the test if it is not recognised.

    :param expression: The builder expression to decompose
    :return: Its decomposition
    """
    form = affine_form(expression.unwrap())
    assert form is not None, "expected an affine tree"
    return form


def _terms(form: AffineForm) -> dict[str, object]:
    """Dump a decomposition's scales to wire objects.

    :param form: The decomposition
    :return: Sweep name -> the scale as plain data
    """
    return {name: scale.model_dump(mode="json") for name, scale in form.terms.items()}


def _offset(form: AffineForm) -> object:
    """Dump a decomposition's offset to a wire object.

    :param form: The decomposition
    :return: The offset as plain data
    """
    return form.offset.model_dump(mode="json")


class TestRecognised:
    """The recognisable set, one test per shape, with the exact decomposition asserted."""

    def test_bare_sweep(self):
        """A bare sweep is one term of scale one, offset zero -- the implicit values, spelled out."""
        form = _form(sweep("a"))
        assert _terms(form) == {"a": {"value": 1}}
        assert _offset(form) == {"value": 0}

    def test_sweep_times_literal(self):
        """``s * 2``: the literal is the scale, not a factor of one."""
        form = _form(sweep("a") * 2)
        assert _terms(form) == {"a": {"value": 2}}
        assert _offset(form) == {"value": 0}

    def test_literal_times_sweep(self):
        """``2 * s``: a scale on the left is recognised the same way."""
        form = _form(2 * sweep("a"))
        assert _terms(form) == {"a": {"value": 2}}
        assert _offset(form) == {"value": 0}

    def test_sweep_over_literal(self):
        """``s / 2``: the scale is the quotient, left as a tree rather than folded to ``0.5``."""
        form = _form(sweep("a") / 2)
        assert _terms(form) == {"a": {"binary_op": {"op": "/", "lhs": {"value": 1}, "rhs": {"value": 2}}}}
        assert _offset(form) == {"value": 0}

    def test_negated_sweep(self):
        """``-s``: the scale is negated as a tree, for the reason ``s / 2``'s is left as one."""
        form = _form(-sweep("a"))
        assert _terms(form) == {"a": {"unary_op": {"op": "-", "rhs": {"value": 1}}}}
        assert _offset(form) == {"value": 0}

    def test_sweep_plus_scalar(self):
        """``s + 5``: the rank-0 side is the offset."""
        form = _form(sweep("a") + 5)
        assert _terms(form) == {"a": {"value": 1}}
        assert _offset(form) == {"value": 5}

    def test_scalar_minus_sweep(self):
        """``5 - s``: the sweep side is negated, the scalar side is the offset."""
        form = _form(5 - sweep("a"))
        assert _terms(form) == {"a": {"unary_op": {"op": "-", "rhs": {"value": 1}}}}
        assert _offset(form) == {"value": 5}

    def test_difference_of_two_sweeps(self):
        """``s1 - s2``: two terms over one sweep group, the second negated (plan §13 example G)."""
        form = _form(sweep("d1") - sweep("d2"))
        assert _terms(form) == {
            "d1": {"value": 1},
            "d2": {"unary_op": {"op": "-", "rhs": {"value": 1}}},
        }
        assert _offset(form) == {"value": 0}

    def test_scale_and_offset_over_externals(self, context):
        """``s * m11 + o1``: the affine transform the whole utility exists for."""
        form = _form(sweep("a") * ext("vg.m11") + ext("vg.o1"))
        assert _terms(form) == {"a": {"symbol": {"ext": "vg.m11"}}}
        assert _offset(form) == {"symbol": {"ext": "vg.o1"}}

    def test_scalar_tree_is_all_offset(self, context):
        """A tree reading no sweep has no terms and is entirely offset -- an honest decomposition."""
        form = _form(expr(2) * ext("vg.m11"))
        assert form.terms == {}
        assert _offset(form) == {"binary_op": {"op": "*", "lhs": {"value": 2}, "rhs": {"symbol": {"ext": "vg.m11"}}}}

    def test_index_and_length_land_in_the_offset(self, context):
        """``len_(s1) + s2``: both scalar-from-sweep nodes are offset, sweep and all."""
        form = _form(len_(sweep("a")) + sweep("b"))
        assert _terms(form) == {"b": {"value": 1}}
        assert _offset(form) == {"len_op": {"operand": {"sweep": "a"}}}

        indexed = _form(expr(sweep("a")[var("i")]) * 2)
        assert indexed.terms == {}
        assert _offset(indexed) == {
            "binary_op": {
                "op": "*",
                "lhs": {"index_op": {"operand": {"sweep": "a"}, "indices": [{"symbol": {"var": "i"}}]}},
                "rhs": {"value": 2},
            }
        }

    def test_scale_distributes_over_a_sum(self, context):
        """``(s1 + s2) * m11``: a scale applied to a two-term decomposition reaches both terms."""
        form = _form((sweep("d1") + sweep("d2")) * ext("vg.m11"))
        assert _terms(form) == {
            "d1": {"symbol": {"ext": "vg.m11"}},
            "d2": {"symbol": {"ext": "vg.m11"}},
        }
        assert _offset(form) == {"value": 0}

    def test_negation_reaches_scale_and_offset(self, context):
        """``-(s * m11 + o1)``: unary minus negates every scale and the offset."""
        form = _form(-(sweep("a") * ext("vg.m11") + ext("vg.o1")))
        assert _terms(form) == {"a": {"unary_op": {"op": "-", "rhs": {"symbol": {"ext": "vg.m11"}}}}}
        assert _offset(form) == {"unary_op": {"op": "-", "rhs": {"symbol": {"ext": "vg.o1"}}}}


class TestCanonicalisation:
    """One term per distinct sweep, whatever the tree's shape."""

    def test_a_sweep_read_twice_is_one_term(self):
        """``s + s`` is **one** term whose scale is ``1 + 1`` -- summed, and left unfolded."""
        form = _form(sweep("a") + sweep("a"))
        assert list(form.terms) == ["a"]
        assert _terms(form) == {"a": {"binary_op": {"op": "+", "lhs": {"value": 1}, "rhs": {"value": 1}}}}
        assert _offset(form) == {"value": 0}

    def test_scaled_reads_of_one_sweep_sum(self, context):
        """``s * m11 + s * m21`` is one term whose scale is the sum of the two."""
        form = _form(sweep("a") * ext("vg.m11") + sweep("a") * ext("vg.m21"))
        assert list(form.terms) == ["a"]
        assert _terms(form) == {
            "a": {"binary_op": {"op": "+", "lhs": {"symbol": {"ext": "vg.m11"}}, "rhs": {"symbol": {"ext": "vg.m21"}}}}
        }

    def test_offsets_on_both_sides_are_summed(self, context):
        """``(s + o1) + (s + o2)`` keeps one term and one offset tree."""
        form = _form((sweep("a") + ext("vg.o1")) + (sweep("a") + ext("vg.o2")))
        assert list(form.terms) == ["a"]
        assert _offset(form) == {
            "binary_op": {"op": "+", "lhs": {"symbol": {"ext": "vg.o1"}}, "rhs": {"symbol": {"ext": "vg.o2"}}}
        }


class TestNotAffine:
    """The other direction: a :obj:`None` result, which means *evaluate this elementwise*."""

    def test_product_of_two_sweeps(self):
        """``s1 * s2``: legal, elementwise, and no linear combination describes it (§13 example H)."""
        assert affine_form((sweep("a") * sweep("b")).unwrap()) is None

    def test_scalar_over_a_sweep(self):
        """``1 / s``: division by a sweep is never affine, unlike division *of* one."""
        assert affine_form((1 / sweep("a")).unwrap()) is None

    def test_function_of_a_sweep(self):
        """``abs(s)``: every :class:`~eq1_pulse.models.expressions.CallExpr` is out."""
        assert affine_form(abs(sweep("a")).unwrap()) is None

    def test_variadic_function_of_a_sweep(self):
        """``max(s, 0)``: variadic calls are out for the same reason ``abs`` is."""
        assert affine_form(call_expr_("max", sweep("a"), 0).unwrap()) is None

    def test_remainder(self):
        """``s % 3``: the one arithmetic operator that is not affine."""
        assert affine_form((sweep("a") % 3).unwrap()) is None

    def test_comparison(self):
        """``s > 0``: a boolean sweep is rank-1 and decomposes into nothing."""
        assert affine_form((sweep("a") > 0).unwrap()) is None

    def test_a_non_affine_subtree_poisons_the_whole(self):
        """``s1 * s2 + s3``: recognisable at the top, and still :obj:`None`."""
        assert affine_form((sweep("a") * sweep("b") + sweep("c")).unwrap()) is None

    def test_sweep_dividing_a_recognisable_operand(self):
        """``s1 / s2``: the divisor is checked before the dividend is decomposed."""
        assert affine_form((sweep("a") / sweep("b")).unwrap()) is None


class TestNothingIsEvaluated:
    """Scales come back as trees, because a scale may have no value until invocation."""

    def test_a_scale_over_externals_survives_as_a_tree(self, context):
        """``s * (m11 + m21)``: the scale is the tree the author wrote, unevaluated."""
        form = _form(sweep("a") * (expr(ext("vg.m11")) + ext("vg.m21")))
        assert _terms(form) == {
            "a": {"binary_op": {"op": "+", "lhs": {"symbol": {"ext": "vg.m11"}}, "rhs": {"symbol": {"ext": "vg.m21"}}}}
        }

    def test_literal_arithmetic_is_not_folded(self):
        """``s * 2 * 3``: the scale is ``2 * 3``, not ``6``. A consumer that wants numbers evaluates."""
        form = _form(sweep("a") * 2 * 3)
        assert _terms(form) == {"a": {"binary_op": {"op": "*", "lhs": {"value": 2}, "rhs": {"value": 3}}}}


class TestWorkedExampleC:
    """Plan §13 example C: one supplied sweep, two affine transforms, three numbers per gate."""

    def test_both_virtual_gate_transforms_are_recognised(self, context):
        """Each transform decomposes to one term over ``detuning`` and an external offset."""
        transforms = [
            sweep("detuning") * ext("vg.m11") + ext("vg.o1"),
            sweep("detuning") * ext("vg.m21") + ext("vg.o2"),
        ]
        forms = [_form(transform) for transform in transforms]

        assert _terms(forms[0]) == {"detuning": {"symbol": {"ext": "vg.m11"}}}
        assert _offset(forms[0]) == {"symbol": {"ext": "vg.o1"}}
        assert _terms(forms[1]) == {"detuning": {"symbol": {"ext": "vg.m21"}}}
        assert _offset(forms[1]) == {"symbol": {"ext": "vg.o2"}}
