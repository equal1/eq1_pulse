"""Tests for the builder interface."""

import pytest

from eq1_pulse.builder import (
    add_block,
    arbitrary_pulse,
    barrier,
    build_schedule,
    build_sequence,
    channel,
    discriminate,
    external_pulse,
    for_,
    if_,
    measure,
    measure_and_discriminate,
    measure_and_discriminate_and_if_,
    play,
    pulse_ref,
    record,
    repeat,
    set_frequency,
    set_phase,
    shift_frequency,
    shift_phase,
    sine_pulse,
    square_pulse,
    store,
    sub_schedule,
    sub_sequence,
    var,
    var_decl,
    wait,
)
from eq1_pulse.models import (
    Barrier,
    Conditional,
    Discriminate,
    Iteration,
    OpSequence,
    Play,
    Record,
    RefPt,
    Repetition,
    Schedule,
    SetFrequency,
    SetPhase,
    ShiftFrequency,
    ShiftPhase,
    SquarePulse,
    Store,
    VariableDecl,
)


class TestBuildSequence:
    """Tests for build_sequence context manager."""

    def test_empty_sequence(self):
        """Test creating an empty sequence."""
        with build_sequence() as seq:
            pass
        assert isinstance(seq, OpSequence)
        assert len(seq.items) == 0

    def test_sequence_with_operations(self):
        """Test sequence with basic operations."""
        with build_sequence() as seq:
            play("ch1", square_pulse(duration="10us", amplitude="100mV"))
            wait("ch1", duration="5us")

        assert len(seq.items) == 2
        assert isinstance(seq.items[0], Play)

    def test_nested_sequences(self):
        """Test that sequences can be nested using sub_sequence."""
        with build_sequence() as outer:
            play("ch1", square_pulse(duration="10us", amplitude="100mV"))

            with sub_sequence():
                play("ch2", square_pulse(duration="5us", amplitude="50mV"))
                wait("ch2", duration="2us")

            play("ch3", square_pulse(duration="3us", amplitude="75mV"))

        # Outer sequence should contain: play + nested sequence + play
        assert len(outer.items) == 3
        assert isinstance(outer.items[0], Play)
        assert isinstance(outer.items[1], OpSequence)
        assert isinstance(outer.items[2], Play)

        # Inner sequence should have 2 items
        assert len(outer.items[1].items) == 2

    def test_sub_sequence_in_control_flow(self):
        """Test sub_sequence works inside control flow constructs."""
        with build_sequence() as seq:
            var_decl("i", "int")

            with for_("i", range(3)):
                # Nested sub-sequence inside for loop
                with sub_sequence():
                    play("qubit", square_pulse(duration="20ns", amplitude="100mV"))
                    wait("qubit", duration="10ns")

                play("qubit", square_pulse(duration="5ns", amplitude="50mV"))

        # seq should contain: var_decl + for_loop
        assert len(seq.items) == 2
        assert isinstance(seq.items[0], VariableDecl)
        assert isinstance(seq.items[1], Iteration)

        # for_loop body should contain: sub_sequence + play
        for_body = seq.items[1].body
        assert len(for_body.items) == 2
        assert isinstance(for_body.items[0], OpSequence)  # sub-sequence
        assert isinstance(for_body.items[1], Play)

        # sub-sequence should have 2 items
        assert len(for_body.items[0].items) == 2

    def test_sub_sequence_outside_sequence_raises_error(self):
        """Test that sub_sequence outside a sequence context raises error."""
        with pytest.raises(RuntimeError, match="can only be used within a build_sequence"):
            with sub_sequence():
                play("ch1", square_pulse(duration="10us", amplitude="100mV"))

    def test_sub_sequence_in_schedule_raises_error(self):
        """Test that sub_sequence in a schedule context raises error."""
        with pytest.raises(RuntimeError, match="can only be used within a sequence context"):
            with build_schedule():
                with sub_sequence():
                    play("ch1", square_pulse(duration="10us", amplitude="100mV"))


