"""Tests for zipped iteration support in the builder interface."""

import pytest

from eq1_pulse.builder import (
    build_sequence,
    for_,
    indices,
    play,
    square_pulse,
    var,
    var_decl,
)
from eq1_pulse.models import Iteration, LinSpace, Range


class TestZippedIterationBasics:
    """Basic tests for zipped iteration functionality."""

    def test_zipped_iteration_two_variables(self):
        """Test zipped iteration with two variables creates proper iteration."""
        with build_sequence() as seq:
            var_decl("i", "int")
            var_decl("j", "int")

            with for_(["i", "j"], [[1, 2, 3], [10, 20, 30]]):
                play("ch1", square_pulse(duration="10ns", amplitude="100mV"))

        # Should have 2 var_decls + for_
        assert len(seq.items) == 3
        iter_obj = seq.items[2]
        assert isinstance(iter_obj, Iteration)

    def test_zipped_iteration_three_variables(self):
        """Test zipped iteration with three variables of same length."""
        with build_sequence() as seq:
            var_decl("freq", "float", unit="MHz")
            var_decl("amp", "float", unit="mV")
            var_decl("phase", "float", unit="deg")

            # All iterables must have same length
            with for_(
                ["freq", "amp", "phase"],
                [
                    range(4000, 4005),  # 5 elements
                    [10, 20, 30, 40, 50],  # 5 elements
                    [0, 90, 180, 270, 0],  # 5 elements
                ],
            ):
                play("ch1", square_pulse(duration="100ns", amplitude="50mV"))

        # Should have 3 var_decls + for_
        assert len(seq.items) == 4
        iter_obj = seq.items[3]
        assert isinstance(iter_obj, Iteration)

    def test_zipped_iteration_with_range_and_lists(self):
        """Test zipped iteration with range and list of same length."""
        with build_sequence() as seq:
            var_decl("i", "int")
            var_decl("label", "int")

            with for_(["i", "label"], [[0, 1, 2, 3, 4], [1, 2, 3, 4, 5]]):
                play("ch1", square_pulse(duration="100ns", amplitude=var("label")))

        iter_obj = seq.items[2]
        assert isinstance(iter_obj, Iteration)

    def test_zipped_iteration_large_variables(self):
        """Test zipped iteration with many variables."""
        with build_sequence() as seq:
            for i in range(5):
                var_decl(f"v{i}", "int")

            with for_([f"v{i}" for i in range(5)], [range(10) for _ in range(5)]):
                play("ch1", square_pulse(duration="100ns", amplitude="50mV"))

        iter_obj = seq.items[5]
        assert isinstance(iter_obj, Iteration)

    def test_single_iteration_still_works(self):
        """Test that single variable iteration still works."""
        with build_sequence() as seq:
            var_decl("i", "int", unit="MHz")

            with for_("i", range(0, 100, 10)):
                play("ch1", square_pulse(duration="100ns", amplitude="50mV"))

        # Should have var_decl + for_
        assert len(seq.items) == 2
        iter_obj = seq.items[1]
        assert isinstance(iter_obj, Iteration)

    def test_zipped_iteration_operations_in_body(self):
        """Test operations inside zipped iteration body."""
        with build_sequence() as seq:
            var_decl("freq", "float", unit="MHz")
            var_decl("amp", "float", unit="mV")

            with for_(["freq", "amp"], [range(5), range(5)]):
                play("ch1", square_pulse(duration="100ns", amplitude=var("amp")))
                play("ch2", square_pulse(duration="50ns", amplitude="25mV"))

        iter_obj = seq.items[2]
        assert isinstance(iter_obj, Iteration)
        # Body should have 2 play operations
        assert len(iter_obj.body.items) == 2

    def test_zipped_iteration_undeclared_variable_raises(self):
        """Test that using undeclared variable raises error."""
        with pytest.raises(RuntimeError, match="Variable 'undeclared' has not been declared"):
            with build_sequence():
                with for_(["undeclared", "j"], [range(5), range(5)]):
                    play("ch1", square_pulse(duration="100ns", amplitude="50mV"))

    def test_zipped_iteration_json_serialization(self):
        """Test JSON serialization of zipped iteration."""
        with build_sequence() as seq:
            var_decl("i", "int")
            var_decl("j", "int")

            with for_(["i", "j"], [[0, 1, 2], [10, 20, 30]]):
                play("ch1", square_pulse(duration="100ns", amplitude="50mV"))

        # Serialize to JSON and verify content
        json_str = seq.model_dump_json()
        assert '"for"' in json_str
        # Verify variables appear in JSON
        assert "i" in json_str or "j" in json_str

    def test_zipped_iteration_with_linspace(self):
        """Test zipped iteration with LinSpace objects."""
        with build_sequence() as seq:
            var_decl("x", "float")
            var_decl("y", "float")

            with for_(["x", "y"], [LinSpace(start=0, stop=1, num=5), LinSpace(start=10, stop=100, num=5)]):
                play("ch1", square_pulse(duration="100ns", amplitude="50mV"))

        iter_obj = seq.items[2]
        assert isinstance(iter_obj, Iteration)

    def test_zipped_iteration_with_range_and_linspace(self):
        """Test zipped iteration with Range and LinSpace objects."""
        with build_sequence() as seq:
            var_decl("i", "int")
            var_decl("amp", "float")

            with for_(
                ["i", "amp"],
                [
                    Range(start=0, stop=8, step=2),  # 5 elements: 0, 2, 4, 6, 8 (stop point included)
                    LinSpace(start=10, stop=100, num=5),  # 5 elements
                ],
            ):
                play("ch1", square_pulse(duration="100ns", amplitude=var("amp")))

        iter_obj = seq.items[2]
        assert isinstance(iter_obj, Iteration)

    def test_mismatched_lengths_raises(self):
        """Test that mismatched variable/iterable lengths raise error."""
        with pytest.raises(ValueError, match="one iterable per variable"):
            with build_sequence():
                var_decl("i", "int")
                var_decl("j", "int")

                # 2 variables but 3 iterables
                with for_(["i", "j"], [range(5), range(5), range(5)]):
                    play("ch1", square_pulse(duration="100ns", amplitude="50mV"))

    def test_literal_indices_count_is_compared_against_the_other_lengths(self):
        """``indices(5)`` is not ``Sized``, but a literal count is a length like any other."""
        with pytest.raises(ValueError, match="same length"):
            with build_sequence():
                var_decl("i", "int")
                var_decl("j", "int")

                with for_(["i", "j"], [indices(5), range(3)]):
                    play("ch1", square_pulse(duration="100ns", amplitude="50mV"))

    def test_matching_indices_count_is_accepted(self):
        """The same comparison the other way: agreeing lengths build."""
        with build_sequence() as seq:
            var_decl("i", "int")
            var_decl("j", "int")

            with for_(["i", "j"], [indices(3), range(3)]):
                play("ch1", square_pulse(duration="100ns", amplitude="50mV"))

        iter_obj = seq.items[2]
        assert isinstance(iter_obj, Iteration)

    def test_single_iterable_is_broadcast_over_variables(self):
        """Test that one iterable given for several variables is used for each of them."""
        with build_sequence() as seq:
            var_decl("i", "int")
            var_decl("j", "int")

            with for_(["i", "j"], range(0, 10, 2)):
                play("ch1", square_pulse(duration="100ns", amplitude="50mV"))

        iter_obj = seq.items[2]
        assert isinstance(iter_obj, Iteration)
        assert isinstance(iter_obj.var, list)
        assert isinstance(iter_obj.items, list)
        assert len(iter_obj.var) == 2
        assert len(iter_obj.items) == 2
        assert iter_obj.items[0] == iter_obj.items[1]

    def test_zipped_iteration_in_nested_context(self):
        """Test zipped iteration inside repeat."""
        from eq1_pulse.builder import repeat

        with build_sequence() as seq:
            var_decl("i", "int")
            var_decl("j", "int")

            with repeat(2):
                with for_(["i", "j"], [range(3), range(3)]):
                    play("ch1", square_pulse(duration="100ns", amplitude="50mV"))

        # Should have var_decl + var_decl + repeat
        assert len(seq.items) == 3

    def test_zipped_iteration_model_dump(self):
        """Test model_dump preserves zipped iteration structure."""
        with build_sequence() as seq:
            var_decl("i", "int")
            var_decl("j", "int")

            with for_(["i", "j"], [[0, 1, 2], [10, 20, 30]]):
                play("ch1", square_pulse(duration="100ns", amplitude="50mV"))

        dumped = seq.model_dump()
        # Should have var_decl, var_decl, for_
        assert len(dumped) == 3
        assert set(dumped[2]) == {"for"}
