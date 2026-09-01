"""Tests for the sweep side of the builder (parameter sweeps plan, task T4).

Three groups. :class:`TestWorkedExamples` builds plan §13's examples A-H and compares each dump
against the wire form §15 fixes as normative -- example H in particular, a *product* of two
lock-step sweeps, which had no spelling at all before the 2026-08-26 revision and whose test is
what stops the restriction being reintroduced. :class:`TestIndexingAndLength` covers the two
accessors and the ``TypeError``-at-the-calling-line rule they exist to keep. :class:`TestChecks`
covers the three build-time checks: undeclared sweep, at most one consuming loop, and lock-step.
"""

import re

import pytest

from eq1_pulse.builder import (
    build_sequence,
    expr,
    ext,
    extern_decl,
    for_,
    full_integration,
    indices,
    len_,
    play,
    record,
    repeat,
    set_frequency,
    square_pulse,
    step_pulse,
    store,
    sub_sequence,
    sweep,
    sweep_decl,
    sweep_group,
    var,
    var_decl,
    wait,
)
from eq1_pulse.models.basic_types import LinSpace
from eq1_pulse.models.expressions import BinaryExpr, IndexExpr, LenExpr, SweepExpr


def _ops(sequence):
    """Dump a built sequence to the list of single-key operation objects §15 shows.

    :param sequence: The :class:`~eq1_pulse.models.sequence.OpSequence` to dump
    :return: The operations as plain data
    """
    return sequence.model_dump(mode="json")