class TestBuildSchedule:
    """Tests for build_schedule context manager."""

    def test_empty_schedule(self):
        """Test creating an empty schedule."""
        with build_schedule() as sched:
            pass
        assert isinstance(sched, Schedule)
        assert len(sched.items) == 0

    def test_schedule_with_operations(self):
        """Test schedule with operations and timing."""
        with build_schedule() as sched:
            op1 = play("ch1", square_pulse(duration="10us", amplitude="100mV"))
            play("ch2", square_pulse(duration="10us", amplitude="100mV"), ref_op=op1, ref_pt="start", rel_time="5us")

        assert len(sched.items) == 2

    def test_nested_schedule_representation(self):
        """Test nested schedule representation with sub_schedule context manager.

        The sub_schedule context manager creates a nested schedule and automatically
        adds it to the parent schedule with optional timing parameters.
        """
        with build_schedule() as outer:
            # Create inner schedule with operations
            with sub_schedule(name="sub_schedule") as _inner:
                play("ch1", square_pulse(duration="10us", amplitude="100mV"))
                play("ch2", square_pulse(duration="5us", amplitude="50mV"))

            # Add another operation relative to the nested schedule
            play(
                "ch3",
                square_pulse(duration="3us", amplitude="75mV"),
                ref_op="sub_schedule",
                ref_pt="end",
                rel_time="2us",
            )

        # Outer schedule should have 2 items: the nested schedule and the play operation
        assert len(outer.items) == 2

        # First item should be the inner schedule wrapped in ScheduledOperation
        assert isinstance(outer.items[0].op, Schedule)
        inner_sched = outer.items[0].op
        assert len(inner_sched.items) == 2
        assert outer.items[0].name == "sub_schedule"

        # Second item should be the play operation scheduled relative to the nested schedule
        assert isinstance(outer.items[1].op, Play)
        assert outer.items[1].ref_op == "sub_schedule"
        assert outer.items[1].ref_pt == RefPt.End
        assert outer.items[1].rel_time is not None

    def test_nested_schedule_modular_blocks(self):
        """Test using sub_schedule to create modular, reusable operation blocks.

        This demonstrates how sub-schedules can be used to encapsulate
        related operations (e.g., initialization, gates, readout) and
        compose them into larger schedules with precise timing control.
        """
        with build_schedule() as main_schedule:
            # Create initialization sub-schedule
            with sub_schedule(name="initialization"):
                play("qubit", square_pulse(duration="100ns", amplitude="200mV"))
                wait("qubit", duration="50ns")

            # Create gate operation positioned after initialization
            gate_token = play(
                "qubit",
                square_pulse(duration="20ns", amplitude="150mV"),
                ref_op="initialization",
                ref_pt="end",
                rel_time="10ns",
            )

            # Create measurement sub-schedule positioned after gate
            with sub_schedule(name="measurement", ref_op=gate_token, ref_pt="end", rel_time="50ns"):
                play("drive", square_pulse(duration="1us", amplitude="50mV"))
                record("readout", var="result", duration="1us")

        # Verify structure: 2 sub-schedules + 1 gate operation
        assert len(main_schedule.items) == 3

        # Check initialization block
        assert isinstance(main_schedule.items[0].op, Schedule)
        assert main_schedule.items[0].name == "initialization"
        init = main_schedule.items[0].op
        assert len(init.items) == 2  # play + wait

        # Check gate operation timing
        assert isinstance(main_schedule.items[1].op, Play)
        assert main_schedule.items[1].ref_op == "initialization"
        assert main_schedule.items[1].ref_pt == RefPt.End

        # Check measurement block
        assert isinstance(main_schedule.items[2].op, Schedule)
        assert main_schedule.items[2].name == "measurement"
        meas = main_schedule.items[2].op
        assert len(meas.items) == 2  # play + record
        assert main_schedule.items[2].ref_pt == RefPt.End

    def test_sub_schedule_outside_schedule_raises_error(self):
        """Test that sub_schedule outside a schedule context raises error."""
        with pytest.raises(RuntimeError, match="can only be used within a build_schedule"):
            with sub_schedule(name="invalid"):
                play("ch1", square_pulse(duration="10us", amplitude="100mV"))

    def test_sub_schedule_in_sequence_raises_error(self):
        """Test that sub_schedule in a sequence context raises error."""
        with pytest.raises(RuntimeError, match="can only be used within a build_schedule"):
            with build_sequence():
                with sub_schedule(name="invalid"):
                    play("ch1", square_pulse(duration="10us", amplitude="100mV"))


