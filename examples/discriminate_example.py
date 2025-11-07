#!/usr/bin/env python3
"""Example demonstrating the discriminate operation in the builder interface.

This script shows how to use the discriminate operation to convert measurement
results into binary outcomes for quantum state readout.

Note:
    These examples are for illustration purposes only and may not represent
    realistic experimental parameters or physical hardware configurations.
"""

# ruff: noqa: SIM117 RUF100

import sys
from pathlib import Path

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eq1_pulse.builder import *


def example_basic_discriminate():
    """Example 1: Basic discrimination operation."""
    print("=" * 70)
    print("Example 1: Basic Discriminate")
    print("=" * 70)

    with build_sequence() as seq:
        var_decl("raw_result", "complex", unit="mV")
        var_decl("qubit_state", "bool")
        # Perform measurement via sensor (complex variable with demod)
        measure("readout", result_var="raw_result", duration="1us", amplitude="50mV", integration=demod_integration())

        # Discriminate the result to get a binary outcome
        discriminate(target="qubit_state", source="raw_result", threshold="0.5mV")

        # Use the discriminated result in a conditional
        with if_("qubit_state"):
            play("qubit", square_pulse(duration="50ns", amplitude="100mV"))

    print(f"Created sequence with {len(seq.items)} operations")
    print(seq.model_dump_json(indent=2))
    print()
    return seq


def example_discriminate_with_rotation():
    """Example 2: Discrimination with phase rotation and projection.

    Demonstrates different projection methods for discriminating measurement results:
    - 'real': Project to real axis (default)
    - 'magnitude': Use magnitude of complex signal (especially useful for spectroscopy)
    - rotation: Rotate IQ plane before projection for optimal state separation
    """
    print("=" * 70)
    print("Example 2: Discriminate with Rotation and Projection")
    print("=" * 70)

    with build_sequence() as seq:
        var_decl("iq_data", "complex", unit="mV")
        var_decl("state_real", "bool")
        var_decl("state_magnitude", "bool")

        # Perform measurement via sensor
        measure(
            "readout",
            result_var="iq_data",
            duration="1us",
            amplitude="50mV",
            integration=demod_integration(phase="0deg"),
        )

        # Method 1: Discriminate with phase rotation, then project to real axis
        discriminate(
            target="state_real",
            source="iq_data",
            threshold="0.0mV",
            rotation="45deg",  # Rotate IQ plane for better separation
            compare=">=",
            project="real",  # Project to real axis after rotation (default)
        )

        # Method 2: Discriminate using magnitude (especially useful for spectroscopy)
        # Magnitude projection is insensitive to phase noise
        discriminate(
            target="state_magnitude",
            source="iq_data",
            threshold="0.3mV",
            compare=">",
            project="abs",  # Use magnitude (absolute value) instead of real/imag
        )

    print(f"Created sequence with {len(seq.items)} operations")
    print(seq.model_dump_json(indent=2))
    print()
    return seq


def example_discriminate_in_schedule():
    """Example 3: Discrimination in a schedule context.

    Note: Variable declarations (var_decl) must be done outside the schedule context.
    This is a known limitation - variables should be declared before building the schedule.
    """
    print("=" * 70)
    print("Example 3: Discriminate in Schedule")
    print("=" * 70)

    with build_schedule() as sched:
        var_decl("result", "complex", unit="mV")
        var_decl("bit", "bool")

        # Perform measurement via sensor
        meas_op = measure(
            "readout",
            result_var="result",
            duration="1us",
            amplitude="50mV",
            integration=demod_integration(),
            op_name="measurement",
        )

        # Discriminate immediately after measurement
        discriminate(
            target="bit",
            source="result",
            threshold="0.5mV",
            ref_op=meas_op,
            ref_pt="end",
            rel_time="100ns",  # Small delay after measurement
            op_name="discrimination",
        )

    print(f"Created schedule with {len(sched.items)} operations")
    print(sched.model_dump_json(indent=2))
    print()
    return sched


