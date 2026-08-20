"""Unit tests for the _validate_or_pass_through helper function in builder.core."""

import pytest

from eq1_pulse.builder.core import _validate_or_pass_through
from eq1_pulse.models import Amplitude, Duration, Frequency, Phase, VariableRef


class TestValidateOrPassThrough:
    """Test suite for _validate_or_pass_through function."""

    def test_none_returns_none(self):
        """None input should return None without validation."""
        result = _validate_or_pass_through(None, param_name="test", context="test()")
        assert result is None

    def test_numeric_pass_through(self):
        """Numeric values should pass through unchanged."""
        assert _validate_or_pass_through(42, param_name="test", context="test()") == 42
        assert _validate_or_pass_through(3.14, param_name="test", context="test()") == 3.14
        assert _validate_or_pass_through(0, param_name="test", context="test()") == 0
        assert _validate_or_pass_through(-1.5, param_name="test", context="test()") == -1.5

    def test_boolean_pass_through(self):
        """Boolean values should pass through unchanged."""
        assert _validate_or_pass_through(True, param_name="test", context="test()") is True
        assert _validate_or_pass_through(False, param_name="test", context="test()") is False

    def test_model_instances_pass_through(self):
        """Model instances should pass through unchanged."""
        result: Frequency | Duration | Amplitude | Phase | VariableRef

        duration = Duration(us=10)
        result = _validate_or_pass_through(duration, param_name="duration", context="test()")
        assert result is duration

        freq = Frequency(GHz=5.0)
        result = _validate_or_pass_through(freq, param_name="frequency", context="test()")
        assert result is freq

        amp = Amplitude(mV=100)
        result = _validate_or_pass_through(amp, param_name="amplitude", context="test()")
        assert result is amp

        phase = Phase(rad=1.57)
        result = _validate_or_pass_through(phase, param_name="phase", context="test()")
        assert result is phase

    def test_variable_ref_instance_declared(self):
        """VariableRef instances should be validated if declared."""
        from eq1_pulse.builder import build_sequence, var, var_decl

        with build_sequence():
            var_decl("my_var", "int")
            v = var("my_var")
            result = _validate_or_pass_through(v, param_name="test", context="test()")
            assert isinstance(result, VariableRef)
            assert result.var == "my_var"

    def test_variable_ref_instance_undeclared_raises(self):
        """VariableRef instances referencing undeclared variables should raise RuntimeError."""
        from eq1_pulse.builder import build_sequence

        with build_sequence():
            var_ref = VariableRef(var="undeclared_var")
            with pytest.raises(RuntimeError, match="Variable 'undeclared_var' has not been declared"):
                _validate_or_pass_through(var_ref, param_name="test", context="test()")

    def test_identifier_string_declared(self):
        """Valid identifier strings referencing declared variables should return VariableRef."""
        from eq1_pulse.builder import build_sequence, var_decl

        with build_sequence():
            var_decl("my_var", "int")
            result = _validate_or_pass_through("my_var", param_name="test", context="test()")
            assert isinstance(result, VariableRef)
            assert result.var == "my_var"

    def test_identifier_string_undeclared_raises(self):
        """Valid identifier strings referencing undeclared variables should raise RuntimeError."""
        from eq1_pulse.builder import build_sequence

        with build_sequence():
            with pytest.raises(RuntimeError, match="references undeclared variable 'undeclared_var'"):
                _validate_or_pass_through("undeclared_var", param_name="test", context="test()")

    def test_non_identifier_string_pass_through(self):
        """Non-identifier strings (e.g., '10us') should pass through unchanged."""
        # Duration-like strings
        assert _validate_or_pass_through("10us", param_name="duration", context="test()") == "10us"
        assert _validate_or_pass_through("5ns", param_name="duration", context="test()") == "5ns"
        assert _validate_or_pass_through("1.5ms", param_name="duration", context="test()") == "1.5ms"

        # Frequency-like strings
        assert _validate_or_pass_through("4.5GHz", param_name="frequency", context="test()") == "4.5GHz"
        assert _validate_or_pass_through("100MHz", param_name="frequency", context="test()") == "100MHz"

        # Amplitude-like strings
        assert _validate_or_pass_through("50mV", param_name="amplitude", context="test()") == "50mV"
        assert _validate_or_pass_through("0.5V", param_name="amplitude", context="test()") == "0.5V"

        # Phase-like strings
        assert _validate_or_pass_through("1.57rad", param_name="phase", context="test()") == "1.57rad"
        assert _validate_or_pass_through("90deg", param_name="phase", context="test()") == "90deg"

    def test_dict_with_var_key_declared(self):
        """Dicts with 'var' key referencing declared variables should return VariableRef."""
        from eq1_pulse.builder import build_sequence, var_decl

        with build_sequence():
            var_decl("my_var", "int")
            result = _validate_or_pass_through({"var": "my_var"}, param_name="test", context="test()")
            assert isinstance(result, VariableRef)
            assert result.var == "my_var"

    def test_dict_with_var_key_undeclared_raises(self):
        """Dicts with 'var' key referencing undeclared variables should raise RuntimeError."""
        from eq1_pulse.builder import build_sequence

        with build_sequence():
            with pytest.raises(RuntimeError, match="Variable 'undeclared_var' has not been declared"):
                _validate_or_pass_through({"var": "undeclared_var"}, param_name="test", context="test()")

    def test_dict_without_var_key_pass_through(self):
        """Dicts without 'var' key should pass through unchanged."""
        dict_val = {"us": 10}
        result = _validate_or_pass_through(dict_val, param_name="duration", context="test()")
        assert result == dict_val

        dict_val2 = {"GHz": 5.0}
        result = _validate_or_pass_through(dict_val2, param_name="frequency", context="test()")  # type: ignore[arg-type]
        assert result == dict_val2

        dict_val3 = {"mV": 100, "other_key": "value"}
        result = _validate_or_pass_through(dict_val3, param_name="test", context="test()")  # type: ignore[arg-type]
        assert result == dict_val3

    def test_list_pass_through(self):
        """Lists should pass through unchanged."""
        list_val = [1, 2, 3, 4]
        result = _validate_or_pass_through(list_val, param_name="samples", context="test()")
        assert result is list_val

    def test_tuple_pass_through(self):
        """Tuples should pass through unchanged."""
        tuple_val = (1, 2, 3)
        result = _validate_or_pass_through(tuple_val, param_name="test", context="test()")
        assert result is tuple_val

    def test_error_message_includes_param_name_and_context(self):
        """Error messages should include parameter name and context."""
        from eq1_pulse.builder import build_sequence

        with build_sequence():
            with pytest.raises(RuntimeError) as exc_info:
                _validate_or_pass_through("undefined", param_name="duration", context="square_pulse()")

            error_msg = str(exc_info.value)
            assert "duration" in error_msg
            assert "square_pulse()" in error_msg
            assert "undefined" in error_msg

    def test_no_context_still_validates(self):
        """Validation should work without builder context (just won't find variables)."""
        # Outside any builder context, identifier strings should raise
        with pytest.raises(RuntimeError, match="references undeclared variable 'some_var'"):
            _validate_or_pass_through("some_var", param_name="test", context="test()")

    def test_variable_ref_invalid_identifier_raises(self):
        """VariableRef with invalid identifier should raise ValueError from model."""
        # Invalid identifiers should fail at VariableRef construction
        with pytest.raises(ValueError):
            VariableRef(var="123invalid")

        with pytest.raises(ValueError):
            VariableRef(var="invalid-name")

    def test_empty_string_pass_through(self):
        """Empty string should pass through (not a valid identifier)."""
        result = _validate_or_pass_through("", param_name="test", context="test()")
        assert result == ""

    def test_whitespace_string_pass_through(self):
        """Strings with whitespace should pass through (not valid identifiers)."""
        result = _validate_or_pass_through("10 us", param_name="test", context="test()")
        assert result == "10 us"

        result = _validate_or_pass_through("my var", param_name="test", context="test()")
        assert result == "my var"

    def test_nested_context_variable_lookup(self):
        """Variables should be found in nested contexts."""
        from eq1_pulse.builder import build_sequence, repeat, var_decl

        with build_sequence():
            var_decl("outer_var", "int")

            with repeat(5):
                result = _validate_or_pass_through("outer_var", param_name="test", context="test()")
                assert isinstance(result, VariableRef)
                assert result.var == "outer_var"

    def test_special_python_keywords_as_var_names(self):
        """Python keywords used as variable names should be handled."""
        from eq1_pulse.builder import build_sequence

        with build_sequence():
            # Python keywords are valid identifiers but we shouldn't allow them as variable names
            # This tests that str.isidentifier() passes but variable lookup fails
            with pytest.raises(RuntimeError, match="references undeclared variable 'for'"):
                _validate_or_pass_through("for", param_name="test", context="test()")

            with pytest.raises(RuntimeError, match="references undeclared variable 'if'"):
                _validate_or_pass_through("if", param_name="test", context="test()")

    def test_underscore_prefixed_identifiers(self):
        """Identifiers starting with underscore should be validated."""
        from eq1_pulse.builder import build_sequence, var_decl

        with build_sequence():
            var_decl("_private_var", "int")
            result = _validate_or_pass_through("_private_var", param_name="test", context="test()")
            assert isinstance(result, VariableRef)
            assert result.var == "_private_var"

    def test_unicode_identifiers(self):
        """Unicode identifiers should be supported."""
        from eq1_pulse.builder import build_sequence, var_decl

        with build_sequence():
            # Python allows unicode in identifiers
            var_decl("τ_delay", "int")
            result = _validate_or_pass_through("τ_delay", param_name="test", context="test()")
            assert isinstance(result, VariableRef)
            assert result.var == "τ_delay"

    def test_numeric_like_strings_with_units_pass_through(self):
        """Strings that look like numbers with units should pass through."""
        # Scientific notation with units
        assert _validate_or_pass_through("1e-6s", param_name="test", context="test()") == "1e-6s"
        assert _validate_or_pass_through("2.5e9Hz", param_name="test", context="test()") == "2.5e9Hz"

        # Negative numbers with units
        assert _validate_or_pass_through("-10mV", param_name="test", context="test()") == "-10mV"

        # Numbers with spaces
        assert _validate_or_pass_through("10 us", param_name="test", context="test()") == "10 us"
