"""Schedule-side builder API for constructing explicitly-timed pulse programs.

.. warning::

    This API is **unused** and scheduled for removal (equal1/eq1_pulse#8). It exists
    alongside :mod:`eq1_pulse.builder` only for one deprecation cycle. For actively
    supported code, build :class:`~eq1_pulse.models.sequence.OpSequence` programs with
    :mod:`eq1_pulse.builder` instead.

Examples

.. code-block:: python

    from eq1_pulse.builder.experimental import *

    with build_schedule() as sched:
        op1 = play("ch1", square_pulse(duration="10us", amplitude="100mV"))
        op2 = play("ch2", square_pulse(duration="10us", amplitude="100mV"),
                        ref_op=op1, ref_pt="start", rel_time="5us")
"""

from .._factories import (
    arbitrary_pulse,
    channel,
    demod_integration,
    external_pulse,
    full_integration,
    phase,
    pulse_ref,
    sine_pulse,
    square_pulse,
    var,
)
from .schedule import (
    ScheduleBlock,
    add_block,
    barrier,
    build_schedule,
    discriminate,
    for_,
    if_,
    measure,
    nested_schedule,
    play,
    pulse_decl,
    record,
    repeat,
    set_frequency,
    set_phase,
    shift_frequency,
    shift_phase,
    store,
    sub_schedule,
    var_decl,
    wait,
)
from .utils import OperationToken, ScheduleParams, resolve_schedule_params

__all__ = (
    "OperationToken",
    "ScheduleBlock",
    "ScheduleParams",
    "add_block",
    "arbitrary_pulse",
    "barrier",
    "build_schedule",
    "channel",
    "demod_integration",
    "discriminate",
    "external_pulse",
    "for_",
    "full_integration",
    "if_",
    "measure",
    "nested_schedule",
    "phase",
    "play",
    "pulse_decl",
    "pulse_ref",
    "record",
    "repeat",
    "resolve_schedule_params",
    "set_frequency",
    "set_phase",
    "shift_frequency",
    "shift_phase",
    "sine_pulse",
    "square_pulse",
    "store",
    "sub_schedule",
    "var",
    "var_decl",
    "wait",
)