class TestWorkedExamples:
    """Plan §13's examples A-H, each built and compared against §15's wire form."""

    def test_example_a_gate_scan(self):
        """A: values supplied per invocation, bound one item at a time."""
        with build_sequence() as seq:
            sweep_decl("vg", "float", unit="mV")
            extern_decl("gate.gain", "float")
            var_decl("iq", "complex", unit="mV")
            var_decl("v", "float", unit="mV")

            with for_("v", sweep("vg")):
                play("gate", step_pulse(duration="40ns", amplitude=expr(var("v")) * ext("gate.gain")))
                record("readout", "iq", duration="1us", integration=full_integration())
                store("scan", "iq", mode="average")

        ops = _ops(seq)
        assert ops[0] == {"sweep_decl": {"name": "vg", "dtype": "float", "unit": "mV"}}
        assert ops[-1]["for"]["items"] == {"sweep": "vg"}
        assert ops[-1]["for"]["body"][0]["play"]["pulse"]["amplitude"] == {
            "binary_op": {"op": "*", "lhs": {"symbol": {"var": "v"}}, "rhs": {"symbol": {"ext": "gate.gain"}}}
        }

    def test_example_b_rabi_indexed_by_position(self):
        """B: a default, iterated by position -- §15's ``{count: {len_op: ...}}`` loop."""
        with build_sequence() as seq:
            extern_decl("q0.f01", "float", unit="GHz")
            sweep_decl("t_pi", "float", unit="ns", default=LinSpace(start=0, stop=200, num=101))
            var_decl("i", "int")
            var_decl("iq", "complex", unit="mV")

            set_frequency("q0_drive", ext("q0.f01"))

            with for_("i", indices(len_(sweep("t_pi")))):
                play("q0_drive", square_pulse(duration=sweep("t_pi")[var("i")], amplitude="100mV"))
                record("q0_readout", "iq", duration="1us", integration=full_integration())
                store("rabi", "iq", mode="average")

        ops = _ops(seq)
        assert ops[1] == {
            "sweep_decl": {
                "name": "t_pi",
                "dtype": "float",
                "unit": "ns",
                "default": {"start": 0, "stop": 200, "num": 101},
            }
        }
        assert ops[-1]["for"]["items"] == {"count": {"len_op": {"operand": {"sweep": "t_pi"}}}}
        assert ops[-1]["for"]["body"][0]["play"]["pulse"]["duration"] == {
            "index_op": {"operand": {"sweep": "t_pi"}, "indices": [{"symbol": {"var": "i"}}]}
        }

    def test_example_c_virtual_gates(self):
        """C: one supplied sweep and two anonymous transforms of it, §15's complete experiment."""
        with build_sequence() as seq:
            sweep_decl("detuning", "float", unit="mV")
            for name in ("vg.m11", "vg.m21"):
                extern_decl(name, "float")
            for name in ("vg.o1", "vg.o2"):
                extern_decl(name, "float", unit="mV")
            var_decl("p1", "float", unit="mV")
            var_decl("p2", "float", unit="mV")

            with for_(
                ["p1", "p2"],
                [
                    sweep("detuning") * ext("vg.m11") + ext("vg.o1"),
                    sweep("detuning") * ext("vg.m21") + ext("vg.o2"),
                ],
            ):
                play("gate_1", step_pulse(duration="40ns", amplitude=var("p1")))
                play("gate_2", step_pulse(duration="40ns", amplitude=var("p2")))

        items = _ops(seq)[-1]["for"]["items"]
        assert items[0] == {
            "binary_op": {
                "op": "+",
                "lhs": {"binary_op": {"op": "*", "lhs": {"sweep": "detuning"}, "rhs": {"symbol": {"ext": "vg.m11"}}}},
                "rhs": {"symbol": {"ext": "vg.o1"}},
            }
        }
        # One sweep declaration and no transform declaration: a transform is a value, not a name.
        assert [key for op in _ops(seq) for key in op].count("sweep_decl") == 1

    def test_example_d_sweep_group(self):
        """D: independent sweeps in lock-step -- §15's group, members carrying their own units."""
        with build_sequence() as seq:
            with sweep_group():
                sweep_decl("i_amp", "float", unit="mV")
                sweep_decl("drive_freq", "float", unit="MHz")

            var_decl("a", "float", unit="mV")
            var_decl("f", "float", unit="MHz")
            with for_(["a", "f"], [sweep("i_amp"), sweep("drive_freq")]):
                set_frequency("q0_drive", var("f"))
                play("q0_drive", square_pulse(duration="40ns", amplitude=var("a")))

        ops = _ops(seq)
        assert ops[0] == {
            "sweep_group": {
                "sweeps": [
                    {"name": "i_amp", "dtype": "float", "unit": "mV"},
                    {"name": "drive_freq", "dtype": "float", "unit": "MHz"},
                ]
            }
        }
        assert ops[-1]["for"]["items"] == [{"sweep": "i_amp"}, {"sweep": "drive_freq"}]

    def test_example_e_outer_and_inner(self):
        """E: an unconsumed sweep alongside a consumed one; both are ordinary declarations."""
        with build_sequence() as seq:
            sweep_decl("b_field", "float", unit="mT")
            sweep_decl("tau", "float", unit="ns", default=LinSpace(start=0, stop=5000, num=51))
            var_decl("t", "float", unit="ns")

            with for_("t", sweep("tau")):
                wait("q0_drive", duration=var("t"))

        ops = _ops(seq)
        assert ops[0] == {"sweep_decl": {"name": "b_field", "dtype": "float", "unit": "mT"}}
        assert ops[-1]["for"]["items"] == {"sweep": "tau"}

    def test_example_f_repeating_items(self):
        """F: a list default is the JSON array itself -- a list of items, not an axis."""
        with build_sequence() as seq:
            sweep_decl("amp_seq", "float", unit="mV", default=[100, 0, 100, 50, 100, 25])
            var_decl("a", "float", unit="mV")

            with for_("a", sweep("amp_seq")):
                play("q0_drive", square_pulse(duration="40ns", amplitude=var("a")))

        assert _ops(seq)[0] == {
            "sweep_decl": {
                "name": "amp_seq",
                "dtype": "float",
                "unit": "mV",
                "default": [100, 0, 100, 50, 100, 25],
            }
        }

    def test_example_g_sum_and_difference(self):
        """G: sum and difference of two grouped sweeps, computed before the loop."""
        with build_sequence() as seq:
            with sweep_group():
                sweep_decl("d1", "float", unit="mV")
                sweep_decl("d2", "float", unit="mV")

            var_decl("c", "float", unit="mV")
            var_decl("e", "float", unit="mV")
            with for_(["c", "e"], [sweep("d1") + sweep("d2"), sweep("d1") - sweep("d2")]):
                play("gate_c", step_pulse(duration="40ns", amplitude=var("c")))
                play("gate_e", step_pulse(duration="40ns", amplitude=var("e")))

        assert _ops(seq)[-1]["for"]["items"] == [
            {"binary_op": {"op": "+", "lhs": {"sweep": "d1"}, "rhs": {"sweep": "d2"}}},
            {"binary_op": {"op": "-", "lhs": {"sweep": "d1"}, "rhs": {"sweep": "d2"}}},
        ]

    def test_example_h_product_of_two_lock_step_sweeps(self):
        """H: what the revision added.

        ``sweep("amp") * sweep("scale")`` is an ordinary :class:`BinaryExpr`. Under the first
        design ``Sweep.__mul__`` refused a ``Sweep`` operand and this had no spelling at all, so a
        test asserting that it *works* is what stops the restriction being reintroduced.
        """
        with build_sequence() as seq:
            with sweep_group():
                sweep_decl("amp", "float", unit="mV")
                sweep_decl("scale", "float")

            var_decl("a", "float", unit="mV")
            with for_("a", sweep("amp") * sweep("scale")):
                play("q0_drive", square_pulse(duration="40ns", amplitude=var("a")))

        assert _ops(seq)[-1]["for"]["items"] == {
            "binary_op": {"op": "*", "lhs": {"sweep": "amp"}, "rhs": {"sweep": "scale"}}
        }

    def test_example_h_builds_a_binary_expr_outside_a_loop(self):
        """The same product, read as a tree: no fold, no curated operator list."""
        node = (sweep("amp") * sweep("scale")).unwrap()
        assert isinstance(node, BinaryExpr)
        assert node.binary_op == "*"
        assert isinstance(node.lhs, SweepExpr)
        assert isinstance(node.rhs, SweepExpr)


