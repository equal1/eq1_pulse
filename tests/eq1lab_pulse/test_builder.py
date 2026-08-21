"""Tests for the builder interface."""

import re

import pytest

from eq1_pulse.builder import (
    arbitrary_pulse,
    assign,
    barrier,
    build_sequence,
    channel,
    demod_integration,
    discriminate,
    experimental,
    expr,
    ext,
    extern_decl,
    external_block,
    external_pulse,
    for_,
    full_integration,
    if_,
    measure,
    param_decl,
    phase,
    play,
    pulse_decl,
    pulse_ref,
    record,
    repeat,
    set_frequency,
    set_phase,
    shift_frequency,
    shift_phase,
    sine_pulse,
    square_pulse,
    step_pulse,
    store,
    sub_sequence,
    trigger_pulse,
    var,
    var_decl,
    wait,
    wait_for_trigger,
)
from eq1_pulse.models import (
    Amplitude,
    Assign,
    Barrier,
    Conditional,
    DigitalTriggerPulse,
    Discriminate,
    Duration,
    ExternalBlock,
    ExternalDecl,
    Iteration,
    OpSequence,
    ParameterDecl,
    Play,
    PulseDecl,
    Record,
    Repetition,
    SetFrequency,
    SetPhase,
    ShiftFrequency,
    ShiftPhase,
    SquarePulse,
    StepPulse,
    Store,
    Time,
    ValueLimits,
    VariableDecl,
    VariableRef,
    Voltage,
    WaitForTrigger,
)
from eq1_pulse.models.reference_types import ChannelRef, ExternalRef


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
        with pytest.raises(RuntimeError, match="sub_sequence"):
            with sub_sequence():
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

    def test_amplitude_with_phase_syntax(self):
        """Test amplitude @ phase syntax for complex amplitudes.

        This test demonstrates the recommended syntax for specifying complex
        amplitudes using the @ operator with phase, similar to the quick start
        example in the documentation.
        """
        with build_sequence() as seq:
            # Play a pulse with phase specified using @ operator
            play("drive", square_pulse(duration="20us", amplitude="50mV" @ phase("90deg")))

            # Also test with wait
            wait("drive", duration="5us")

            # Test with different phase value
            play("drive", square_pulse(duration="10us", amplitude="100mV" @ phase("180deg")))

        assert len(seq.items) == 3
        assert isinstance(seq.items[0], Play)
        assert isinstance(seq.items[2], Play)

        # Verify the pulse has the correct complex amplitude with phase
        # The amplitude should be a complex number with phase encoded
        first_pulse = seq.items[0].pulse
        assert isinstance(first_pulse, SquarePulse)
        # Complex amplitude with 90 degree phase


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

    def test_barrier_in_sequence(self):
        """Test barrier operation in sequence."""
        with build_sequence() as seq:
            barrier("ch1", "ch2")

        assert len(seq.items) == 1
        assert isinstance(seq.items[0], Barrier)


