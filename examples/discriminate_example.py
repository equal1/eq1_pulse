#!/usr/bin/env python3
"""Example demonstrating the discriminate operation in the builder interface.

This script shows how to use the discriminate operation to convert measurement
results into binary outcomes for quantum state readout.
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
        # Perform measurement
        measure("drive", result_var="raw_result", duration="1us", amplitude="50mV")

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
    """Example 2: Discrimination with phase rotation and projection."""
    print("=" * 70)
    print("Example 2: Discriminate with Rotation and Projection")
    print("=" * 70)

    with build_sequence() as seq:
        # Perform measurement
        record(
            "readout",
            "iq_data",
            duration="1us",
            integration="demod",
            phase="0deg",
        )

        # Discriminate with phase rotation for optimal separation
        discriminate(
            target="state_0",
            source="iq_data",
            threshold="0.0mV",
            rotation="45deg",  # Rotate IQ plane for better separation
            compare=">=",
            project="real",  # Project to real axis after rotation
        )

        # Alternative: discriminate using magnitude
        discriminate(
            target="state_magnitude",
            source="iq_data",
            threshold="0.3mV",
            compare=">",
            project="abs",  # Use magnitude instead of real/imag
        )

    print(f"Created sequence with {len(seq.items)} operations")
    print(seq.model_dump_json(indent=2))
    print()
    return seq


def example_discriminate_in_schedule():
    """Example 3: Discrimination in a schedule context."""
    print("=" * 70)
    print("Example 3: Discriminate in Schedule")
    print("=" * 70)

    with build_schedule() as sched:
        var_decl("result", "complex", unit="mV")
        var_decl("bit", "bool")
        # Perform measurement
        meas_op = measure(
            ("drive", "readout"),
            result_var="result",
            duration="1us",
            amplitude="50mV",
            name="measurement",
        )

        # Discriminate immediately after measurement
        discriminate(
            target="bit",
            source="result",
            threshold="0.5mV",
            ref_op=meas_op,
            ref_pt="end",
            rel_time="100ns",  # Small delay after measurement
            name="discrimination",
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
        # Read out multiple qubits
        measure(("drive_q0", "readout_q0"), result_var="raw_q0", duration="1us", amplitude="50mV")
        measure(("drive_q1", "readout_q1"), result_var="raw_q1", duration="1us", amplitude="50mV")

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

    print("*" * 70)
    print("All examples completed successfully!")
    print("*" * 70)


if __name__ == "__main__":
    main()