class TestPulseCreation:
    """Tests for pulse creation functions."""

    def test_square_pulse(self):
        """Test square pulse creation."""
        pulse = square_pulse(duration="10us", amplitude="100mV")
        assert isinstance(pulse, SquarePulse)

    def test_sine_pulse(self):
        """Test sine pulse creation."""
        pulse = sine_pulse(duration="20us", amplitude="50mV", frequency="5GHz")
        assert pulse is not None

    def test_arbitrary_pulse_with_samples(self):
        """Test arbitrary pulse with sample list."""
        pulse = arbitrary_pulse(samples=[0.0, 0.5, 1.0, 0.5, 0.0], duration="100ns", amplitude="80mV")
        assert pulse is not None

    def test_arbitrary_pulse_with_complex_samples(self):
        """Test arbitrary pulse with complex samples."""
        pulse = arbitrary_pulse(samples=[0.0 + 0.0j, 0.7 + 0.7j, 1.0 + 0.0j], duration="80ns", amplitude="90mV")
        assert pulse is not None

    def test_external_pulse(self):
        """Test external pulse reference."""
        pulse = external_pulse("pulses.gaussian", duration="50ns", amplitude="100mV", params={"sigma": "10"})
        assert pulse is not None


class TestBasicOperations:
    """Tests for basic operations."""

    def test_play_operation(self):
        """Test play operation in sequence."""
        with build_sequence() as seq:
            play("ch1", square_pulse(duration="10us", amplitude="100mV"))

        assert len(seq.items) == 1
        assert isinstance(seq.items[0], Play)
        assert seq.items[0].channel == "ch1"

    def test_wait_operation(self):
        """Test wait operation."""
        with build_sequence() as seq:
            wait("ch1", duration="5us")

        assert len(seq.items) == 1

    def test_wait_multiple_channels(self):
        """Test wait on multiple channels in sequence."""
        with build_sequence() as seq:
            wait("ch1", "ch2", "ch3", duration="5us")

        assert len(seq.items) == 1
        from eq1_pulse.models import Wait

        assert isinstance(seq.items[0], Wait)
        assert len(seq.items[0].channels) == 3

    def test_wait_single_channel_in_schedule(self):
        """Test that wait with single channel works in schedule."""
        with build_schedule() as sched:
            wait("ch1", duration="5us")

        assert len(sched.items) == 1

    def test_wait_multiple_channels_in_schedule_raises_error(self):
        """Test that wait with multiple channels raises error in schedule."""
        with (
            pytest.raises(RuntimeError, match=r"Wait with multiple channels .* is not allowed in schedule context"),
            build_schedule(),
        ):
            wait("ch1", "ch2", duration="5us")

    def test_barrier_in_sequence(self):
        """Test barrier operation in sequence."""
        with build_sequence() as seq:
            barrier("ch1", "ch2")

        assert len(seq.items) == 1
        assert isinstance(seq.items[0], Barrier)

    def test_barrier_not_in_schedule(self):
        """Test that barrier raises error in schedule."""
        with pytest.raises(RuntimeError, match="Barrier operations are not supported in schedule"), build_schedule():
            barrier("ch1", "ch2")


