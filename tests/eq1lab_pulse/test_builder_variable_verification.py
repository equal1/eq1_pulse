"""Tests for variable declaration verification in the builder interface."""

import re

import pytest

from eq1_pulse.builder import (
    build_sequence,
    demod_integration,
    discriminate,
    ext,
    for_,
    if_,
    measure,
    play,
    record,
    repeat,
    set_frequency,
    square_pulse,
    store,
    var,
    var_decl,
)
from eq1_pulse.builder._state import _register_external


class TestVariableDeclarationVerification:
    """Tests for variable declaration verification."""

    def test_var_without_declaration_raises_error(self):
        """Test that using var() without declaring the variable raises an error."""
        with build_sequence():
            with pytest.raises(RuntimeError, match="Variable 'undeclared' has not been declared"):
                var("undeclared")

    def test_var_with_declaration_succeeds(self):
        """Test that using var() after declaring the variable succeeds."""
        with build_sequence():
            var_decl("my_var", "complex")
            # Should not raise
            result = var("my_var")
            assert result.var == "my_var"

    def test_variable_scoping_in_nested_contexts(self):
        """Test that variables are scoped to their declaration context and nested contexts."""
        with build_sequence():
            var_decl("outer_var", "int")

            # Variable should be accessible in parent context
            var("outer_var")

            # Variable should be accessible in nested repeat
            with repeat(5):
                var("outer_var")

                # Declare a variable in nested context
                var_decl("inner_var", "float")
                var("inner_var")

            # outer_var should still be accessible
            var("outer_var")

            # inner_var should NOT be accessible outside its context
            with pytest.raises(RuntimeError, match="Variable 'inner_var' has not been declared"):
                var("inner_var")

    def test_variable_in_for_loop(self):
        """Test that variables must be declared before use in for loops."""
        with build_sequence():
            # Variable must be declared before for_ loop
            var_decl("i", "int")

            with for_("i", range(10)):
                # Can use the declared variable inside the loop
                set_frequency("ch1", var("i"))

    def test_variable_in_conditional(self):
        """Test that condition variable must be declared before if_."""
        with build_sequence():
            var_decl("condition", "bool")

            with if_("condition"):
                play("ch1", square_pulse(duration="10us", amplitude="100mV"))

    def test_undeclared_variable_in_conditional_raises_error(self):
        """Test that using undeclared variable in if_ raises an error."""
        with build_sequence():
            # Note: if_ takes a VariableRefLike, so it may not immediately call var()
            # depending on how it's implemented. Let's test the actual usage.
            with pytest.raises(RuntimeError):
                # This should fail when if_ tries to process the variable
                with if_(var("undeclared")):
                    play("ch1", square_pulse(duration="10us", amplitude="100mV"))

    def test_variable_in_record_operation(self):
        """Test that variable used in record must be declared."""
        with build_sequence():
            # Should fail - variable not declared
            with pytest.raises(RuntimeError, match="Variable 'result' has not been declared"):
                record("ch1", var="result", duration="1us", integration=demod_integration())

    def test_variable_in_record_operation_succeeds_after_declaration(self):
        """Test that record works after variable declaration."""
        with build_sequence():
            var_decl("result", "complex", unit="mV")
            # Should succeed
            record("ch1", var="result", duration="1us", integration=demod_integration())

    def test_variable_in_discriminate_operation(self):
        """Test that variables in discriminate must be declared."""
        with build_sequence():
            # Declare source but not target
            var_decl("source_var", "complex")

            with pytest.raises(RuntimeError, match="Variable 'target_var' has not been declared"):
                discriminate(target=var("target_var"), source=var("source_var"), threshold="0.5mV")

    def test_variable_in_discriminate_operation_succeeds(self):
        """Test that discriminate works with both variables declared."""
        with build_sequence():
            var_decl("source_var", "complex", unit="mV")
            var_decl("target_var", "bool")

            # Should succeed
            discriminate(target=var("target_var"), source=var("source_var"), threshold="0.5mV")

    def test_variable_in_store_operation(self):
        """Test that variable used in store must be declared."""
        with build_sequence():
            with pytest.raises(RuntimeError, match="Variable 'data' has not been declared"):
                store("key", source=var("data"))

    def test_variable_in_store_operation_succeeds(self):
        """Test that store works after variable declaration."""
        with build_sequence():
            var_decl("data", "complex", unit="mV")
            # Should succeed
            store("key", source=var("data"))

    def test_measure_with_undeclared_variable_raises_error(self):
        """Test that measure with undeclared result variable raises error."""
        with build_sequence():
            with pytest.raises(RuntimeError):
                # This should fail when trying to use the undeclared variable
                measure(
                    "ch1", result_var=var("result"), duration="1us", amplitude="50mV", integration=demod_integration()
                )

    def test_measure_with_declared_variable_succeeds(self):
        """Test that measure works with declared result variable."""
        with build_sequence():
            var_decl("result", "complex", unit="mV")

            # Should succeed
            measure("ch1", result_var=var("result"), duration="1us", amplitude="50mV", integration=demod_integration())

    def test_complex_nested_scoping(self):
        """Test complex nested scoping scenario."""
        with build_sequence():
            var_decl("global_var", "int")

            with repeat(3):
                var("global_var")  # Should work

                var_decl("repeat_var", "float")

                with for_("global_var", range(5)):
                    var("global_var")  # Should work
                    var("repeat_var")  # Should work

                    var_decl("for_var", "complex")
                    var("for_var")  # Should work

                var("repeat_var")  # Should work

                # for_var is out of scope
                with pytest.raises(RuntimeError, match="Variable 'for_var' has not been declared"):
                    var("for_var")


class TestExternalSymbolDeclarationVerification:
    """Tests for external symbol declaration verification."""

    def test_ext_without_declaration_raises_error(self):
        """Test that using ext() without declaring the external symbol raises an error."""
        with build_sequence():
            with pytest.raises(RuntimeError, match=re.escape("External symbol 'q0.f01' has not been declared")):
                ext("q0.f01")

    def test_ext_with_declaration_succeeds(self):
        """Test that using ext() after declaring the external symbol succeeds."""
        with build_sequence():
            _register_external("q0.f01")
            # Should not raise
            result = ext("q0.f01")
            assert result.ext == "q0.f01"

    def test_external_symbol_scoping_in_nested_contexts(self):
        """Test that external symbols are scoped to their declaration context and nested contexts."""
        with build_sequence():
            _register_external("q0.f01")

            # External symbol should be accessible in parent context
            ext("q0.f01")

            # External symbol should be accessible in nested repeat
            with repeat(5):
                ext("q0.f01")

                # Declare an external symbol in nested context
                _register_external("q0.pi_amp")
                ext("q0.pi_amp")

            # q0.f01 should still be accessible
            ext("q0.f01")

            # q0.pi_amp should NOT be accessible outside its context
            with pytest.raises(RuntimeError, match=re.escape("External symbol 'q0.pi_amp' has not been declared")):
                ext("q0.pi_amp")
