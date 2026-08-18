"""Builder state must not survive a build, successful or otherwise.

Tracking state used to be keyed by ``id(context)`` and cleaned up only on the success
path, so a build that raised left entries behind. Because CPython reuses ``id`` values
once an object is collected, those entries could later attach themselves to an unrelated
build and fail it with a traceback pointing at long-finished code.
"""

import pytest

from eq1_pulse.builder import (
    add_block,
    build_schedule,
    build_sequence,
    nested_schedule,
    play,
    repeat,
    square_pulse,
    var,
    var_decl,
)
from eq1_pulse.builder.core import _get_state

PULSE = {"duration": "100ns", "amplitude": "50mV"}


def _assert_state_is_clean():
    """Assert that no builder tracking state is left over."""
    state = _get_state()
    assert state.context_stack == []
    assert state.unconsumed_blocks == []
    assert state.declared_variables == []


def test_state_is_clean_after_a_successful_build():
    """Test that a normal build leaves nothing behind."""
    with build_schedule():
        var_decl("v", "int")
        play("q", square_pulse(**PULSE))
    _assert_state_is_clean()


def test_state_is_clean_after_a_failed_build():
    """Test that an exception mid-build still unwinds all tracking state."""
    with pytest.raises(ValueError, match="boom"):
        with build_schedule():
            var_decl("v", "int")
            play("q", square_pulse(**PULSE))
            raise ValueError("boom")
    _assert_state_is_clean()


def test_state_is_clean_after_a_failed_nested_build():
    """Test that failing deep inside nested contexts still unwinds everything."""
    with pytest.raises(ValueError, match="boom"):
        with build_schedule():
            with repeat(2):
                with repeat(3):
                    raise ValueError("boom")
    _assert_state_is_clean()


def test_unconsumed_block_does_not_leak_into_a_later_build():
    """Test that a block left over by a failed build cannot fail an unrelated one."""

    @nested_schedule
    def block(channel: str):
        play(channel, square_pulse(**PULSE))

    with pytest.raises(RuntimeError, match="unconsumed ScheduleBlock"):
        with build_schedule():
            block("q")  # created but never passed to add_block()
    _assert_state_is_clean()

    # An unrelated build afterwards must be unaffected, however ids get reused
    for _ in range(200):
        with build_schedule() as sched:
            play("q", square_pulse(**PULSE))
        assert len(sched.items) == 1
    _assert_state_is_clean()


def test_original_error_is_not_masked_by_the_unconsumed_block_check():
    """Test that an in-flight exception propagates rather than the block report."""

    @nested_schedule
    def block(channel: str):
        play(channel, square_pulse(**PULSE))

    with pytest.raises(ValueError, match="boom"):
        with build_schedule():
            block("q")  # would be reported as unconsumed on a clean exit
            raise ValueError("boom")
    _assert_state_is_clean()


def test_variables_do_not_leak_between_builds():
    """Test that a variable declared in one build is not visible in the next."""
    with build_sequence():
        var_decl("secret", "int")

    for _ in range(200):
        with build_sequence():
            with pytest.raises(RuntimeError, match="has not been declared"):
                var("secret")
    _assert_state_is_clean()


def test_generated_operation_names_are_reproducible():
    """Test that building the same schedule twice produces the same generated names."""
    names = []
    for _ in range(3):
        with build_schedule() as sched:
            play("q", square_pulse(**PULSE))
            play("q", square_pulse(**PULSE))
        names.append([item.name for item in sched.items])

    assert names[0] == ["op_1", "op_2"]
    assert names[0] == names[1] == names[2]


def test_add_block_returns_a_usable_token():
    """Test that add_block hands back a token that positions later operations."""

    @nested_schedule
    def block(channel: str):
        play(channel, square_pulse(**PULSE))

    with build_schedule() as sched:
        token = add_block(block("q"), op_name="init")
        follow_up = play("q", square_pulse(**PULSE), ref_op=token, ref_pt="end")

    assert token.name == "init"
    assert follow_up is not None
    assert follow_up.operation.ref_op == "init"
    assert len(sched.items) == 2
