"""Tests for variable declaration verification in the schedule builder interface."""

import pytest

from eq1_pulse.builder import demod_integration, experimental, var


class TestVariableDeclarationVerification:
    """Tests for variable declaration verification in schedule context."""

    def test_variable_in_schedule_context(self):
        """Test that variable verification works in schedule context."""
        with experimental.build_schedule():
            experimental.var_decl("my_var", "complex", unit="mV")

            # Should succeed
            experimental.record("ch1", var="my_var", duration="1us", integration=demod_integration())

    def test_undeclared_variable_in_schedule_raises_error(self):
        """Test that undeclared variable in schedule raises error."""
        with experimental.build_schedule():
            with pytest.raises(RuntimeError, match="Variable 'undeclared' has not been declared"):
                experimental.record("ch1", var=var("undeclared"), duration="1us", integration=demod_integration())
