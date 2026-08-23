"""Tests for automatic conversion of Python range to Range model in builder."""

import pytest

from eq1_pulse.builder import build_sequence, for_, play, square_pulse, var_decl
from eq1_pulse.models import Iteration, Range


class TestRangeConversion:
    """Test automatic conversion of Python range to Range model."""

    def test_range_converts_to_range_model(self):
        """Test that Python range is converted to Range model."""
        with build_sequence() as seq:
            var_decl("i", "int")

            # Python range(0, 10, 2) excludes 10, so elements are [0, 2, 4, 6, 8]
            # Should convert to Range(start=0, stop=8, step=2) which includes 8
            with for_("i", range(0, 10, 2)):
                play("ch1", square_pulse(duration="100ns", amplitude="50mV"))

        iter_obj = seq.items[1]
        assert isinstance(iter_obj, Iteration)
        assert isinstance(iter_obj.items, Range)
        assert iter_obj.items.start == 0
        assert iter_obj.items.stop == 8
        assert iter_obj.items.step == 2
        assert len(iter_obj.items) == 5  # 0, 2, 4, 6, 8

    def test_range_with_negative_step(self):
        """Test range with negative step converts correctly."""
        with build_sequence() as seq:
            var_decl("i", "int")

            # range(10, 0, -2) gives [10, 8, 6, 4, 2]
            # Should convert to Range(start=10, stop=2, step=-2)
            with for_("i", range(10, 0, -2)):
                play("ch1", square_pulse(duration="100ns", amplitude="50mV"))

        iter_obj = seq.items[1]
        assert isinstance(iter_obj, Iteration)
        assert isinstance(iter_obj.items, Range)
        assert iter_obj.items.start == 10
        assert iter_obj.items.stop == 2
        assert iter_obj.items.step == -2
        assert len(iter_obj.items) == 5  # 10, 8, 6, 4, 2

    def test_empty_range_raises(self):
        """Test that an empty range (wrong step direction) is rejected."""
        with pytest.raises(ValueError, match="would never execute"):
            with build_sequence():
                var_decl("i", "int")

                # range(0, 10, -1) is empty (wrong step direction)
                with for_("i", range(0, 10, -1)):
                    play("ch1", square_pulse(duration="100ns", amplitude="50mV"))

    def test_single_element_range_converts_to_list(self):
        """Test that single-element range converts to list (which becomes numpy array in model)."""
        with build_sequence() as seq:
            var_decl("i", "int")

            # range(5, 6) gives [5]
            with for_("i", range(5, 6)):
                play("ch1", square_pulse(duration="100ns", amplitude="50mV"))

        iter_obj = seq.items[1]
        assert isinstance(iter_obj, Iteration)
        # Model converts lists to numpy arrays
        assert len(iter_obj.items) == 1

    def test_range_in_zipped_iteration(self):
        """Test that ranges in zipped iteration are converted."""
        with build_sequence() as seq:
            var_decl("i", "int")
            var_decl("j", "int")

            # Both ranges should be converted
            with for_(
                ["i", "j"],
                [
                    range(0, 10, 2),  # [0, 2, 4, 6, 8]
                    range(10, 0, -2),  # [10, 8, 6, 4, 2]
                ],
            ):
                play("ch1", square_pulse(duration="100ns", amplitude="50mV"))

        iter_obj = seq.items[2]
        assert isinstance(iter_obj, Iteration)
        assert isinstance(iter_obj.items, list)
        assert len(iter_obj.items) == 2

        # First range converted to Range
        assert isinstance(iter_obj.items[0], Range)
        assert iter_obj.items[0].start == 0
        assert iter_obj.items[0].stop == 8
        assert iter_obj.items[0].step == 2

        # Second range converted to Range
        assert isinstance(iter_obj.items[1], Range)
        assert iter_obj.items[1].start == 10
        assert iter_obj.items[1].stop == 2
        assert iter_obj.items[1].step == -2

    def test_range_with_step_one(self):
        """Test range with step=1 converts to Range."""
        with build_sequence() as seq:
            var_decl("i", "int")

            # range(0, 5) gives [0, 1, 2, 3, 4]
            # Should convert to Range(start=0, stop=4, step=1)
            with for_("i", range(0, 5)):
                play("ch1", square_pulse(duration="100ns", amplitude="50mV"))

        iter_obj = seq.items[1]
        assert isinstance(iter_obj, Iteration)
        assert isinstance(iter_obj.items, Range)
        assert iter_obj.items.start == 0
        assert iter_obj.items.stop == 4
        assert iter_obj.items.step == 1
        assert len(iter_obj.items) == 5

    def test_range_mixed_with_list_in_zipped_iteration(self):
        """Test mixing range with regular list in zipped iteration."""
        with build_sequence() as seq:
            var_decl("i", "int")
            var_decl("amp", "float")

            with for_(
                ["i", "amp"],
                [
                    range(0, 10, 2),  # Should convert to Range
                    [10, 20, 30, 40, 50],  # Plain list (becomes numpy array in model)
                ],
            ):
                play("ch1", square_pulse(duration="100ns", amplitude="50mV"))

        iter_obj = seq.items[2]
        assert isinstance(iter_obj, Iteration)
        assert isinstance(iter_obj.items, list)

        # First item converted to Range
        assert isinstance(iter_obj.items[0], Range)
        assert len(iter_obj.items[0]) == 5

        # Second item is stored (model converts list to numpy array internally)
        assert len(iter_obj.items[1]) == 5

    def test_range_serialization(self):
        """Test that converted Range serializes correctly."""
        with build_sequence() as seq:
            var_decl("i", "int")

            with for_("i", range(0, 10, 2)):
                play("ch1", square_pulse(duration="100ns", amplitude="50mV"))

        # Should serialize without errors
        json_data = seq.model_dump()
        assert set(json_data[1]) == {"for"}
        assert json_data[1]["for"]["items"]["start"] == 0
        assert json_data[1]["for"]["items"]["stop"] == 8
        assert json_data[1]["for"]["items"]["step"] == 2

    def test_non_range_iterables_unchanged(self):
        """Test that non-range iterables are not modified (though model may convert them internally)."""
        with build_sequence() as seq:
            var_decl("i", "int")

            # Plain list should not be converted to Range
            with for_("i", [0, 2, 4, 6, 8]):
                play("ch1", square_pulse(duration="100ns", amplitude="50mV"))

        iter_obj = seq.items[1]
        assert isinstance(iter_obj, Iteration)
        # Model may convert list to numpy array, but should not be Range
        assert not isinstance(iter_obj.items, Range)
        assert len(iter_obj.items) == 5
