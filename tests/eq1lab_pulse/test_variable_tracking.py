"""Tests for variable declaration tracking in the builder interface."""

import pytest

from eq1_pulse.builder import (
    build_sequence,
    discriminate,
    for_,
    if_,
    measure,
    play,
    record,
    repeat,
    square_pulse,
    store,
    sub_sequence,
    var,
    var_decl,
)
from eq1_pulse.models import VariableRef


class TestVariableDeclarationTracking:
    """Tests for variable declaration verification."""

    def test_var_without_decl_raises_error(self):
        """Test that referencing undeclared variable raises error."""
        with pytest.raises(RuntimeError, match="Variable 'x' has not been declared"):
            with build_sequence():
                # Try to use variable without declaring it
                var("x")

    def test_var_with_decl_succeeds(self):
        """Test that referencing declared variable succeeds."""
        with build_sequence():
            var_decl("x", "int")
            # Should not raise an error
            var_ref = var("x")
            assert var_ref.var == "x"

    def test_duplicate_var_decl_raises_error(self):
        """Test that declaring the same variable twice in same context raises error."""
        with pytest.raises(RuntimeError, match="Variable 'x' is already declared"):
            with build_sequence():
                var_decl("x", "int")
                var_decl("x", "float")  # Duplicate declaration

    def test_var_decl_in_nested_contexts(self):
        """Test that variables can be declared in nested contexts."""
        with build_sequence():
            var_decl("outer", "int")

            # Nested context can access outer variable
            with sub_sequence():
                var_ref = var("outer")
                assert var_ref.var == "outer"

                # Can declare new variable in nested context
                var_decl("inner", "float")
                var_ref_inner = var("inner")
                assert var_ref_inner.var == "inner"

            # Outer context can still access outer variable
            var_ref = var("outer")
            assert var_ref.var == "outer"

    def test_var_decl_shadowing_allowed_in_nested_context(self):
        """Test that variable shadowing is allowed in nested contexts."""
        with build_sequence():
            var_decl("x", "int")

            # Can redeclare same name in nested context (shadowing)
            with sub_sequence():
                var_decl("x", "float")  # This should be allowed
                var_ref = var("x")
                assert var_ref.var == "x"

    def test_var_in_control_flow(self):
        """Test variable usage in control flow structures."""
        with build_sequence():
            var_decl("i", "int")
            var_decl("result", "bool")

            # Variable used in for loop
            with for_("i", range(10)):
                # Can reference variables from parent context
                var_ref = var("i")
                assert var_ref.var == "i"

            # Variable used in conditional
            with if_("result"):
                var_ref = var("result")
                assert var_ref.var == "result"

    def test_var_in_operations(self):
        """Test variable usage in operations that accept variable references."""
        with build_sequence():
            var_decl("raw_data", "complex", unit="mV")
            var_decl("result", "bool")

            # These operations should succeed with declared variables
            discriminate(target="result", source="raw_data", threshold="0.5mV")
            store(key="data", source="raw_data")

    def test_undeclared_var_in_discriminate_raises_error(self):
        """Test that discriminate with undeclared source variable raises error."""
        with pytest.raises(RuntimeError, match="Variable 'undeclared' has not been declared"):
            with build_sequence():
                var_decl("result", "bool")
                discriminate(target="result", source="undeclared", threshold="0.5mV")

    def test_undeclared_var_in_store_raises_error(self):
        """Test that store with undeclared source variable raises error."""
        with pytest.raises(RuntimeError, match="Variable 'undeclared' has not been declared"):
            with build_sequence():
                store(key="data", source="undeclared")

    def test_undeclared_var_in_if_raises_error(self):
        """Test that if_ with undeclared condition variable raises error."""
        with pytest.raises(RuntimeError, match="Variable 'condition' has not been declared"):
            with build_sequence():
                with if_("condition"):
                    pass

    def test_undeclared_var_in_for_raises_error(self):
        """Test that for_ with undeclared loop variable raises error."""
        with pytest.raises(RuntimeError, match="Variable 'i' has not been declared"):
            with build_sequence():
                with for_("i", range(10)):
                    pass

    def test_var_scoping_with_repeat(self):
        """Test that variables declared in repeat blocks are scoped correctly."""
        with build_sequence():
            var_decl("outer", "int")

            with repeat(5):
                # Can access outer variable
                var_ref = var("outer")
                assert var_ref.var == "outer"

                # Can declare variable inside repeat
                var_decl("inner", "float")
                var_ref_inner = var("inner")
                assert var_ref_inner.var == "inner"

    def test_var_cleanup_after_context_exit(self):
        """Test that variable tracking is cleaned up after context exits."""
        # Build a sequence and exit it
        with build_sequence():
            var_decl("x", "int")
            var("x")  # Should work

        # Start a new sequence - should not have access to previous variable
        with pytest.raises(RuntimeError, match="Variable 'x' has not been declared"):
            with build_sequence():
                var("x")  # Should fail - different context