class TestSweepReference:
    """``sweep()`` itself, and how a bare reference and a transform reach the wire."""

    def test_sweep_returns_an_expr_wrapping_a_sweep_expr(self):
        node = sweep("vg").unwrap()
        assert isinstance(node, SweepExpr)
        assert node.sweep == "vg"

    def test_a_bare_reference_dumps_as_the_sole_key_object(self):
        with build_sequence() as seq:
            sweep_decl("vg", "float", unit="mV")
            var_decl("v", "float", unit="mV")
            with for_("v", sweep("vg")):
                pass

        assert _ops(seq)[-1]["for"]["items"] == {"sweep": "vg"}

    def test_an_inline_transform_dumps_as_the_expression_tree(self):
        with build_sequence() as seq:
            sweep_decl("vg", "float", unit="mV")
            extern_decl("gate.gain", "float")
            var_decl("p", "float", unit="mV")
            with for_("p", sweep("vg") * ext("gate.gain")):
                pass

        assert _ops(seq)[-1]["for"]["items"] == {
            "binary_op": {"op": "*", "lhs": {"sweep": "vg"}, "rhs": {"symbol": {"ext": "gate.gain"}}}
        }

    def test_a_bare_expression_node_is_accepted_as_items(self):
        with build_sequence() as seq:
            sweep_decl("vg", "float", unit="mV")
            var_decl("v", "float", unit="mV")
            with for_("v", sweep("vg").unwrap()):
                pass

        assert _ops(seq)[-1]["for"]["items"] == {"sweep": "vg"}


