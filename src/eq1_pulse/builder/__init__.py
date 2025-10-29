"""Builder interface for constructing pulse sequences and schedules.

This package provides a fluent API for creating pulse programs with:

- Global context for building models
- Context managers for sequences, schedules, iterations, and conditionals
- Function calls for operations like playing pulses, recording, and barriers
- Token-based references for relative positioning in schedules
- Shorthand functions for common pulse types
- Measure function for simultaneous play + record operations
- Sub-schedules and sub-sequences for creating modular, reusable operation blocks

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

    # Using control flow in sequences
    with build_sequence() as seq:
        with repeat(10):
            play("qubit", square_pulse(duration="50ns", amplitude="100mV"))
            measure("qubit", result_var="readout", duration="1us", amplitude="50mV")

        var_decl("i", "int", unit="MHz")
        with for_("i", range(0, 100, 10)):
            set_frequency("qubit", var("i"))
            play("qubit", square_pulse(duration="100ns", amplitude="50mV"))

    # Using sub-sequences for modular composition in sequences
    with build_sequence() as seq:
        var_decl("readout", "complex", unit="mV")

        # Create reusable initialization block
        with sub_sequence():
            play("qubit", square_pulse(duration="100ns", amplitude="200mV"))
            wait("qubit", duration="50ns")

        # Main operation
        play("qubit", square_pulse(duration="20ns", amplitude="150mV"))

        # Measurement block
        with sub_sequence():
            play("drive", square_pulse(duration="1us", amplitude="50mV"))

    # Using sub-schedules for modular composition with timing
    with build_schedule() as main:
        # Create initialization block
        with sub_schedule(name="init"):
            play("qubit", square_pulse(duration="100ns", amplitude="200mV"))
            wait("qubit", duration="50ns")

        # Gate positioned after initialization
        gate = play("qubit", square_pulse(duration="20ns", amplitude="150mV"),
                   ref_op="init", ref_pt="end", rel_time="10ns")

        # Measurement block positioned after gate
        with sub_schedule(name="measure", ref_op=gate, ref_pt="end", rel_time="50ns"):
            play("drive", square_pulse(duration="1us", amplitude="50mV"))
            record("readout", var="result", duration="1us")
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
    sub_schedule,
    sub_sequence,
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
    "sub_schedule",
    "sub_sequence",
    "var",
    "var_decl",
    "wait",
)