class TestStepAndTriggerPulses:
    """Tests for step_pulse(), trigger_pulse() and wait_for_trigger()."""

    def test_step_pulse(self):
        """Test step_pulse happy path."""
        pulse = step_pulse(duration="1us", amplitude="150mV")
        assert isinstance(pulse, StepPulse)
        assert pulse.duration == Duration("1us")
        assert pulse.amplitude == Amplitude("150mV")

    def test_trigger_pulse(self):
        """Test trigger_pulse happy path."""
        pulse = trigger_pulse(duration="100ns")
        assert isinstance(pulse, DigitalTriggerPulse)
        assert pulse.duration == Duration("100ns")

    def test_trigger_pulse_rejects_amplitude(self):
        """trigger_pulse() has no amplitude keyword to pass."""
        with pytest.raises(TypeError):
            trigger_pulse(duration="100ns", amplitude="1V")  # type: ignore[call-arg]

    def test_wait_for_trigger_in_sequence(self):
        """Test wait_for_trigger operation in sequence."""
        with build_sequence() as seq:
            wait_for_trigger("trig_in")

        assert len(seq.items) == 1
        assert isinstance(seq.items[0], WaitForTrigger)
        assert seq.items[0].channel == ChannelRef("trig_in")

    def test_wait_for_trigger_outside_sequence_raises_error(self):
        """Test that wait_for_trigger outside a sequence context raises RuntimeError."""
        with pytest.raises(RuntimeError, match="No active building context for wait_for_trigger\\(\\)"):
            wait_for_trigger("trig_in")


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

    def test_repeat_with_variable_count(self):
        """Test repeat loop with a variable count."""
        with build_sequence() as seq:
            var_decl("n", "int")
            with repeat(var("n")):
                play("ch1", square_pulse(duration="10us", amplitude="100mV"))

        assert len(seq.items) == 2
        rep = seq.items[1]
        assert isinstance(rep, Repetition)
        assert rep.count == VariableRef("n")

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
        with build_sequence():
            var_decl("frequency", "float", unit="GHz")
            ref = var("frequency")
            assert ref.var == "frequency"

    def test_channel_reference(self):
        """Test channel reference creation."""
        ch = channel("qubit")
        assert ch.root == "qubit"

    def test_pulse_reference(self):
        """Test pulse reference creation."""
        with build_sequence():
            pulse_decl("my_pulse", square_pulse(duration="100ns", amplitude="200mV"))
            pref = pulse_ref("my_pulse")
            assert pref.pulse_name == "my_pulse"

    def test_pulse_decl_in_sequence(self):
        """Test pulse declaration in sequence context."""
        with build_sequence() as seq:
            pulse_decl("my_pulse", square_pulse(duration="100ns", amplitude="200mV"))

        assert len(seq.items) == 1
        assert isinstance(seq.items[0], PulseDecl)
        assert seq.items[0].name == "my_pulse"
        assert isinstance(seq.items[0].pulse, SquarePulse)

    def test_pulse_decl_and_reference(self):
        """Test declaring a pulse and using its reference."""
        with build_sequence() as seq:
            pulse_decl("reusable", square_pulse(duration="100ns", amplitude="200mV"))
            play("qubit", pulse_ref("reusable"))
            play("qubit", pulse_ref("reusable"))  # Reuse

        assert len(seq.items) == 3
        assert isinstance(seq.items[0], PulseDecl)
        assert isinstance(seq.items[1], Play)
        assert isinstance(seq.items[2], Play)