class TestDeclarations:
    """``sweep_decl()`` and ``sweep_group()``, and there is no third declaration function."""

    def test_a_group_member_is_declared_in_the_surrounding_scope(self):
        """A group is one operation, not a scope: its members outlive the ``with`` block."""
        with build_sequence() as seq:
            with sweep_group():
                sweep_decl("a", "float")
                sweep_decl("b", "float")

            var_decl("x", "float")
            with for_("x", sweep("a") + sweep("b")):
                pass

        assert len(_ops(seq)) == 3

    def test_a_group_of_one_raises(self):
        with build_sequence():
            with pytest.raises(RuntimeError, match="at least two sweep_decl"):
                with sweep_group():
                    sweep_decl("only", "float")

    def test_a_nested_group_raises(self):
        with build_sequence():
            with pytest.raises(RuntimeError, match="cannot be nested"):
                with sweep_group():
                    sweep_decl("a", "float")
                    with sweep_group():
                        sweep_decl("b", "float")

    def test_a_failed_group_body_emits_nothing(self):
        with build_sequence() as seq:
            with pytest.raises(ValueError, match="boom"):
                with sweep_group():
                    sweep_decl("a", "float")
                    raise ValueError("boom")

        assert _ops(seq) == []

    def test_a_failed_group_leaves_its_members_undeclared(self):
        """A group that raises emits nothing, so nothing it declared may stay in scope.

        Otherwise a later ``sweep("a")`` validates against a sweep the program does not declare --
        a document referencing a name that is nowhere in it.
        """
        with build_sequence():
            with pytest.raises(ValueError, match="boom"):
                with sweep_group():
                    sweep_decl("a", "float")
                    sweep_decl("b", "float")
                    raise ValueError("boom")

            var_decl("v", "float")
            with pytest.raises(RuntimeError, match="Sweep 'a' has not been declared"):
                with for_("v", sweep("a")):
                    pass

            # The name is free again, so the recovery an author would write actually works.
            sweep_decl("a", "float")

    def test_a_group_of_one_leaves_its_member_undeclared(self):
        """The same rollback for the other way a group fails: too few members to be a group."""
        with build_sequence() as seq:
            with pytest.raises(RuntimeError, match="at least two sweep_decl"):
                with sweep_group():
                    sweep_decl("only", "float")

            var_decl("v", "float")
            with pytest.raises(RuntimeError, match="Sweep 'only' has not been declared"):
                with for_("v", sweep("only")):
                    pass

        assert [next(iter(op)) for op in _ops(seq)] == ["var_decl"]

    def test_redeclaring_a_sweep_in_one_context_raises(self):
        with build_sequence():
            sweep_decl("vg", "float")
            with pytest.raises(RuntimeError, match="Sweep 'vg' is already declared"):
                sweep_decl("vg", "float")

    def test_a_sweep_and_a_variable_may_share_a_name(self):
        """Sweeps have their own namespace, as external symbols do."""
        with build_sequence() as seq:
            sweep_decl("x", "float")
            var_decl("x", "float")

        assert len(_ops(seq)) == 2

    def test_a_sweep_is_scoped_to_its_context(self):
        with build_sequence():
            with sub_sequence():
                sweep_decl("inner", "float")
            var_decl("v", "float")
            with pytest.raises(RuntimeError, match="Sweep 'inner' has not been declared"):
                with for_("v", sweep("inner")):
                    pass

    def test_sweep_decl_outside_a_context_raises(self):
        with pytest.raises(RuntimeError, match="No active building context for sweep_decl"):
            sweep_decl("vg", "float")

    def test_sweep_group_outside_a_context_raises(self):
        with pytest.raises(RuntimeError, match="No active building context for sweep_group"):
            with sweep_group():
                pass


