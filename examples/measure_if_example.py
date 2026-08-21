#!/usr/bin/env python3
"""Example demonstrating measurement, discrimination, and conditional execution.

This script shows how to use measure, discriminate, and if_ to perform
measurement, discrimination, and conditional execution in pulse sequences.

NOTE: These examples are for illustration purposes only and demonstrate the
builder API syntax. Real experimental sequences would require calibrated
parameters, proper channel configuration, and integration with hardware backends.
"""

import sys
from pathlib import Path

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eq1_pulse.builder import *
from eq1_pulse.builder import experimental


def example_basic_measure_if():
    """Example 1: Basic measure, discriminate, and conditional execution."""
    print("=" * 70)
    print("Example 1: Basic Measure, Discriminate, and If")
    print("=" * 70)

    with build_sequence() as seq:
        var_decl("raw_data", "float", unit="mV")
        var_decl("qubit_state", "bool")
        # Measure, discriminate, and execute conditionally
        # Using full integration for simple magnitude measurement
        measure(
            "readout",  # Readout via sensor
            result_var="raw_data",
            duration="1us",
            amplitude="50mV",
            integration=full_integration(),
        )
        discriminate(
            target="qubit_state",
            source="raw_data",
            threshold="0.5mV",
        )
        with if_("qubit_state"):
            # This block executes only if qubit_state is True (above threshold)
            play("qubit", square_pulse(duration="50ns", amplitude="100mV"))

    print(f"Created sequence with {len(seq.items)} operations")
    print(seq.model_dump_json(indent=2))
    print()
    return seq


def example_measure_if_with_rotation():
    """Example 2: Measurement with phase rotation and discrimination."""
    print("=" * 70)
    print("Example 2: Measure with Phase Rotation")
    print("=" * 70)

    with build_sequence() as seq:
        var_decl("raw_iq", "complex", unit="mV")
        var_decl("excited_state", "bool")
        # Use phase rotation for better state separation
        measure(
            "qubit",
            result_var="raw_iq",
            duration="1us",
            amplitude="50mV",
            integration=demod_integration(),
        )
        discriminate(
            target="excited_state",
            source="raw_iq",
            threshold="0.0mV",
            rotation="45deg",  # Rotate IQ plane for optimal separation
            project="real",
        )
        with if_("excited_state"):
            # Correction pulse if in excited state
            play(
                "qubit",
                square_pulse(duration="100ns", amplitude="100mV"),
            )

    print(f"Created sequence with {len(seq.items)} operations")
    print(seq.model_dump_json(indent=2))
    print()
    return seq


def example_nested_measure_if():
    """Example 3: Nested conditional measurements."""
    print("=" * 70)
    print("Example 3: Nested Conditional Measurements")
    print("=" * 70)

    with build_sequence() as seq:
        var_decl("raw_q0", "complex", unit="mV")
        var_decl("state_q0", "bool")
        var_decl("raw_q1", "complex", unit="mV")
        var_decl("state_q1", "bool")
        # First measurement with demodulation
        measure(
            "readout_q0",
            result_var="raw_q0",
            duration="1us",
            amplitude="50mV",
            integration=demod_integration(),
        )
        discriminate(
            target="state_q0",
            source="raw_q0",
            threshold="0.5mV",
        )
        with if_("state_q0"):
            # If Q0 is excited, measure Q1
            measure(
                "readout_q1",
                result_var="raw_q1",
                duration="1us",
                amplitude="50mV",
                integration=demod_integration(),
            )
            discriminate(
                target="state_q1",
                source="raw_q1",
                threshold="0.5mV",
            )
            with if_("state_q1"):
                # Both qubits excited - apply two-qubit gate
                play(
                    "coupler",
                    square_pulse(duration="200ns", amplitude="80mV"),
                )

    print(f"Created sequence with {len(seq.items)} operations")
    print(seq.model_dump_json(indent=2))
    print()
    return seq


def example_measure_and_discriminate_separate():
    """Example 4: Using measure and discriminate separately for manual control."""
    print("=" * 70)
    print("Example 4: Measure and Discriminate (Separate)")
    print("=" * 70)

    with build_sequence() as seq:
        var_decl("raw_result", "complex", unit="mV")
        var_decl("discriminated_state", "bool")
        # Perform measurement and discrimination via sensor
        measure(
            "readout",
            result_var="raw_result",
            duration="1us",
            amplitude="50mV",
            integration=demod_integration(),
        )
        discriminate(
            target="discriminated_state",
            source="raw_result",
            threshold="0.5mV",
        )

        # Manually create conditional - gives more control
        with if_("discriminated_state"):
            play("qubit", square_pulse(duration="50ns", amplitude="100mV"))

        # Can also do operations outside the conditional
        wait("qubit", duration="100ns")

    print(f"Created sequence with {len(seq.items)} operations")
    print(seq.model_dump_json(indent=2))
    print()
    return seq


def example_active_reset():
    """Example 5: Active reset using measure, discriminate, and if_."""
    print("=" * 70)
    print("Example 5: Active Reset Protocol")
    print("=" * 70)

    with build_sequence() as seq:
        var_decl("raw_state", "complex", unit="mV")
        var_decl("is_excited", "bool")
        # Repeat measurement and reset until ground state
        with repeat(3):  # Max 3 attempts
            measure(
                "readout",
                result_var="raw_state",
                duration="1us",
                amplitude="50mV",
                integration=demod_integration(),
            )
            discriminate(
                target="is_excited",
                source="raw_state",
                threshold="0.5mV",
            )
            with if_("is_excited"):
                # Apply pi pulse to flip back to ground state
                play("qubit", square_pulse(duration="50ns", amplitude="100mV"))

            # Wait between attempts
            wait("qubit", duration="1us")

    print(f"Created sequence with {len(seq.items)} operations")
    print(seq.model_dump_json(indent=2))
    print()
    return seq


def example_measure_if_in_schedule():
    """Example 6: Using measure, discriminate, and if_ in a schedule context."""
    print("=" * 70)
    print("Example 6: Measure, Discriminate, If in Schedule")
    print("=" * 70)

    with experimental.build_schedule() as sched:
        experimental.var_decl("raw", "complex", unit="mV")
        experimental.var_decl("state", "bool")
        # In schedules, measure, discriminate, and if_ work with relative timing
        experimental.measure(
            "readout",
            result_var="raw",
            duration="1us",
            amplitude="50mV",
            integration=demod_integration(),
            op_name="measure_op",
        )
        experimental.discriminate(
            target="state",
            source="raw",
            threshold="0.5mV",
            op_name="discriminate_op",
        )
        with experimental.if_("state", op_name="conditional_measure"):
            # Conditional operations in schedule
            experimental.play(
                "qubit",
                square_pulse(duration="50ns", amplitude="100mV"),
                op_name="correction",
            )

    print(f"Created schedule with {len(sched.items)} operations")
    print(sched.model_dump_json(indent=2))
    print()
    return sched


def main():
    """Run all examples."""
    print()
    print("*" * 70)
    print("MEASURE, DISCRIMINATE, AND CONDITIONAL EXAMPLES")
    print("*" * 70)
    print()

    example_basic_measure_if()
    example_measure_if_with_rotation()
    example_nested_measure_if()
    example_measure_and_discriminate_separate()
    example_active_reset()
    example_measure_if_in_schedule()

    print("*" * 70)
    print("All examples completed successfully!")
    print("*" * 70)


if __name__ == "__main__":
    main()