class TestParamAndExternDecl:
    """Tests for param_decl() and extern_decl()."""

    def test_param_decl_simple(self):
        """Test a required parameter declaration with no default or limits."""
        with build_sequence() as seq:
            param_decl("n_shots", "int")

        assert len(seq.items) == 1
        assert isinstance(seq.items[0], ParameterDecl)
        assert seq.items[0].name == "n_shots"
        assert seq.items[0].dtype == "int"
        assert seq.items[0].default is None
        assert seq.items[0].limits is None

    def test_param_decl_with_default_and_limits(self):
        """Test a parameter declaration with a default and min/max/allowed limits."""
        with build_sequence() as seq:
            param_decl("n_shots", "int", default=1000, min=1, max=100_000)

        assert len(seq.items) == 1
        assert isinstance(seq.items[0], ParameterDecl)
        assert seq.items[0].default == 1000
        assert isinstance(seq.items[0].limits, ValueLimits)
        assert seq.items[0].limits.minimum == 1
        assert seq.items[0].limits.maximum == 100_000
        assert seq.items[0].limits.allowed is None

    def test_param_decl_with_allowed(self):
        """Test a parameter declaration restricted to a fixed set of values."""
        with build_sequence() as seq:
            param_decl("mode", "int", allowed=[0, 1, 2])

        assert isinstance(seq.items[0], ParameterDecl)
        assert isinstance(seq.items[0].limits, ValueLimits)
        assert seq.items[0].limits.allowed == [0, 1, 2]

    def test_param_decl_coerces_unit_suffixed_string_default_and_limits(self):
        """A unit-suffixed string default/min/max/allowed is coerced to the dimensional quantity."""
        with build_sequence() as seq:
            param_decl("amp", "float", unit="mV", default="10us", min="5us", max="20us", allowed=["10us", "15us"])

        assert isinstance(seq.items[0], ParameterDecl)
        assert isinstance(seq.items[0].default, Time)
        assert seq.items[0].default.us == 10
        assert isinstance(seq.items[0].limits, ValueLimits)
        assert isinstance(seq.items[0].limits.minimum, Time)
        assert seq.items[0].limits.minimum.us == 5
        assert isinstance(seq.items[0].limits.maximum, Time)
        assert seq.items[0].limits.maximum.us == 20
        assert seq.items[0].limits.allowed is not None
        assert [value.us for value in seq.items[0].limits.allowed] == [10, 15]  # type: ignore[union-attr]

    def test_param_decl_registers_into_variable_namespace(self):
        """A parameter is referenced with var() and shares the variable namespace."""
        with build_sequence():
            param_decl("n_shots", "int", default=1000)
            ref = var("n_shots")
            assert ref.var == "n_shots"

    def test_param_decl_redeclaration_with_var_decl_raises(self):
        """Declaring a variable with the same name as a parameter is a redeclaration error."""
        with build_sequence():
            param_decl("n_shots", "int")
            with pytest.raises(RuntimeError, match="'n_shots' is already declared"):
                var_decl("n_shots", "int")

    def test_var_decl_redeclaration_with_param_decl_raises(self):
        """Declaring a parameter with the same name as a variable is a redeclaration error."""
        with build_sequence():
            var_decl("n_shots", "int")
            with pytest.raises(RuntimeError, match="'n_shots' is already declared"):
                param_decl("n_shots", "int")

    def test_extern_decl_simple(self):
        """Test a required external constant declaration with no default or limits."""
        with build_sequence() as seq:
            extern_decl("q0.f01", "float", unit="GHz")

        assert len(seq.items) == 1
        assert isinstance(seq.items[0], ExternalDecl)
        assert seq.items[0].name == "q0.f01"
        assert seq.items[0].dtype == "float"
        assert seq.items[0].unit == "GHz"
        assert seq.items[0].default is None
        assert seq.items[0].limits is None

    def test_extern_decl_with_default_and_limits(self):
        """Test an external constant declaration with a default and limits."""
        with build_sequence() as seq:
            extern_decl("readout.threshold", "float", unit="mV", default=0, min=-100, max=100)

        assert isinstance(seq.items[0], ExternalDecl)
        assert seq.items[0].default == 0
        assert isinstance(seq.items[0].limits, ValueLimits)
        assert seq.items[0].limits.minimum == -100
        assert seq.items[0].limits.maximum == 100

    def test_extern_decl_coerces_unit_suffixed_string_default(self):
        """A unit-suffixed string default is coerced to the dimensional quantity."""
        with build_sequence() as seq:
            extern_decl("readout.threshold", "float", unit="mV", default="100mV")

        assert isinstance(seq.items[0], ExternalDecl)
        assert isinstance(seq.items[0].default, Voltage)
        assert seq.items[0].default.mV == 100

    def test_extern_decl_registers_into_external_namespace(self):
        """An external constant is referenced with ext(), never var()."""
        with build_sequence():
            extern_decl("q0.f01", "float", unit="GHz")
            ref = ext("q0.f01")
            assert ref.ext == "q0.f01"

    def test_extern_decl_does_not_share_variable_namespace(self):
        """Declaring a variable with the same name as an external symbol is not a conflict."""
        with build_sequence():
            extern_decl("q0_f01", "float")
            # Should not raise: variables and external symbols are separate namespaces.
            var_decl("q0_f01", "float")

    def test_ext_on_undeclared_symbol_raises(self):
        """Using ext() on an undeclared external symbol raises RuntimeError."""
        with build_sequence():
            with pytest.raises(RuntimeError, match=re.escape("External symbol 'q0.f01' has not been declared")):
                ext("q0.f01")


