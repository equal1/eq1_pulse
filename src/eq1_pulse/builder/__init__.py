"""Builder interface for constructing pulse sequences.

This package provides a fluent API for creating pulse programs with:

- Global context for building models
- Context managers for sequences, iterations, and conditionals
- Function calls for operations like playing pulses, recording, and barriers
- Shorthand functions for common pulse types
- Measure function for simultaneous play + record operations
- Sub-sequences for creating modular, reusable operation blocks

For the unused, experimental schedule API (explicit timing with reference points),
see :mod:`eq1_pulse.builder.experimental`.

Examples

.. code-block:: python

    from eq1_pulse.builder import *
    from eq1_pulse.models import LinSpace

    # Building a sequence
    with build_sequence() as seq:
        play("ch1", square_pulse(duration="10us", amplitude="100mV"))
        wait("ch1", duration="5us")
        play("ch1", sine_pulse(duration="20us", amplitude="50mV", frequency="5GHz"))

    # Using control flow in sequences
    with build_sequence() as seq:
        with repeat(10):
            play("qubit", square_pulse(duration="50ns", amplitude="100mV"))
            measure("qubit", result_var="readout", duration="1us", amplitude="50mV",
                    integration=full_integration())

        var_decl("i", "int", unit="MHz")
        with for_("i", LinSpace(0, 100, 10)):
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
"""

from .core import (
    arbitrary_pulse,
    barrier,
    build_sequence,
    channel,
    demod_integration,
    discriminate,
    ext,
    extern_decl,
    external_block,
    external_pulse,
    for_,
    full_integration,
    if_,
    measure,
    nested_sequence,
    param_decl,
    phase,
    play,
    pulse_decl,
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
    sub_sequence,
    var,
    var_decl,
    wait,
)

__all__ = (
    "arbitrary_pulse",
    "barrier",
    "build_sequence",
    "channel",
    "demod_integration",
    "discriminate",
    "ext",
    "extern_decl",
    "external_block",
    "external_pulse",
    "for_",
    "full_integration",
    "if_",
    "measure",
    "nested_sequence",
    "param_decl",
    "phase",
    "play",
    "pulse_decl",
    "pulse_ref",
    "record",
    "repeat",
    "set_frequency",
    "set_phase",
    "shift_frequency",
    "shift_phase",
    "sine_pulse",
    "square_pulse",
    "store",
    "sub_sequence",
    "var",
    "var_decl",
    "wait",
)
