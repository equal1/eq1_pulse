"""Ramsey interferometry sequence with expression support.

This example demonstrates the use of expressions in eq1_pulse, specifically:

- Using `expr()` to wrap variables and external constants
- Arithmetic operations on expressions (addition, multiplication)
- `call_expr_()` for expression function calls (clamping a parameter with "min")
- `assign()` to compute a value once and store it under a variable name
- Expressions in pulse amplitude parameters (enabled by `SymbolValue` accepting complex voltages)
- Expressions in wait durations

The sequence performs a Ramsey experiment with a variable delay time, sweeping the delay
to measure decoherence (T2*) of the qubit.
"""

from eq1_pulse.builder import *
from eq1_pulse.models import Amplitude

with build_sequence() as seq:
    # Declare external constants (resolved from calibration store at submission time)
    extern_decl("q0.f01", "float", unit="GHz")

    # Declare parameters (supplied by caller at submission time)
    param_decl("detuning", "float", unit="MHz", default=0.0)
    param_decl("tau_step", "float", unit="ns")
    param_decl("scale", "float", default=1.0)

    # Declare internal variables
    var_decl("step", "int")
    var_decl("iq", "complex", unit="mV")
    var_decl("scale_clamped", "float")

    # Set frequency with expression: external constant plus parameter
    set_frequency("q0_drive", expr(ext("q0.f01")) + expr(var("detuning")))

    # Clamp the scale so a miscalibrated parameter can't overdrive the qubit, computing it once
    # and storing it under a name instead of repeating the expression at every use site
    assign("scale_clamped", call_expr_("min", var("scale"), 1.0))

    # Sweep delay time
    with for_("step", range(0, 50)):
        # Pulse amplitude is an expression: clamped scale times a literal amplitude
        pulse_decl("pi_half", square_pulse(duration="25ns", amplitude=expr(var("scale_clamped")) * Amplitude("80mV")))

        # Ramsey sequence: pi/2 - delay - pi/2
        play("q0_drive", pulse_ref("pi_half"))
        wait("q0_drive", duration=expr(var("step")) * expr(var("tau_step")))
        play("q0_drive", pulse_ref("pi_half"))

        # Measure
        measure(
            "q0_readout",
            result_var="iq",
            duration="1us",
            amplitude="50mV",
            integration=full_integration(),
        )

print(seq.model_dump_json(indent=2))