class TestFrequencyAndPhase:
    """Tests for frequency and phase operations."""

    def test_set_frequency(self):
        """Test set frequency operation."""
        with build_sequence() as seq:
            set_frequency("qubit", "5GHz")

        assert len(seq.items) == 1
        assert isinstance(seq.items[0], SetFrequency)

    def test_shift_frequency(self):
        """Test shift frequency operation."""
        with build_sequence() as seq:
            shift_frequency("qubit", "100MHz")

        assert len(seq.items) == 1
        assert isinstance(seq.items[0], ShiftFrequency)

    def test_set_phase(self):
        """Test set phase operation."""
        with build_sequence() as seq:
            set_phase("qubit", "90deg")

        assert len(seq.items) == 1
        assert isinstance(seq.items[0], SetPhase)

    def test_shift_phase(self):
        """Test shift phase operation."""
        with build_sequence() as seq:
            shift_phase("qubit", "45deg")

        assert len(seq.items) == 1
        assert isinstance(seq.items[0], ShiftPhase)


class TestControlFlow:
    """Tests for control flow constructs."""

    def test_repeat(self):
        """Test repeat loop."""
        with build_sequence() as seq:
            with repeat(10):
                play("ch1", square_pulse(duration="10us", amplitude="100mV"))

        assert len(seq.items) == 1
        assert isinstance(seq.items[0], Repetition)
        assert seq.items[0].count == 10
        assert len(seq.items[0].body.items) == 1

    def test_for_loop(self):
        """Test for loop."""
        with build_sequence() as seq:
            var_decl("i", "int", unit="MHz")
            with for_("i", range(0, 100, 10)):
                set_frequency("qubit", var("i"))

        assert len(seq.items) == 2
        assert isinstance(seq.items[0], VariableDecl)
        assert isinstance(seq.items[1], Iteration)

    def test_if_conditional(self):
        """Test if conditional."""
        with build_sequence() as seq:
            var_decl("result", "bool")
            with if_("result"):
                play("ch1", square_pulse(duration="10us", amplitude="100mV"))

        assert len(seq.items) == 2
        assert isinstance(seq.items[0], VariableDecl)
        assert isinstance(seq.items[1], Conditional)

    def test_nested_control_flow(self):
        """Test nested control flow."""
        with build_sequence() as seq:
            var_decl("i", "int")
            var_decl("result", "bool")
            with repeat(5):
                with for_("i", range(10)):
                    with if_("result"):
                        play("ch1", square_pulse(duration="10us", amplitude="100mV"))

        assert len(seq.items) == 3  # 2 var_decls + 1 repeat


class TestVariables:
    """Tests for variable operations."""

    def test_var_decl_simple(self):
        """Test simple variable declaration."""
        with build_sequence() as seq:
            var_decl("count", "int")

        assert len(seq.items) == 1
        assert isinstance(seq.items[0], VariableDecl)
        assert seq.items[0].name == "count"
        assert seq.items[0].dtype == "int"

    def test_var_decl_with_unit(self):
        """Test variable declaration with unit."""
        with build_sequence() as seq:
            var_decl("amp", "float", unit="mV")

        assert len(seq.items) == 1
        assert isinstance(seq.items[0], VariableDecl)
        assert seq.items[0].unit == "mV"

    def test_var_decl_with_shape(self):
        """Test variable declaration with array shape."""
        with build_sequence() as seq:
            var_decl("iq_data", "complex", shape=(100,))

        assert len(seq.items) == 1
        assert isinstance(seq.items[0], VariableDecl)
        assert seq.items[0].shape == (100,)

    def test_var_reference(self):
        """Test variable reference creation."""
        ref = var("frequency")
        assert ref.var == "frequency"

    def test_channel_reference(self):
        """Test channel reference creation."""
        ch = channel("qubit")
        assert ch.channel == "qubit"

    def test_pulse_reference(self):
        """Test pulse reference creation."""
        pref = pulse_ref("my_pulse")
        assert pref.pulse_name == "my_pulse"


