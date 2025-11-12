"""Tests for schedule parameter validation in sequence contexts."""

import pytest

from eq1_pulse.builder import (
    build_schedule,
    build_sequence,
    discriminate,
    for_,
    full_integration,
    if_,
    measure,
    play,
    pulse_decl,
    record,
    repeat,
    set_frequency,
    set_phase,
    shift_frequency,
    shift_phase,
    square_pulse,
    store,
    var_decl,
    wait,
)


class TestScheduleParamsInSequenceValidation:
    """Test that schedule parameters raise errors when used in sequence contexts."""

    def test_play_with_schedule_params_in_sequence_raises_error(self):
        """Test that play() with schedule params in sequence context raises error."""
        with pytest.raises(RuntimeError, match=r"Schedule parameters.*not allowed in sequence context"):
            with build_sequence():
                play("ch1", square_pulse(duration="10us", amplitude="100mV"), ref_op="some_op")

    def test_play_with_multiple_schedule_params_in_sequence_raises_error(self):
        """Test that play() with multiple schedule params shows all in error."""
        with pytest.raises(RuntimeError, match=r"'ref_op'.*'ref_pt'.*not allowed in sequence context"):
            with build_sequence():
                play(
                    "ch1",
                    square_pulse(duration="10us", amplitude="100mV"),
                    ref_op="some_op",
                    ref_pt="end",
                )

    def test_wait_with_schedule_params_in_sequence_raises_error(self):
        """Test that wait() with schedule params in sequence context raises error."""
        with pytest.raises(RuntimeError, match=r"Schedule parameters.*not allowed in sequence context"):
            with build_sequence():
                wait("ch1", duration="5us", rel_time="10us")

    def test_set_frequency_with_schedule_params_in_sequence_raises_error(self):
        """Test that set_frequency() with schedule params in sequence context raises error."""
        with pytest.raises(RuntimeError, match=r"Schedule parameters.*not allowed in sequence context"):
            with build_sequence():
                set_frequency("ch1", "5GHz", op_name="freq_set")

    def test_shift_frequency_with_schedule_params_in_sequence_raises_error(self):
        """Test that shift_frequency() with schedule params in sequence context raises error."""
        with pytest.raises(RuntimeError, match=r"Schedule parameters.*not allowed in sequence context"):
            with build_sequence():
                shift_frequency("ch1", "100MHz", ref_op="some_op")

    def test_set_phase_with_schedule_params_in_sequence_raises_error(self):
        """Test that set_phase() with schedule params in sequence context raises error."""
        with pytest.raises(RuntimeError, match=r"Schedule parameters.*not allowed in sequence context"):
            with build_sequence():
                set_phase("ch1", "90deg", ref_pt="start")

    def test_shift_phase_with_schedule_params_in_sequence_raises_error(self):
        """Test that shift_phase() with schedule params in sequence context raises error."""
        with pytest.raises(RuntimeError, match=r"Schedule parameters.*not allowed in sequence context"):
            with build_sequence():
                shift_phase("ch1", "45deg", rel_time="5us")

    def test_record_with_schedule_params_in_sequence_raises_error(self):
        """Test that record() with schedule params in sequence context raises error."""
        with pytest.raises(RuntimeError, match=r"Schedule parameters.*not allowed in sequence context"):
            with build_sequence():
                var_decl("result", "complex", unit="mV")
                record(
                    "ch1",
                    "result",
                    duration="1us",
                    integration=full_integration(),
                    ref_op="some_op",
                )

    def test_discriminate_with_schedule_params_in_sequence_raises_error(self):
        """Test that discriminate() with schedule params in sequence context raises error."""
        with pytest.raises(RuntimeError, match=r"Schedule parameters.*not allowed in sequence context"):
            with build_sequence():
                var_decl("bit", "bool")
                var_decl("measurement", "complex", unit="mV")
                discriminate("bit", "measurement", threshold="0.5mV", op_name="discrim")

    def test_store_with_schedule_params_in_sequence_raises_error(self):
        """Test that store() with schedule params in sequence context raises error."""
        with pytest.raises(RuntimeError, match=r"Schedule parameters.*not allowed in sequence context"):
            with build_sequence():
                var_decl("measurement", "complex", unit="mV")
                store("result", "measurement", mode="last", ref_pt_new="end")

    def test_measure_with_schedule_params_in_sequence_raises_error(self):
        """Test that measure() with schedule params in sequence context raises error."""
        with pytest.raises(RuntimeError, match=r"Schedule parameters.*not allowed in sequence context"):
            with build_sequence():
                var_decl("result", "complex", unit="mV")
                measure(
                    "qubit",
                    result_var="result",
                    duration="1us",
                    amplitude="50mV",
                    integration=full_integration(),
                    ref_op="some_op",
                )

    def test_var_decl_with_schedule_params_in_sequence_raises_error(self):
        """Test that var_decl() with schedule params in sequence context raises error."""
        with pytest.raises(RuntimeError, match=r"Schedule parameters.*not allowed in sequence context"):
            with build_sequence():
                var_decl("data", "float", ref_op="some_op")

    def test_pulse_decl_with_schedule_params_in_sequence_raises_error(self):
        """Test that pulse_decl() with schedule params in sequence context raises error."""
        with pytest.raises(RuntimeError, match=r"Schedule parameters.*not allowed in sequence context"):
            with build_sequence():
                pulse_decl(
                    "my_pulse",
                    square_pulse(duration="100ns", amplitude="200mV"),
                    op_name="pulse1",
                )

    def test_repeat_with_schedule_params_in_sequence_raises_error(self):
        """Test that repeat() with schedule params in sequence context raises error."""
        with pytest.raises(RuntimeError, match=r"Schedule parameters.*not allowed in sequence context"):
            with build_sequence():
                with repeat(10, ref_op="some_op"):
                    play("qubit", square_pulse(duration="50ns", amplitude="100mV"))

    def test_for_with_schedule_params_in_sequence_raises_error(self):
        """Test that for_() with schedule params in sequence context raises error."""
        with pytest.raises(RuntimeError, match=r"Schedule parameters.*not allowed in sequence context"):
            with build_sequence():
                var_decl("i", "int")
                with for_("i", range(5), rel_time="10us"):
                    play("qubit", square_pulse(duration="50ns", amplitude="100mV"))

    def test_if_with_schedule_params_in_sequence_raises_error(self):
        """Test that if_() with schedule params in sequence context raises error."""
        with pytest.raises(RuntimeError, match=r"Schedule parameters.*not allowed in sequence context"):
            with build_sequence():
                var_decl("result", "bool")
                with if_("result", ref_pt="end"):
                    play("qubit", square_pulse(duration="50ns", amplitude="100mV"))

    def test_nested_sequence_with_schedule_params_raises_error(self):
        """Test that schedule params raise error in nested sequence contexts."""
        with pytest.raises(RuntimeError, match=r"Schedule parameters.*not allowed in sequence context"):
            with build_sequence():
                with repeat(5):
                    play("ch1", square_pulse(duration="10us", amplitude="100mV"), op_name="nested_play")

    def test_operations_without_schedule_params_work_in_sequence(self):
        """Test that operations without schedule params work fine in sequences."""
        with build_sequence() as seq:
            play("ch1", square_pulse(duration="10us", amplitude="100mV"))
            wait("ch1", duration="5us")
            set_frequency("ch1", "5GHz")
            var_decl("result", "complex", unit="mV")

        # Should succeed
        assert len(seq.items) == 4

    def test_operations_with_schedule_params_work_in_schedule(self):
        """Test that operations with schedule params work correctly in schedules."""
        with build_schedule() as sched:
            op1 = play("ch1", square_pulse(duration="10us", amplitude="100mV"))
            assert op1 is not None, "play() should return a token in schedule context"
            play("ch2", square_pulse(duration="5us", amplitude="50mV"), ref_op=op1, ref_pt="end")

        # Should succeed
        assert len(sched.items) == 2
        assert sched.items[1].ref_op == op1.name
