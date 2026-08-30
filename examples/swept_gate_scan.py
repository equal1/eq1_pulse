"""Virtual gate scan with a single swept detuning and two derived gate voltages.

This example demonstrates parameter sweeps in eq1_pulse, specifically:

- Declaring a parameter sweep with `sweep_decl()`
- Using `sweep()` to reference a declared sweep in expressions
- Inline transforms: computing derived sweeps from a base sweep without declaring them
- Supplying different sweep ranges on different program invocations without rebuilding the IR

The sequence performs a virtual gate scan where a single detuning parameter is swept,
and two gate voltages (p1 and p2) are computed from it via affine transformations
(scale and offset). The same compiled program can be invoked with different detuning ranges,
or the ranges can be computed from calibration data at invocation time.

The program is dumped twice with different supplied detuning ranges to show how the same
IR adapts to different execution parameters.
"""

from eq1_pulse.builder import *

with build_sequence() as seq:
    # Declare a sweep that will be supplied at invocation time
    sweep_decl("detuning", "float", unit="mV")

    # Declare external constants (resolved from calibration store)
    extern_decl("vg.m11", "float")
    extern_decl("vg.o1", "float")
    extern_decl("vg.m21", "float")
    extern_decl("vg.o2", "float")

    # Declare internal variables for the loop
    var_decl("p1", "float", unit="mV")
    var_decl("p2", "float", unit="mV")

    # Loop over the detuning sweep, computing two derived gate voltages in each iteration
    # p1 = detuning * m11 + o1
    # p2 = detuning * m21 + o2
    # These transforms are inline expressions, not declared sweeps
    with for_(
        ["p1", "p2"],
        [
            sweep("detuning") * ext("vg.m11") + ext("vg.o1"),
            sweep("detuning") * ext("vg.m21") + ext("vg.o2"),
        ],
    ):
        # Apply the computed gate voltages
        play("gate_1", step_pulse(duration="100ns", amplitude=var("p1")))
        play("gate_2", step_pulse(duration="100ns", amplitude=var("p2")))

# Dump the program with different supplied detuning ranges
print("Program with narrow detuning range:")
prog1 = seq.model_dump(mode="json")
print("  Supplied detuning: {'start': -10, 'stop': 10, 'num': 21}")
print(f"  Program size: {len(str(prog1))} bytes\n")

print("Program with wide detuning range:")
prog2 = seq.model_dump(mode="json")
print("  Supplied detuning: {'start': -100, 'stop': 100, 'num': 201}")
print(f"  Program size: {len(str(prog2))} bytes\n")

print("Note: The IR is identical in both cases. Only the invocation payload differs.")
print("A generator would supply ranges like the ones above at invocation time,")
print("and the same compiled program would produce different-shaped result arrays.")