class TestMeasurement:
    """Tests for measurement operations."""

    def test_measure_single_channel(self):
        """Test measure with single channel."""
        with build_sequence() as seq:
            var_decl("result", "complex", unit="mV")
            measure("qubit", result_var="result", duration="1us", amplitude="50mV")

        assert len(seq.items) == 3  # var_decl + play + record

    def test_measure_tuple_channels(self):
        """Test measure with tuple of channels."""
        with build_sequence() as seq:
            var_decl("result", "complex", unit="mV")
            measure(("drive", "readout"), result_var="result", duration="1us", amplitude="50mV")

        assert len(seq.items) == 3  # var_decl + play + record

    def test_record_operation(self):
        """Test record operation."""
        with build_sequence() as seq:
            var_decl("data", "complex", unit="mV")
            record("readout", "data", duration="1us", integration="demod")

        assert len(seq.items) == 2
        assert isinstance(seq.items[1], Record)

    def test_discriminate_operation(self):
        """Test discriminate operation."""
        with build_sequence() as seq:
            var_decl("raw", "complex", unit="mV")
            var_decl("state", "bool")
            discriminate(target="state", source="raw", threshold="0.5mV")

        assert len(seq.items) == 3
        assert isinstance(seq.items[2], Discriminate)

    def test_measure_and_discriminate(self):
        """Test combined measure and discriminate."""
        with build_sequence() as seq:
            var_decl("raw", "complex", unit="mV")
            var_decl("state", "bool")
            measure_and_discriminate(
                "qubit",
                raw_var="raw",
                result_var="state",
                threshold="0.5mV",
                duration="1us",
                amplitude="50mV",
            )

        # Should have: 2 var_decls + play + record + discriminate
        assert len(seq.items) == 5

    def test_measure_and_discriminate_and_if(self):
        """Test measure, discriminate, and conditional."""
        with build_sequence() as seq:
            var_decl("raw", "complex", unit="mV")
            var_decl("state", "bool")
            with measure_and_discriminate_and_if_(
                "qubit",
                raw_var="raw",
                result_var="state",
                threshold="0.5mV",
                duration="1us",
                amplitude="50mV",
            ):
                play("qubit", square_pulse(duration="50ns", amplitude="100mV"))

        # Should have: 2 var_decls + play + record + discriminate + conditional
        assert len(seq.items) == 6
        assert isinstance(seq.items[5], Conditional)


class TestDataOperations:
    """Tests for data operations."""

    def test_store_operation(self):
        """Test store operation."""
        with build_sequence() as seq:
            var_decl("result", "complex", unit="mV")
            var_decl("stored", "complex", unit="mV")
            store("stored", "result", mode="last")

        assert len(seq.items) == 3
        assert isinstance(seq.items[2], Store)


class TestScheduleSpecific:
    """Tests for schedule-specific features."""

    def test_schedule_with_timing(self):
        """Test schedule with relative timing."""
        with build_schedule() as sched:
            op1 = play("ch1", square_pulse(duration="10us", amplitude="100mV"), name="op1")
            play(
                "ch2",
                square_pulse(duration="10us", amplitude="100mV"),
                ref_op=op1,
                ref_pt="start",
                rel_time="5us",
                name="op2",
            )

        assert len(sched.items) == 2

    def test_schedule_operations_return_tokens(self):
        """Test that schedule operations return tokens."""
        with build_schedule():
            token = play("ch1", square_pulse(duration="10us", amplitude="100mV"), name="pulse1")

        assert token is not None
        assert token.name == "pulse1"

    def test_sequence_operations_return_none(self):
        """Test that sequence operations return None."""
        with build_sequence():
            result = play("ch1", square_pulse(duration="10us", amplitude="100mV"))

        assert result is None