class TestVariableTrackingWithOperations:
    """Test variable tracking with real builder operations."""

    def test_measure_with_undeclared_result_var_raises_error(self):
        """Test that measure with undeclared result variable raises error."""
        from eq1_pulse.builder import demod_integration

        with pytest.raises(RuntimeError, match="Variable 'result' has not been declared"):
            with build_sequence():
                measure(
                    "readout",
                    result_var="result",
                    duration="1us",
                    amplitude="50mV",
                    integration=demod_integration(),
                )

    def test_record_with_undeclared_var_raises_error(self):
        """Test that record with undeclared variable raises error."""
        from eq1_pulse.builder import full_integration

        with pytest.raises(RuntimeError, match="Variable 'result' has not been declared"):
            with build_sequence():
                record(
                    "readout",
                    var="result",
                    duration="1us",
                    integration=full_integration(),
                )

    def test_complete_measurement_workflow(self):
        """Test complete measurement workflow with proper variable declarations."""
        from eq1_pulse.builder import demod_integration

        with build_sequence() as seq:
            # Declare all variables first
            var_decl("raw_data", "complex", unit="mV")
            var_decl("state", "bool")

            # Perform measurement
            measure(
                "readout",
                result_var="raw_data",
                duration="1us",
                amplitude="50mV",
                integration=demod_integration(),
            )

            # Discriminate result
            discriminate(target="state", source="raw_data", threshold="0.5mV")

            # Store result
            store(key="final_state", source="state")

            # Use result in conditional
            with if_("state"):
                play("qubit", square_pulse(duration="50ns", amplitude="100mV"))

        # Verify sequence was built successfully
        assert len(seq.items) > 0

    def test_iteration_with_proper_var_decl(self):
        """Test iteration with properly declared loop variable."""
        with build_sequence() as seq:
            var_decl("i", "int", unit="MHz")

            with for_("i", range(0, 100, 10)):
                # Operations using the loop variable should work
                from eq1_pulse.builder import set_frequency

                set_frequency("qubit", var("i"))

        # Verify sequence was built successfully
        assert len(seq.items) > 0