def example_multi_qubit_readout():
    """Example 4: Multi-qubit readout with discrimination."""
    print("=" * 70)
    print("Example 4: Multi-Qubit Readout")
    print("=" * 70)

    with build_sequence() as seq:
        var_decl("raw_q0", "complex", unit="mV")
        var_decl("raw_q1", "complex", unit="mV")
        var_decl("state_q0", "bool")
        var_decl("state_q1", "bool")
        # Read out multiple qubits via separate sensors
        measure("readout_q0", result_var="raw_q0", duration="1us", amplitude="50mV", integration=demod_integration())
        measure("readout_q1", result_var="raw_q1", duration="1us", amplitude="50mV", integration=demod_integration())

        # Discriminate each qubit with potentially different thresholds
        discriminate(
            target="state_q0",
            source="raw_q0",
            threshold="0.45mV",
            rotation="0deg",
        )

        discriminate(
            target="state_q1",
            source="raw_q1",
            threshold="0.52mV",  # Different threshold for Q1
            rotation="30deg",  # Different rotation for Q1
        )

        # Conditional operations based on results
        with if_("state_q0"):
            play("qubit_0", square_pulse(duration="50ns", amplitude="100mV"))

        with if_("state_q1"):
            play("qubit_1", square_pulse(duration="50ns", amplitude="100mV"))

    print(f"Created sequence with {len(seq.items)} operations")
    print(seq.model_dump_json(indent=2))
    print()
    return seq


def example_spectroscopy_with_magnitude():
    """Example 5: Spectroscopy measurement using magnitude projection.

    Demonstrates using magnitude (abs) projection with demodulation integration
    for spectroscopy measurements. The scale_sin=-1 parameter inverts the sine
    component, and magnitude projection is especially useful when phase is not
    well-defined or varies.
    """
    print("=" * 70)
    print("Example 5: Spectroscopy with Magnitude Projection")
    print("=" * 70)

    with build_sequence() as seq:
        var_decl("spectroscopy_signal", "complex", unit="mV")
        var_decl("peak_detected", "bool")
        var_decl("freq", "float", unit="GHz")

        # Sweep frequency for spectroscopy
        from eq1_pulse.models.basic_types import LinSpace

        freq_sweep = LinSpace(start=4.0, stop=6.0, num=200)

        with for_("freq", freq_sweep):
            # Set frequency for spectroscopy
            set_frequency("qubit", var("freq"))

            # Apply spectroscopy pulse
            play("qubit", square_pulse(duration="10us", amplitude="20mV"))

            # Measure with demodulation
            # Using scale_sin=-1 inverts the sine component (Q quadrature)
            measure(
                "readout",
                result_var="spectroscopy_signal",
                duration="2us",
                amplitude="50mV",
                integration=demod_integration(phase="0deg", scale_cos=1, scale_sin=-1),
            )

            # Discriminate using magnitude projection
            # Magnitude is especially useful for spectroscopy as it's insensitive
            # to phase drift and gives the signal strength regardless of phase
            discriminate(
                target="peak_detected",
                source="spectroscopy_signal",
                threshold="1.0mV",
                project="abs",  # Use magnitude for phase-insensitive detection
                compare=">",
            )

            # Store results
            store("spectroscopy", "peak_detected", mode="average")

            # Wait for reset
            wait("qubit", duration="100us")

    print(f"Created sequence with {len(seq.items)} operations")
    print(seq.model_dump_json(indent=2))
    print()
    print("Key points:")
    print("- scale_sin=-1 inverts Q quadrature (useful for certain calibrations)")
    print("- magnitude projection (abs) gives phase-insensitive signal strength")
    print("- Ideal for spectroscopy where phase may vary or is not well-defined")
    print()
    return seq


def main():
    """Run all examples."""
    print()
    print("*" * 70)
    print("DISCRIMINATE OPERATION EXAMPLES")
    print("*" * 70)
    print()

    example_basic_discriminate()
    example_discriminate_with_rotation()
    example_discriminate_in_schedule()
    example_multi_qubit_readout()
    example_spectroscopy_with_magnitude()

    print("*" * 70)
    print("All examples completed successfully!")
    print("*" * 70)


if __name__ == "__main__":
    main()