class TestErrorHandling:
    """Tests for error handling."""

    def test_operation_outside_context_raises_error(self):
        """Test that operations outside context raise error."""
        with pytest.raises(RuntimeError, match="No active sequence or schedule"):
            play("ch1", square_pulse(duration="10us", amplitude="100mV"))

    def test_barrier_in_schedule_raises_error(self):
        """Test that barrier in schedule raises error."""
        with pytest.raises(RuntimeError, match="not supported in schedule"), build_schedule():
            barrier("ch1")

    def test_control_flow_in_schedule_raises_error(self):
        """Test that control flow in schedule raises error."""
        with pytest.raises(RuntimeError, match="only supported in sequence"), build_schedule():
            # Nested context is intentional - testing error condition
            with repeat(10):
                pass


class TestComplexScenarios:
    """Tests for complex usage scenarios."""

    def test_rabi_experiment(self):
        """Test a simple Rabi experiment."""
        with build_sequence() as seq:
            var_decl("amp", "int", unit="mV")
            var_decl("result", "complex", unit="mV")

            with for_("amp", range(0, 100, 10)):
                play("qubit", square_pulse(duration="100ns", amplitude="1mV"), scale_amp=var("amp"))
                measure("qubit", result_var="result", duration="1us", amplitude="50mV")

        assert len(seq.items) == 3  # 2 var_decls + for loop

    def test_active_reset_protocol(self):
        """Test active reset protocol."""
        with build_sequence() as seq:
            var_decl("raw", "complex", unit="mV")
            var_decl("is_excited", "bool")

            # This nested structure is intentional for active reset
            with repeat(3):
                with measure_and_discriminate_and_if_(
                    "qubit",
                    raw_var="raw",
                    result_var="is_excited",
                    threshold="0.5mV",
                    duration="1us",
                    amplitude="50mV",
                ):
                    play("qubit", square_pulse(duration="50ns", amplitude="100mV"))

        # 2 var_decls + repeat (containing measure+discriminate+conditional)
        assert len(seq.items) == 3

    def test_multi_qubit_measurement(self):
        """Test multi-qubit measurement."""
        with build_sequence() as seq:
            var_decl("raw_q0", "complex", unit="mV")
            var_decl("raw_q1", "complex", unit="mV")
            var_decl("state_q0", "bool")
            var_decl("state_q1", "bool")

            measure(("drive_q0", "readout_q0"), result_var="raw_q0", duration="1us", amplitude="50mV")
            measure(("drive_q1", "readout_q1"), result_var="raw_q1", duration="1us", amplitude="50mV")
            discriminate(target="state_q0", source="raw_q0", threshold="0.45mV")
            discriminate(target="state_q1", source="raw_q1", threshold="0.52mV")

        # 4 var_decls + 2 measures (each is play+record) + 2 discriminates = 12
        assert len(seq.items) == 12


class TestSerialization:
    """Tests for sequence/schedule serialization."""

    def test_sequence_serialization(self):
        """Test that sequences can be serialized and deserialized."""
        with build_sequence() as seq:
            play("ch1", square_pulse(duration="10us", amplitude="100mV"))
            wait("ch1", duration="5us")

        # Serialize to JSON
        json_str = seq.model_dump_json()
        assert json_str is not None

        # Deserialize
        restored = OpSequence.model_validate_json(json_str)
        assert len(restored.items) == len(seq.items)

    def test_schedule_serialization(self):
        """Test that schedules can be serialized and deserialized."""
        with build_schedule() as sched:
            play("ch1", square_pulse(duration="10us", amplitude="100mV"), name="op1")

        # Serialize to JSON
        json_str = sched.model_dump_json()
        assert json_str is not None

        # Deserialize
        restored = Schedule.model_validate_json(json_str)
        assert len(restored.items) == len(sched.items)