class TestIndexingAndLength:
    """``Expr.__getitem__``, ``len_()``, and the ``__len__`` that is deliberately not bound."""

    def test_indexing_builds_an_index_expr(self):
        node = sweep("vg")[0].unwrap()
        assert isinstance(node, IndexExpr)
        assert len(node.indices) == 1

    def test_a_tuple_index_becomes_several_indices(self):
        node = sweep("grid")[0, 1].unwrap()
        assert isinstance(node, IndexExpr)
        assert len(node.indices) == 2

    def test_len_builds_a_len_expr(self):
        node = len_(sweep("vg")).unwrap()
        assert isinstance(node, LenExpr)
        assert isinstance(node.operand, SweepExpr)

    def test_len_of_a_transform_is_accepted(self):
        """§15: ``operand`` is a ``SweepSource``, so any sweep-valued tree fits."""
        node = len_(sweep("vg") * 2).unwrap()
        assert isinstance(node, LenExpr)
        assert isinstance(node.operand, BinaryExpr)

    def test_builtin_len_is_not_bound(self):
        """Plan §9 Q4: ``len()`` runs ``__index__`` on the result, which a tree can never satisfy."""
        with pytest.raises(TypeError, match="has no len"):
            len(sweep("a"))  # type: ignore[arg-type]  # the point of the test: it is not Sized

    def test_iteration_is_refused(self):
        """``__getitem__`` without ``__iter__`` would make ``list(sweep("a"))`` run forever.

        Python falls back to the legacy sequence protocol -- ``self[0]``, ``self[1]``, ... until an
        ``IndexError`` that indexing an expression never raises. Asserted through :func:`iter`
        rather than through ``list()`` or a ``for``, which are the same call and would hang the
        suite rather than fail it if this regressed.
        """
        with pytest.raises(TypeError, match="cannot be iterated"):
            iter(sweep("a"))  # type: ignore[call-overload]  # the point of the test: it is not Iterable

    def test_a_symbolic_index_count_is_not_compared_against_a_length(self):
        """``indices(len_(s))`` has no length until invocation, so a zipped sibling's is unopposed."""
        with build_sequence() as seq:
            sweep_decl("vg", "float")
            var_decl("i", "int")
            var_decl("j", "int")
            with for_(["i", "j"], [indices(len_(sweep("vg"))), range(3)]):
                pass

        assert _ops(seq)[-1]["for"]["items"][1] == {"start": 0, "stop": 2, "step": 1}  # range(3), stop inclusive

    def test_indexing_a_scalar_expression_raises_type_error(self):
        """A ``TypeError`` at the calling line, not a ``ValidationError`` two frames later."""
        with build_sequence():
            var_decl("i", "int")
            with pytest.raises(TypeError, match="reads no sweep"):
                expr(var("i"))[0]

    def test_len_of_a_scalar_expression_raises_type_error(self):
        with build_sequence():
            var_decl("i", "int")
            with pytest.raises(TypeError, match="reads no sweep"):
                len_(expr(var("i")))

    def test_an_indexed_sweep_is_legal_at_a_value_site(self):
        """§5's rank stop: an ``index_op`` is rank-0 however deep the sweep under it sits."""
        with build_sequence() as seq:
            sweep_decl("vg", "float", unit="mV")
            extern_decl("gate.gain", "float")
            var_decl("i", "int")
            with for_("i", indices(len_(sweep("vg")))):
                play("gate", step_pulse(duration="40ns", amplitude=sweep("vg")[var("i")] * ext("gate.gain")))

        assert _ops(seq)[-1]["for"]["body"][0]["play"]["pulse"]["amplitude"] == {
            "binary_op": {
                "op": "*",
                "lhs": {"index_op": {"operand": {"sweep": "vg"}, "indices": [{"symbol": {"var": "i"}}]}},
                "rhs": {"symbol": {"ext": "gate.gain"}},
            }
        }

    def test_repeat_accepts_a_length(self):
        """``Repetition.count`` is already ``int | ValueRef``, so ``LenExpr`` alone suffices."""
        with build_sequence() as seq:
            sweep_decl("vg", "float")
            with repeat(len_(sweep("vg"))):
                pass

        assert _ops(seq)[-1] == {"repeat": {"count": {"len_op": {"operand": {"sweep": "vg"}}}, "body": []}}


