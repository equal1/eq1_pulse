"""Builder interface for constructing pulse sequences and schedules.

This package provides a fluent API for creating pulse programs with:

- Global context for building models
- Context managers for sequences, schedules, iterations, and conditionals
- Function calls for operations like playing pulses, recording, and barriers
- Token-based references for relative positioning in schedules
- Shorthand functions for common pulse types
- Measure function for simultaneous play + record operations

Examples

.. code-block:: python

    from eq1_pulse.builder import *

    # Building a sequence
    with build_sequence() as seq:
        play("ch1", square_pulse(duration="10us", amplitude="100mV"))
        wait("ch1", "5us")
        play("ch1", sine_pulse(duration="20us", amplitude="50mV", frequency="5GHz"))

    # Building a schedule with relative positioning
    with build_schedule() as sched:
        op1 = play("ch1", square_pulse(duration="10us", amplitude="100mV"))
        op2 = play("ch2", square_pulse(duration="10us", amplitude="100mV"),
                        ref_op=op1, ref_pt="start", rel_time="5us")

    # Using control flow
    with build_sequence() as seq:
        with repeat(10):
            play("qubit", square_pulse(duration="50ns", amplitude="100mV"))
            measure("qubit", result_var="readout", duration="1us", amplitude="50mV")

        var_decl("i", "int", unit="MHz")
        with for_("i", range(0, 100, 10)):
            set_frequency("qubit", var("i"))
            play("qubit", square_pulse(duration="100ns", amplitude="50mV"))
"""

from .core import (
    arbitrary_pulse,
    barrier,
    build_schedule,
    build_sequence,
    channel,
    discriminate,
    external_pulse,
    for_,
    if_,
    measure,
    measure_and_discriminate,
    measure_and_discriminate_and_if_,
    play,
    pulse_ref,
    record,
    repeat,
    set_frequency,
    set_phase,
    shift_frequency,
    shift_phase,
    sine_pulse,
    square_pulse,
    store,
    var,
    var_decl,
    wait,
)
from .utils import OperationToken, ScheduleParams, resolve_schedule_params

__all__ = (
    "OperationToken",
    "ScheduleParams",
    "arbitrary_pulse",
    "barrier",
    "build_schedule",
    "build_sequence",
    "channel",
    "discriminate",
    "external_pulse",
    "for_",
    "if_",
    "measure",
    "measure_and_discriminate",
    "measure_and_discriminate_and_if_",
    "play",
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
    "var",
    "var_decl",
    "wait",
)