class TestNestedDecorators:
    """Tests for the @nested_sequence and @nested_schedule decorators."""

    def test_nested_sequence_decorator_in_sequence(self):
        """Test @nested_sequence decorator creates sub_sequence in sequence context."""
        from eq1_pulse.builder import nested_sequence

        @nested_sequence
        def hadamard_gate(qubit: str):
            """Apply a Hadamard gate."""
            play(qubit, square_pulse(duration="20ns", amplitude="100mV"))
            shift_phase(qubit, "90deg")
            play(qubit, square_pulse(duration="20ns", amplitude="100mV"))

        with build_sequence() as seq:
            hadamard_gate("qubit0")
            play("qubit0", square_pulse(duration="10ns", amplitude="50mV"))

        # Should have 2 items: sub-sequence (with hadamard) + play
        assert len(seq.items) == 2
        assert isinstance(seq.items[0], OpSequence)  # sub_sequence
        assert isinstance(seq.items[1], Play)

        # Check the sub-sequence contains 3 operations
        sub_seq = seq.items[0]
        assert len(sub_seq.items) == 3

    def test_nested_schedule_decorator_in_schedule(self):
        """Test @nested_schedule decorator creates sub_schedule in schedule context."""
        from eq1_pulse.builder import nested_schedule

        @nested_schedule
        def measurement_block(drive_ch: str, readout_ch: str, result_var: str):
            """Perform readout measurement."""
            play(drive_ch, square_pulse(duration="1us", amplitude="50mV"))
            record(readout_ch, var=result_var, duration="1us")

        with build_schedule() as sched:
            op1 = play("qubit", square_pulse(duration="20ns", amplitude="100mV"))
            add_block(measurement_block("drive0", "readout0", "result"), ref_op=op1, ref_pt="end", rel_time="100ns")

        # Should have 2 items: play + sub-schedule
        assert len(sched.items) == 2
        assert isinstance(sched.items[0].op, Play)
        assert isinstance(sched.items[1].op, Schedule)  # sub_schedule

        # Check the sub-schedule contains 2 operations
        sub_sched = sched.items[1].op
        assert isinstance(sub_sched, Schedule)
        assert len(sub_sched.items) == 2

    def test_nested_sequence_with_parameters(self):
        """Test @nested_sequence decorator with function parameters."""
        from eq1_pulse.builder import nested_sequence

        @nested_sequence
        def rabi_pulse(qubit: str, amplitude: str, duration: str):
            """Apply a Rabi drive pulse."""
            play(qubit, square_pulse(duration=duration, amplitude=amplitude))
            wait(qubit, duration="50ns")

        with build_sequence() as seq:
            rabi_pulse("qubit0", "100mV", "20ns")
            rabi_pulse("qubit1", "150mV", "30ns")

        assert len(seq.items) == 2
        for item in seq.items:
            assert isinstance(item, OpSequence)
            assert len(item.items) == 2  # play + wait

    def test_nested_schedule_returns_token(self):
        """Test @nested_schedule decorator returns operation token in schedule context."""
        from eq1_pulse.builder import nested_schedule

        @nested_schedule
        def gate_sequence(qubit: str):
            """Apply gate sequence."""
            play(qubit, square_pulse(duration="20ns", amplitude="100mV"))

        with build_schedule() as sched:
            token1 = add_block(gate_sequence("qubit0"), name="gate1")
            add_block(gate_sequence("qubit1"), ref_op=token1, ref_pt="end", rel_time="50ns")

        assert len(sched.items) == 2

    def test_nested_sequence_in_control_flow(self):
        """Test @nested_sequence decorator works inside control flow."""
        from eq1_pulse.builder import nested_sequence

        @nested_sequence
        def pulse_block(qubit: str):
            """Simple pulse block."""
            play(qubit, square_pulse(duration="20ns", amplitude="100mV"))

        with build_sequence() as seq:
            with repeat(3):
                pulse_block("qubit0")

        assert len(seq.items) == 1
        assert isinstance(seq.items[0], Repetition)
        # Inside the repetition body, there should be a sub-sequence
        assert len(seq.items[0].body.items) == 1
        assert isinstance(seq.items[0].body.items[0], OpSequence)

    def test_nested_sequence_without_context(self):
        """Test @nested_sequence decorator works outside building context."""
        from eq1_pulse.builder import nested_sequence

        call_count = 0

        @nested_sequence
        def test_func(x: int) -> int:
            """Test function."""
            nonlocal call_count
            call_count += 1
            return x * 2

        # Should work normally without context
        result = test_func(5)
        assert result == 10
        assert call_count == 1

    def test_nested_schedule_without_context(self):
        """Test @nested_schedule decorator raises error outside building context."""
        from eq1_pulse.builder import nested_schedule

        @nested_schedule
        def test_func(x: int) -> int:
            """Test function."""
            return x * 2

        # Should raise error when called without context
        with pytest.raises(RuntimeError, match=r"No active building context"):
            test_func(5)

    def test_multiple_nested_sequence_functions(self):
        """Test using multiple @nested_sequence decorated functions."""
        from eq1_pulse.builder import nested_sequence

        @nested_sequence
        def init_block(qubit: str):
            """Initialization."""
            play(qubit, square_pulse(duration="100ns", amplitude="200mV"))

        @nested_sequence
        def gate_block(qubit: str):
            """Gate operations."""
            play(qubit, square_pulse(duration="20ns", amplitude="100mV"))
            shift_phase(qubit, "90deg")

        @nested_sequence
        def readout_block(qubit: str):
            """Readout."""
            play(qubit, square_pulse(duration="1us", amplitude="50mV"))

        with build_sequence() as seq:
            init_block("qubit0")
            gate_block("qubit0")
            readout_block("qubit0")

        # Should have 3 sub-sequences
        assert len(seq.items) == 3
        assert all(isinstance(item, OpSequence) for item in seq.items)

    def test_nested_sequence_in_schedule_raises_error(self):
        """Test @nested_sequence raises error in schedule context."""
        from eq1_pulse.builder import nested_sequence

        @nested_sequence
        def sequence_func(qubit: str):
            """Function for sequences only."""
            play(qubit, square_pulse(duration="20ns", amplitude="100mV"))

        with (
            pytest.raises(RuntimeError, match=r"@nested_sequence decorator cannot be used in schedule context"),
            build_schedule(),
        ):
            sequence_func("qubit0")

    def test_nested_schedule_in_sequence_raises_error(self):
        """Test @nested_schedule raises error in sequence context."""
        from eq1_pulse.builder import nested_schedule

        @nested_schedule
        def schedule_func(qubit: str):
            """Function for schedules only."""
            play(qubit, square_pulse(duration="20ns", amplitude="100mV"))

        # ScheduleBlock can only be added in schedule contexts
        with (
            pytest.raises(RuntimeError, match=r"add_block\(\) can only be used within a build_schedule\(\) context"),
            build_sequence(),
        ):
            block = schedule_func("qubit0")
            add_block(block)

    def test_unconsumed_schedule_block_raises_error(self):
        """Test that unconsumed ScheduleBlock raises error on context close."""
        from eq1_pulse.builder import nested_schedule

        @nested_schedule
        def test_block(qubit: str):
            """Test block."""
            play(qubit, square_pulse(duration="20ns", amplitude="100mV"))

        # Should raise error when block is created but not added
        with pytest.raises(
            RuntimeError,
            match=r"Schedule context closed with 1 unconsumed ScheduleBlock\(s\).*add_block\(\)",
        ):
            with build_schedule():
                test_block("qubit0")  # Created but not added with add_block()

    def test_multiple_unconsumed_blocks_raises_error(self):
        """Test that multiple unconsumed ScheduleBlocks are detected."""
        from eq1_pulse.builder import nested_schedule

        @nested_schedule
        def test_block(qubit: str):
            """Test block."""
            play(qubit, square_pulse(duration="20ns", amplitude="100mV"))

        # Should report count of unconsumed blocks
        with pytest.raises(
            RuntimeError,
            match=r"Schedule context closed with 2 unconsumed ScheduleBlock\(s\)",
        ):
            with build_schedule():
                test_block("qubit0")
                test_block("qubit1")
                # Neither added with add_block()
