"""Tests for schedule parameter handling across the sequence/schedule builder split.

Sequence-side operations (``eq1_pulse.builder``) no longer accept schedule timing
parameters at all -- passing e.g. ``ref_op=`` to ``play()`` is a ``TypeError`` from the
call itself, not a runtime check. Schedule timing parameters remain fully supported by
``eq1_pulse.builder.experimental``.
"""

from eq1_pulse.builder import build_sequence, experimental, play, set_frequency, square_pulse, var_decl, wait


def test_operations_without_schedule_params_work_in_sequence():
    """Test that operations without schedule params work fine in sequences."""
    with build_sequence() as seq:
        play("ch1", square_pulse(duration="10us", amplitude="100mV"))
        wait("ch1", duration="5us")
        set_frequency("ch1", "5GHz")
        var_decl("result", "complex", unit="mV")

    # Should succeed
    assert len(seq.items) == 4


def test_operations_with_schedule_params_work_in_schedule():
    """Test that operations with schedule params work correctly in schedules."""
    with experimental.build_schedule() as sched:
        op1 = experimental.play("ch1", square_pulse(duration="10us", amplitude="100mV"))
        assert op1 is not None, "play() should return a token in schedule context"
        experimental.play("ch2", square_pulse(duration="5us", amplitude="50mV"), ref_op=op1, ref_pt="end")

    # Should succeed
    assert len(sched.items) == 2
    assert sched.items[1].ref_op == op1.name