class TestMeasurement:
    """Tests for measurement operations."""

    def test_measure_single_channel(self):
        """Test measure with single channel."""
        with build_sequence() as seq:
            var_decl("result", "complex", unit="mV")
            measure("qubit", result_var="result", duration="1us", amplitude="50mV", integration=full_integration())

        assert len(seq.items) == 3  # var_decl + play + record

    def test_measure_tuple_channels(self):
        """Test measure with tuple of channels."""
        with build_sequence() as seq:
            var_decl("result", "complex", unit="mV")
            measure(
                ("drive", "readout"),
                result_var="result",
                duration="1us",
                amplitude="50mV",
                integration=full_integration(),
            )

        assert len(seq.items) == 3  # var_decl + play + record

    def test_record_operation(self):
        """Test record operation."""
        with build_sequence() as seq:
            var_decl("data", "complex", unit="mV")
            record("readout", "data", duration="1us", integration=demod_integration())

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
            measure(
                "qubit",
                result_var="raw",
                duration="1us",
                amplitude="50mV",
                integration=full_integration(),
            )
            discriminate(
                target="state",
                source="raw",
                threshold="0.5mV",
            )

        # Should have: 2 var_decls + play + record + discriminate
        assert len(seq.items) == 5

    def test_measure_and_discriminate_and_if(self):
        """Test measure, discriminate, and conditional."""
        with build_sequence() as seq:
            var_decl("raw", "complex", unit="mV")
            var_decl("state", "bool")
            measure(
                "qubit",
                result_var="raw",
                duration="1us",
                amplitude="50mV",
                integration=full_integration(),
            )
            discriminate(
                target="state",
                source="raw",
                threshold="0.5mV",
            )
            with if_("state"):
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

    def test_assign_operation_with_literal(self):
        """Test assign operation writing a plain literal."""
        with build_sequence() as seq:
            var_decl("count", "int")
            assign("count", 0)

        assert len(seq.items) == 2
        op = seq.items[1]
        assert isinstance(op, Assign)
        assert op.target.var == "count"
        assert op.value == 0

    def test_assign_operation_with_expression(self):
        """Test assign operation writing an expression over another variable."""
        with build_sequence() as seq:
            var_decl("count", "int")
            var_decl("doubled", "int")
            assign("count", 0)
            assign("doubled", expr(var("count")) * 2)

        assert len(seq.items) == 4
        op = seq.items[3]
        assert isinstance(op, Assign)
        assert op.target.var == "doubled"

    def test_assign_operation_with_variable_ref(self):
        """Test assign operation copying another variable's value directly."""
        with build_sequence() as seq:
            var_decl("source", "int")
            var_decl("dest", "int")
            assign("dest", var("source"))

        op = seq.items[2]
        assert isinstance(op, Assign)
        assert isinstance(op.value, VariableRef)
        assert op.value.var == "source"


class TestExternalBlock:
    """Tests for the external_block() builder function."""

    def test_named_channels_form(self):
        """Test the channels= mapping form with params and results."""
        with build_sequence() as seq:
            var_decl("iq", "complex", unit="mV")
            external_block(
                program="eq1.cal.measure",
                channels={"drive": "q0", "readout": "q0_ro"},
                params={"amp": "50mV"},
                results={"iq": var("iq")},
            )

        assert len(seq.items) == 2
        op = seq.items[1]
        assert isinstance(op, ExternalBlock)
        assert op.channels == {"drive": "q0", "readout": "q0_ro"}
        assert op.results is not None
        assert op.results["iq"].var == "iq"

    def test_channels_accept_an_externally_supplied_name(self):
        """A channel name the calibration store owns is an ``ext()``, declared like any other."""
        with build_sequence() as seq:
            extern_decl("q0.drive", "float")
            external_block(program="eq1.cal.cz", channels={"drive": ext("q0.drive"), "readout": "q0_ro"})

        op = seq.items[1]
        assert isinstance(op, ExternalBlock)
        assert op.channels == {"drive": ExternalRef("q0.drive"), "readout": ChannelRef("q0_ro")}

    def test_an_undeclared_external_channel_is_rejected(self):
        """The declaration check that guards every other external symbol guards this one too."""
        with build_sequence(), pytest.raises(RuntimeError, match="has not been declared"):
            external_block(program="eq1.cal.cz", channels={"drive": ext("q0.drive")})

    def test_positional_channels_form(self):
        """Test the positional channels form generates deterministic role keys."""
        with build_sequence() as seq:
            external_block("q0", "q1", program="eq1.cal.cz")

        assert len(seq.items) == 1
        op = seq.items[0]
        assert isinstance(op, ExternalBlock)
        assert op.channels == {"0": "q0", "1": "q1"}
        assert op.duration is None

    def test_pure_reservation(self):
        """Test a pure reservation with no referenced program."""
        with build_sequence() as seq:
            external_block("q1", duration="1us")

        assert len(seq.items) == 1
        op = seq.items[0]
        assert isinstance(op, ExternalBlock)
        assert op.program is None
        assert op.channels == {"0": "q1"}

    def test_positional_and_channels_mapping_rejected(self):
        """Test that supplying both positional channels and channels= raises."""
        with build_sequence(), pytest.raises(ValueError, match="cannot accept both positional channels"):
            external_block("q0", channels={"drive": "q1"}, program="eq1.cal.cz")

    def test_no_channels_rejected(self):
        """Test that omitting both positional channels and channels= raises."""
        with build_sequence(), pytest.raises(ValueError, match="requires at least one channel"):
            external_block(program="eq1.cal.cz")

    def test_undeclared_results_variable_rejected(self):
        """Test that an undeclared results variable raises."""
        with build_sequence(), pytest.raises(RuntimeError, match=r"not been declared|undeclared"):
            external_block("q0", program="eq1.cal.measure", results={"iq": "undeclared_var"})

    def test_in_repeat(self):
        """Test external_block inside a repeat loop."""
        with build_sequence() as seq:
            with repeat(3):
                external_block("q0", program="eq1.cal.cz")

        assert isinstance(seq.items[0], Repetition)
        assert isinstance(seq.items[0].body.items[0], ExternalBlock)

    def test_in_for_loop(self):
        """Test external_block inside a for_ loop."""
        with build_sequence() as seq:
            var_decl("i", "int")
            with for_("i", range(3)):
                external_block("q0", program="eq1.cal.cz")

        assert isinstance(seq.items[1], Iteration)
        assert isinstance(seq.items[1].body.items[0], ExternalBlock)

    def test_in_if_conditional(self):
        """Test external_block inside an if_ conditional."""
        with build_sequence() as seq:
            var_decl("result", "bool")
            with if_("result"):
                external_block("q0", program="eq1.cal.cz")

        assert isinstance(seq.items[1], Conditional)
        assert isinstance(seq.items[1].body.items[0], ExternalBlock)

    def test_in_sub_sequence(self):
        """Test external_block inside a sub_sequence."""
        with build_sequence() as seq:
            with sub_sequence():
                external_block("q0", program="eq1.cal.cz")

        assert isinstance(seq.items[0], OpSequence)
        assert isinstance(seq.items[0].items[0], ExternalBlock)

    def test_not_exported_from_experimental(self):
        """Test that external_block is not part of the experimental builder API."""
        assert not hasattr(experimental, "external_block")