class TestVariableReferencesInBuilderFunctions:
    """Test variable reference support in builder functions (pulse, channel ops, play)."""

    def test_square_pulse_with_variable_duration(self):
        """Test square_pulse accepts variable reference for duration."""
        with build_sequence():
            var_decl("pulse_dur", "int")
            pulse = square_pulse(duration=var("pulse_dur"), amplitude="100mV")
            assert isinstance(pulse.duration, VariableRef)
            assert pulse.duration.var == "pulse_dur"

    def test_square_pulse_with_variable_duration_string(self):
        """Test square_pulse accepts identifier string for duration (converted to VariableRef)."""
        with build_sequence():
            var_decl("pulse_dur", "int")
            pulse = square_pulse(duration="pulse_dur", amplitude="100mV")
            assert isinstance(pulse.duration, VariableRef)
            assert pulse.duration.var == "pulse_dur"

    def test_square_pulse_with_variable_duration_dict(self):
        """Test square_pulse accepts dict with 'var' key for duration."""
        with build_sequence():
            var_decl("pulse_dur", "int")
            pulse = square_pulse(duration={"var": "pulse_dur"}, amplitude="100mV")
            assert isinstance(pulse.duration, VariableRef)
            assert pulse.duration.var == "pulse_dur"

    def test_square_pulse_with_literal_duration(self):
        """Test square_pulse still accepts literal duration strings."""
        from eq1_pulse.models import Duration

        with build_sequence():
            pulse = square_pulse(duration="10us", amplitude="100mV")
            # Literal strings get converted to model instances by Pydantic
            assert isinstance(pulse.duration, Duration)
            assert pulse.duration.us == 10

    def test_square_pulse_with_all_variable_params(self):
        """Test square_pulse with all parameters as variables."""
        with build_sequence():
            var_decl("dur", "int")
            var_decl("amp", "float")
            var_decl("rise", "int")
            var_decl("fall", "int")

            pulse = square_pulse(
                duration="dur",
                amplitude="amp",
                rise_time="rise",
                fall_time="fall",
            )

            assert isinstance(pulse.duration, VariableRef)
            assert pulse.duration.var == "dur"
            assert isinstance(pulse.amplitude, VariableRef)
            assert pulse.amplitude.var == "amp"
            assert isinstance(pulse.rise_time, VariableRef)
            assert pulse.rise_time.var == "rise"
            assert isinstance(pulse.fall_time, VariableRef)
            assert pulse.fall_time.var == "fall"

    def test_square_pulse_undeclared_variable_raises(self):
        """Test square_pulse raises error for undeclared variable."""
        with pytest.raises(RuntimeError, match="references undeclared variable 'undefined_dur'"):
            with build_sequence():
                square_pulse(duration="undefined_dur", amplitude="100mV")

    def test_sine_pulse_with_variable_params(self):
        """Test sine_pulse accepts variables for duration, amplitude, frequency."""
        from eq1_pulse.builder import sine_pulse

        with build_sequence():
            var_decl("dur", "int")
            var_decl("amp", "float")
            var_decl("freq", "float")

            pulse = sine_pulse(
                duration="dur",
                amplitude="amp",
                frequency="freq",
            )

            assert isinstance(pulse.duration, VariableRef)
            assert pulse.duration.var == "dur"
            assert isinstance(pulse.amplitude, VariableRef)
            assert pulse.amplitude.var == "amp"
            assert isinstance(pulse.frequency, VariableRef)
            assert pulse.frequency.var == "freq"

    def test_sine_pulse_with_variable_to_frequency(self):
        """Test sine_pulse accepts variable for to_frequency (chirp)."""
        from eq1_pulse.builder import sine_pulse

        with build_sequence():
            var_decl("freq_start", "float")
            var_decl("freq_end", "float")

            pulse = sine_pulse(
                duration="10us",
                amplitude="50mV",
                frequency="freq_start",
                to_frequency="freq_end",
            )

            assert isinstance(pulse.frequency, VariableRef)
            assert pulse.frequency.var == "freq_start"
            assert isinstance(pulse.to_frequency, VariableRef)
            assert pulse.to_frequency.var == "freq_end"

    def test_external_pulse_with_variable_params(self):
        """Test external_pulse accepts variables for duration and amplitude."""
        from eq1_pulse.builder import external_pulse

        with build_sequence():
            var_decl("dur", "int")
            var_decl("amp", "float")

            pulse = external_pulse(
                function="my_lib.pulse_func",
                duration="dur",
                amplitude="amp",
            )

            assert isinstance(pulse.duration, VariableRef)
            assert pulse.duration.var == "dur"
            assert isinstance(pulse.amplitude, VariableRef)
            assert pulse.amplitude.var == "amp"

    def test_external_pulse_with_variable_in_params(self):
        """Test external_pulse binds explicit variable references in its params dict."""
        from eq1_pulse.builder import external_pulse, var

        with build_sequence():
            var_decl("phase_val", "float")

            pulse = external_pulse(
                function="my_lib.pulse_func",
                duration="10us",
                amplitude="100mV",
                params={"phase": var("phase_val"), "beta": 0.5},
            )

            assert isinstance(pulse.params, dict)
            assert isinstance(pulse.params["phase"], VariableRef)
            assert pulse.params["phase"].var == "phase_val"
            assert pulse.params["beta"] == 0.5

    def test_external_pulse_params_keep_identifier_like_literals(self):
        """Test that plain strings in params stay literals, even when identifier-shaped."""
        from eq1_pulse.builder import external_pulse

        with build_sequence():
            pulse = external_pulse(
                function="my_lib.pulse_func",
                duration="10us",
                amplitude="100mV",
                params={"window": "hann", "interpolation": "cubic"},
            )

            assert pulse.params == {"window": "hann", "interpolation": "cubic"}

    def test_arbitrary_pulse_with_variable_params(self):
        """Test arbitrary_pulse accepts variables for duration and amplitude (not samples)."""
        from eq1_pulse.builder import arbitrary_pulse

        with build_sequence():
            var_decl("dur", "int")
            var_decl("amp", "float")

            pulse = arbitrary_pulse(
                duration="dur",
                amplitude="amp",
                samples=[0.0, 0.5, 1.0, 0.5, 0.0],
            )

            assert isinstance(pulse.duration, VariableRef)
            assert pulse.duration.var == "dur"
            assert isinstance(pulse.amplitude, VariableRef)
            assert pulse.amplitude.var == "amp"

    def test_wait_with_variable_duration(self):
        """Test wait() accepts variable reference for duration."""
        from eq1_pulse.builder import wait

        with build_sequence():
            var_decl("wait_time", "int")
            wait("qubit", duration="wait_time")
            # No exception should be raised

    def test_wait_with_literal_duration(self):
        """Test wait() still accepts literal duration."""
        from eq1_pulse.builder import wait

        with build_sequence():
            wait("qubit", duration="10us")
            # No exception should be raised

    def test_set_frequency_with_variable(self):
        """Test set_frequency() accepts variable reference."""
        from eq1_pulse.builder import set_frequency

        with build_sequence():
            var_decl("new_freq", "float")
            set_frequency("qubit", frequency="new_freq")
            # No exception should be raised

    def test_shift_frequency_with_variable(self):
        """Test shift_frequency() accepts variable reference."""
        from eq1_pulse.builder import shift_frequency

        with build_sequence():
            var_decl("freq_offset", "float")
            shift_frequency("qubit", frequency="freq_offset")
            # No exception should be raised

    def test_set_phase_with_variable(self):
        """Test set_phase() accepts variable reference."""
        from eq1_pulse.builder import set_phase

        with build_sequence():
            var_decl("new_phase", "float")
            set_phase("qubit", phase="new_phase")
            # No exception should be raised

    def test_shift_phase_with_variable(self):
        """Test shift_phase() accepts variable reference."""
        from eq1_pulse.builder import shift_phase

        with build_sequence():
            var_decl("phase_offset", "float")
            shift_phase("qubit", phase="phase_offset")
            # No exception should be raised

    def test_play_with_variable_scale_amp_as_varref(self):
        """Test play() accepts VariableRef for scale_amp."""
        with build_sequence():
            var_decl("scale_factor", "float")
            pulse = square_pulse(duration="10us", amplitude="100mV")
            play("qubit", pulse, scale_amp=var("scale_factor"))
            # No exception should be raised

    def test_play_with_variable_scale_amp_as_string(self):
        """Test play() accepts identifier string for scale_amp."""
        with build_sequence():
            var_decl("scale_factor", "float")
            pulse = square_pulse(duration="10us", amplitude="100mV")
            play("qubit", pulse, scale_amp="scale_factor")
            # No exception should be raised

    def test_play_with_variable_scale_amp_as_dict(self):
        """Test play() accepts dict with 'var' key for scale_amp."""
        with build_sequence():
            var_decl("scale_factor", "float")
            pulse = square_pulse(duration="10us", amplitude="100mV")
            play("qubit", pulse, scale_amp={"var": "scale_factor"})
            # No exception should be raised

    def test_play_with_numeric_scale_amp(self):
        """Test play() still accepts numeric scale_amp."""
        with build_sequence():
            pulse = square_pulse(duration="10us", amplitude="100mV")
            play("qubit", pulse, scale_amp=0.5)
            # No exception should be raised

    def test_play_with_variable_cond(self):
        """Test play() accepts variable reference for cond parameter."""
        with build_sequence():
            var_decl("condition", "bool")
            pulse = square_pulse(duration="10us", amplitude="100mV")
            play("qubit", pulse, cond="condition")
            # No exception should be raised

    def test_play_undeclared_scale_amp_raises(self):
        """Test play() raises error for undeclared scale_amp variable."""
        with pytest.raises(RuntimeError, match="references undeclared variable 'undefined_scale'"):
            with build_sequence():
                pulse = square_pulse(duration="10us", amplitude="100mV")
                play("qubit", pulse, scale_amp="undefined_scale")

    def test_play_undeclared_cond_raises(self):
        """Test play() raises error for undeclared cond variable."""
        with pytest.raises(RuntimeError, match="Variable 'undefined_cond' has not been declared"):
            with build_sequence():
                pulse = square_pulse(duration="10us", amplitude="100mV")
                play("qubit", pulse, cond="undefined_cond")

    def test_integration_conditional_with_variable_params(self):
        """Integration test: use variables in conditional with variable-based parameters."""
        with build_sequence() as seq:
            var_decl("condition", "bool")
            var_decl("freq", "float")

            with if_("condition"):
                from eq1_pulse.builder import set_frequency

                set_frequency("qubit", frequency="freq")

        # Verify sequence structure
        assert len(seq.items) > 0

    def test_nested_context_variable_scope(self):
        """Test that variables from outer contexts are accessible in nested contexts."""
        from eq1_pulse.builder import set_frequency

        with build_sequence() as seq:
            var_decl("outer_freq", "float")

            with repeat(3):
                # Should be able to use outer_freq here
                set_frequency("qubit", frequency="outer_freq")
                pulse = square_pulse(duration="10us", amplitude="50mV")
                play("qubit", pulse)

        # Verify sequence structure
        assert len(seq.items) > 0

    def test_mixed_literal_and_variable_params(self):
        """Test mixing literal values and variable references in same function."""
        from eq1_pulse.models import Duration

        with build_sequence():
            var_decl("amp_var", "float")

            pulse = square_pulse(
                duration="10us",  # literal
                amplitude="amp_var",  # variable
                rise_time="2us",  # literal
                fall_time="2us",  # literal
            )

            # Literals get converted to model instances
            assert isinstance(pulse.duration, Duration)
            assert pulse.duration.us == 10
            assert isinstance(pulse.amplitude, VariableRef)
            assert pulse.amplitude.var == "amp_var"
            assert isinstance(pulse.rise_time, Duration)
            assert pulse.rise_time.us == 2
