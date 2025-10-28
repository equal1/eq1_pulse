#!/usr/bin/env python3
"""Example demonstrating the measure_if integration in the builder interface.

This script shows how to use the measure_if context manager to perform
measurement, discrimination, and conditional execution in a streamlined way.
"""

# ruff: noqa: SIM117

import sys
from pathlib import Path

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eq1_pulse.builder import build


def example_basic_measure_if():
    """Example 1: Basic measure_if usage."""
    print("=" * 70)
    print("Example 1: Basic Measure-If")
    print("=" * 70)

    with build.sequence() as seq:
        # Measure, discriminate, and execute conditionally in one call
        with build.measure_if(
            "drive",
            "readout",
            "raw_data",
            "qubit_state",
            threshold="0.5mV",
            duration="1us",
            amplitude="50mV",
        ):
            # This block executes only if qubit_state is True (above threshold)
            build.play("qubit", build.square(duration="50ns", amplitude="100mV"))

    print(f"Created sequence with {len(seq.items)} operations")
    print(seq.model_dump_json(indent=2))
    print()
    return seq


def example_measure_if_with_rotation():
    """Example 2: Measure-if with phase rotation."""
    print("=" * 70)
    print("Example 2: Measure-If with Phase Rotation")
    print("=" * 70)

    with build.sequence() as seq:
        # Use phase rotation for better state separation
        with build.measure_if(
            "drive",
            "readout",
            "raw_iq",
            "excited_state",
            threshold="0.0mV",
            duration="1us",
            amplitude="50mV",
            integration="demod",
            rotation="45deg",  # Rotate IQ plane for optimal separation
            project="real",
        ):
            # Correction pulse if in excited state
            build.play(
                "qubit",
                build.square(duration="100ns", amplitude="100mV"),
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

    with build.sequence() as seq:
        # First measurement
        with build.measure_if(
            "drive_q0",
            "readout_q0",
            "raw_q0",
            "state_q0",
            threshold="0.5mV",
            duration="1us",
            amplitude="50mV",
        ):
            # If Q0 is excited, measure Q1
            with build.measure_if(
                "drive_q1",
                "readout_q1",
                "raw_q1",
                "state_q1",
                threshold="0.5mV",
                duration="1us",
                amplitude="50mV",
            ):
                # Both qubits excited - apply two-qubit gate
                build.play(
                    "coupler",
                    build.square(duration="200ns", amplitude="80mV"),
                )

    print(f"Created sequence with {len(seq.items)} operations")
    print(seq.model_dump_json(indent=2))
    print()
    return seq


def example_measure_and_discriminate_separate():
    """Example 4: Using measure_and_discriminate for manual control."""
    print("=" * 70)
    print("Example 4: Measure and Discriminate (Separate)")
    print("=" * 70)

    with build.sequence() as seq:
        # Perform measurement and discrimination
        build.measure_and_discriminate(
            "drive",
            "readout",
            "raw_result",
            "discriminated_state",
            threshold="0.5mV",
            duration="1us",
            amplitude="50mV",
        )

        # Manually create conditional - gives more control
        with build.if_condition("discriminated_state"):
            build.play("qubit", build.square(duration="50ns", amplitude="100mV"))

        # Can also do operations outside the conditional
        build.wait("qubit", duration="100ns")

    print(f"Created sequence with {len(seq.items)} operations")
    print(seq.model_dump_json(indent=2))
    print()
    return seq


def example_active_reset():
    """Example 5: Active reset using measure_if."""
    print("=" * 70)
    print("Example 5: Active Reset Protocol")
    print("=" * 70)

    with build.sequence() as seq:
        # Repeat measurement and reset until ground state
        with build.repeat(3):  # Max 3 attempts
            with build.measure_if(
                "drive",
                "readout",
                "raw_state",
                "is_excited",
                threshold="0.5mV",
                duration="1us",
                amplitude="50mV",
            ):
                # Apply pi pulse to flip back to ground state
                build.play("qubit", build.square(duration="50ns", amplitude="100mV"))

            # Wait between attempts
            build.wait("qubit", duration="1us")

    print(f"Created sequence with {len(seq.items)} operations")
    print(seq.model_dump_json(indent=2))
    print()
    return seq


def example_measure_if_in_schedule():
    """Example 6: Using measure_if in a schedule context."""
    print("=" * 70)
    print("Example 6: Measure-If in Schedule")
    print("=" * 70)

    with build.schedule() as sched:
        # In schedules, measure_if works with relative timing
        with build.measure_if(
            "drive",
            "readout",
            "raw",
            "state",
            threshold="0.5mV",
            duration="1us",
            amplitude="50mV",
            name="conditional_measure",
        ):
            # Conditional operations in schedule
            build.play(
                "qubit",
                build.square(duration="50ns", amplitude="100mV"),
                name="correction",
            )

    print(f"Created schedule with {len(sched.items)} operations")
    print(sched.model_dump_json(indent=2))
    print()
    return sched


def main():
    """Run all examples."""
    print()
    print("*" * 70)
    print("MEASURE-IF INTEGRATION EXAMPLES")
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