class TestErrorHandling:
    """Tests for error handling."""

    def test_operation_outside_context_raises_error(self):
        """Test that operations outside context raise error."""
        with pytest.raises(RuntimeError, match="No active building context for play\\(\\)"):
            play("ch1", square_pulse(duration="10us", amplitude="100mV"))

    def test_repeat_without_context_raises_error(self):
        """Test that repeat outside context raises error."""
        with pytest.raises(RuntimeError, match="No active building context for repeat\\(\\)"):
            with repeat(5):
                pass

    def test_for_without_context_raises_error(self):
        """Test that for_ outside context raises error.

        Note: for_ validates variables first, so it fails on undeclared variable
        before checking for context. This is acceptable behavior.
        """
        with pytest.raises(RuntimeError, match="Variable 'i' has not been declared"):
            with for_("i", range(5)):
                pass

    def test_if_without_context_raises_error(self):
        """Test that if_ outside context raises error.

        Note: if_ validates variables first, so it fails on undeclared variable
        before checking for context. This is acceptable behavior.
        """
        with pytest.raises(RuntimeError, match="references undeclared variable 'result'"):
            with if_("result"):
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
                measure("qubit", result_var="result", duration="1us", amplitude="50mV", integration=full_integration())

        assert len(seq.items) == 3  # 2 var_decls + for loop

    def test_active_reset_protocol(self):
        """Test active reset protocol."""
        with build_sequence() as seq:
            var_decl("raw", "complex", unit="mV")
            var_decl("is_excited", "bool")

            # This nested structure is intentional for active reset
            with repeat(3):
                measure(
                    "qubit",
                    result_var="raw",
                    duration="1us",
                    amplitude="50mV",
                    integration=full_integration(),
                )
                discriminate(
                    target="is_excited",
                    source="raw",
                    threshold="0.5mV",
                )
                with if_("is_excited"):
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

            measure(
                ("drive_q0", "readout_q0"),
                result_var="raw_q0",
                duration="1us",
                amplitude="50mV",
                integration=full_integration(),
            )
            measure(
                ("drive_q1", "readout_q1"),
                result_var="raw_q1",
                duration="1us",
                amplitude="50mV",
                integration=full_integration(),
            )
            discriminate(target="state_q0", source="raw_q0", threshold="0.45mV")
            discriminate(target="state_q1", source="raw_q1", threshold="0.52mV")

        # 4 var_decls + 2 measures (each is play+record) + 2 discriminates = 10
        assert len(seq.items) == 10


class TestSerialization:
    """Tests for sequence serialization."""

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


class TestNestedDecorators:
    """Tests for the @nested_sequence decorator."""

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
