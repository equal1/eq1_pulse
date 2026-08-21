"""Builder state must not survive a sequence build, successful or otherwise.

Tracking state used to be keyed by ``id(context)`` and cleaned up only on the success
path, so a build that raised left entries behind. Because CPython reuses ``id`` values
once an object is collected, those entries could later attach themselves to an unrelated
build and fail it with a traceback pointing at long-finished code.
"""

import pytest

from eq1_pulse.builder import build_sequence, var, var_decl
from eq1_pulse.builder.core import _get_state


def _assert_state_is_clean():
    """Assert that no builder tracking state is left over."""
    state = _get_state()
    assert state.context_stack == []
    assert state.unconsumed_blocks == []
    assert state.declared_variables == []


def test_variables_do_not_leak_between_builds():
    """Test that a variable declared in one build is not visible in the next."""
    with build_sequence():
        var_decl("secret", "int")

    for _ in range(200):
        with build_sequence():
            with pytest.raises(RuntimeError, match="has not been declared"):
                var("secret")
    _assert_state_is_clean()
