"""Tests for variable declaration tracking in the schedule builder interface."""

import pytest

from eq1_pulse.builder import experimental, var


class TestVariableDeclarationTracking:
    """Tests for variable declaration verification in schedule context."""

    def test_var_in_schedule_context(self):
        """Test variable tracking in schedule context."""
        with experimental.build_schedule():
            experimental.var_decl("x", "int")
            # Should work in schedule context
            var_ref = var("x")
            assert var_ref.var == "x"

    def test_duplicate_var_in_schedule_raises_error(self):
        """Test that duplicate variable declaration in schedule context raises error."""
        with pytest.raises(RuntimeError, match="Variable 'x' is already declared"):
            with experimental.build_schedule():
                experimental.var_decl("x", "int")
                experimental.var_decl("x", "float")  # Duplicate