class TestChecks:
    """The three build-time checks. All local; none is a traversal of the program."""

    def test_an_undeclared_sweep_raises(self):
        with build_sequence():
            var_decl("v", "float")
            with pytest.raises(RuntimeError, match="Sweep 'nope' has not been declared"):
                with for_("v", sweep("nope")):
                    pass

    def test_an_undeclared_sweep_under_an_index_raises(self):
        """The declaration check descends past ``index_op``, where the rank walk stops."""
        with build_sequence():
            var_decl("i", "int")
            with pytest.raises(RuntimeError, match="Sweep 'nope' has not been declared"):
                play("gate", step_pulse(duration="40ns", amplitude=sweep("nope")[var("i")]))

    def test_an_undeclared_sweep_deep_in_a_value_expression_raises(self):
        with build_sequence():
            sweep_decl("vg", "float")
            var_decl("i", "int")
            with pytest.raises(RuntimeError, match="Sweep 'other' has not been declared"):
                wait("ch1", duration=sweep("vg")[var("i")] + sweep("other")[var("i")])

    def test_a_second_consuming_loop_raises_naming_the_first(self):
        with build_sequence():
            sweep_decl("vg", "float")
            var_decl("a", "float")
            var_decl("b", "float")
            with for_("a", sweep("vg")):
                with pytest.raises(RuntimeError, match=re.escape("already iterated by for_('a')")):
                    with for_("b", sweep("vg")):
                        pass

    def test_a_transform_consumes_its_bases_too(self):
        """§7: a loop consumes every sweep its items read, transform or bare reference alike."""
        with build_sequence():
            sweep_decl("vg", "float")
            extern_decl("gain", "float")
            var_decl("a", "float")
            var_decl("b", "float")
            with for_("a", sweep("vg")):
                pass
            with pytest.raises(RuntimeError, match=re.escape("already iterated by for_('a')")):
                with for_("b", sweep("vg") * ext("gain")):
                    pass

    def test_a_zipped_loop_names_all_its_variables_in_the_message(self):
        with build_sequence():
            with sweep_group():
                sweep_decl("d1", "float")
                sweep_decl("d2", "float")
            var_decl("a", "float")
            var_decl("f", "float")
            var_decl("z", "float")
            with for_(["a", "f"], [sweep("d1"), sweep("d2")]):
                pass
            with pytest.raises(RuntimeError, match=re.escape("already iterated by for_(['a', 'f'])")):
                with for_("z", sweep("d1")):
                    pass

    def test_index_iteration_consumes_nothing(self):
        """``indices(len_(s))`` reads no sweep through the ``len_op``, so it leaves ``s`` free."""
        with build_sequence():
            sweep_decl("vg", "float")
            var_decl("i", "int")
            var_decl("v", "float")
            with for_("i", indices(len_(sweep("vg")))):
                pass
            with for_("v", sweep("vg")):
                pass

    @pytest.mark.parametrize("combine", [lambda a, b: a + b, lambda a, b: a * b])
    def test_cross_level_sweeps_in_one_expression_raise(self, combine):
        """Example G's mirror: the same two sweeps declared separately rather than grouped."""
        with build_sequence():
            sweep_decl("d1", "float", unit="mV")
            sweep_decl("d2", "float", unit="mV")
            var_decl("c", "float", unit="mV")
            with pytest.raises(RuntimeError, match="do not advance together"):
                with for_("c", combine(sweep("d1"), sweep("d2"))):
                    pass

    @pytest.mark.parametrize("combine", [lambda a, b: a + b, lambda a, b: a * b])
    def test_sweeps_from_different_nesting_levels_raise(self, combine):
        """The genuinely cross-level case: one declared inside the other's loop body."""
        with build_sequence():
            sweep_decl("outer", "float")
            var_decl("c", "float")
            with repeat(2):
                sweep_decl("inner", "float")
                with pytest.raises(RuntimeError, match="do not advance together"):
                    with for_("c", combine(sweep("outer"), sweep("inner"))):
                        pass

    def test_the_lock_step_message_names_both_sweeps_and_the_alternative(self):
        with build_sequence():
            sweep_decl("d1", "float")
            sweep_decl("d2", "float")
            var_decl("c", "float")
            with pytest.raises(RuntimeError) as caught:
                with for_("c", sweep("d1") + sweep("d2")):
                    pass

        message = str(caught.value)
        assert "'d1'" in message
        assert "'d2'" in message
        assert "sweep_group()" in message
        assert "loop variables in the body" in message

    def test_grouped_sweeps_in_one_expression_are_accepted(self):
        with build_sequence():
            with sweep_group():
                sweep_decl("d1", "float")
                sweep_decl("d2", "float")
            var_decl("c", "float")
            with for_("c", sweep("d1") + sweep("d2")):
                pass

    def test_the_same_sweep_twice_in_one_expression_is_accepted(self):
        with build_sequence():
            sweep_decl("vg", "float")
            var_decl("c", "float")
            with for_("c", sweep("vg") + sweep("vg")):
                pass

    def test_two_indexed_sweeps_may_be_combined_whatever_their_levels(self):
        """Each ``index_op`` yields a scalar, so the enclosing tree reads no sweep at all."""
        with build_sequence() as seq:
            sweep_decl("d1", "float")
            sweep_decl("d2", "float")
            var_decl("i", "int")
            with for_("i", indices(3)):
                play("gate", step_pulse(duration="40ns", amplitude=sweep("d1")[var("i")] + sweep("d2")[var("i")]))

        assert _ops(seq)[-1]["for"]["body"][0]["play"]["pulse"]["amplitude"]["binary_op"]["op"] == "+"

    def test_lock_step_is_checked_inside_an_index_operand(self):
        """The operand of an ``index_op`` is a lock-step scope of its own."""
        with build_sequence():
            sweep_decl("d1", "float")
            sweep_decl("d2", "float")
            var_decl("i", "int")
            with pytest.raises(RuntimeError, match="do not advance together"):
                play("gate", step_pulse(duration="40ns", amplitude=(sweep("d1") + sweep("d2"))[var("i")]))

    def test_zipping_independent_sweeps_raises(self):
        """§7: a zipped ``for_`` is one level of nesting, so its items must advance together.

        The same two sweeps in one expression are already rejected; zipped they are the same
        mistake, and the models cannot catch it -- neither item has a length until invocation.
        """
        with build_sequence():
            sweep_decl("a", "float")
            sweep_decl("b", "float")
            var_decl("x", "float")
            var_decl("y", "float")
            with pytest.raises(RuntimeError, match="zipped by one for_") as caught:
                with for_(["x", "y"], [sweep("a"), sweep("b")]):
                    pass

        message = str(caught.value)
        assert "'a'" in message
        assert "'b'" in message
        assert "sweep_group()" in message
        assert "nest the two loops" in message

    def test_zipping_grouped_sweeps_is_accepted(self):
        """Example D's shape: what a ``sweep_group()`` is for."""
        with build_sequence():
            with sweep_group():
                sweep_decl("i_amp", "float", unit="mV")
                sweep_decl("drive_freq", "float", unit="MHz")
            var_decl("a", "float", unit="mV")
            var_decl("f", "float", unit="MHz")
            with for_(["a", "f"], [sweep("i_amp"), sweep("drive_freq")]):
                pass

    def test_zipping_a_base_with_a_transform_of_it_is_accepted(self):
        """Example C's shape: one base and sweeps derived from it are lock-step by construction."""
        with build_sequence():
            sweep_decl("detuning", "float", unit="mV")
            var_decl("p1", "float", unit="mV")
            var_decl("p2", "float", unit="mV")
            with for_(["p1", "p2"], [sweep("detuning") * 2, sweep("detuning") * 3]):
                pass

    def test_zipping_a_sweep_with_a_plain_iterable_is_accepted(self):
        """Only sweeps take their length from a declaration; a literal iterable states its own."""
        with build_sequence():
            sweep_decl("a", "float")
            var_decl("x", "float")
            var_decl("y", "int")
            with for_(["x", "y"], [sweep("a"), range(3)]):
                pass


class TestExports:
    """The five new names reach the public builder namespace."""

    def test_builder_all_is_sorted_and_complete(self):
        import eq1_pulse.builder as builder

        assert list(builder.__all__) == sorted(builder.__all__)
        assert {"indices", "len_", "sweep", "sweep_decl", "sweep_group"} <= set(builder.__all__)

    def test_core_all_is_sorted_and_complete(self):
        import eq1_pulse.builder.core as core

        assert list(core.__all__) == sorted(core.__all__)
        assert {"indices", "len_", "sweep", "sweep_decl", "sweep_group"} <= set(core.__all__)

    def test_sweeps_module_does_not_import_core(self):
        """The one-way rule ``_state``/``_factories``/``_expressions`` already establish."""
        import ast
        from pathlib import Path

        source = Path(__file__).resolve().parents[2] / "src" / "eq1_pulse" / "builder" / "_sweeps.py"
        tree = ast.parse(source.read_text(), filename=str(source))
        imported = [
            f"{'.' * node.level}{node.module or ''}" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        ]
        assert not any(module.endswith("core") for module in imported)
