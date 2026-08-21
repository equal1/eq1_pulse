"""Smoke test for the experimental schedule builder.

Builds a schedule end to end through :mod:`eq1_pulse.builder.experimental` only,
with no import from :mod:`eq1_pulse.builder.core`.
"""

from eq1_pulse.builder.experimental import (
    build_schedule,
    full_integration,
    measure,
    play,
    repeat,
    square_pulse,
    sub_schedule,
    var_decl,
)
from eq1_pulse.models.channel_ops import Play
from eq1_pulse.models.data_ops import VariableDecl
from eq1_pulse.models.experimental.schedule import RefPt, SchedRepetition, Schedule


def test_experimental_builder_end_to_end():
    """Exercise nested sub_schedule, a ref_op/ref_pt relation, repeat, and measure."""
    with build_schedule() as sched:
        var_decl("result", "complex", unit="mV")

        with sub_schedule(op_name="init") as init_token:
            play("qubit", square_pulse(duration="100ns", amplitude="200mV"))

        gate_token = play(
            "qubit",
            square_pulse(duration="20ns", amplitude="150mV"),
            ref_op=init_token,
            ref_pt="end",
            rel_time="10ns",
        )

        with repeat(3, ref_op=gate_token, ref_pt="end") as rep:
            measure(
                "qubit",
                result_var="result",
                duration="1us",
                amplitude="50mV",
                integration=full_integration(),
            )

    assert isinstance(sched, Schedule)
    assert len(sched.items) == 4

    var_op, init_op, gate_op, rep_op = sched.items

    assert isinstance(var_op.op, VariableDecl)
    assert var_op.op.name == "result"

    assert isinstance(init_op.op, Schedule)
    assert init_op.name == "init"
    assert len(init_op.op.items) == 1

    assert isinstance(gate_op.op, Play)
    assert gate_op.ref_op == "init"
    assert gate_op.ref_pt == RefPt.End

    assert isinstance(rep_op.op, SchedRepetition)
    assert rep_op.op is rep
    assert rep_op.ref_op == gate_token.name
    assert rep_op.ref_pt == RefPt.End
    assert rep_op.op.count == 3
    # measure() emits a play and a record inside the repetition body.
    assert len(rep_op.op.body.items) == 2
