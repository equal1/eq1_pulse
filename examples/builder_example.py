#!/usr/bin/env python3
"""Example demonstrating the builder interface for pulse sequences and schedules.

This script shows how to use the builder API to create pulse programs with:
- Simple sequences
- Schedules with relative positioning
- Control flow (loops, conditionals)
- Measurement operations

Note:
    String values like "10us" and "100mV" are used for readability in this example.
    In production code, you should use proper type constructors like Duration(us=10)
    or the models' automatic type conversion.
"""

# ruff: noqa: SIM117

import sys
from pathlib import Path

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eq1_pulse.builder import build


def example_simple_sequence():
    """Example 1: Creating a simple pulse sequence."""
    print("=" * 70)
    print("Example 1: Simple Sequence")
    print("=" * 70)

    with build.sequence() as seq:
        # Play a square pulse
        build.play("drive", build.square_pulse(duration="10us", amplitude="100mV"))

        # Wait
        build.wait("drive", duration="5us")

        # Play a sine pulse
        build.play("drive", build.sine_pulse(duration="20us", amplitude="50mV", frequency="5GHz"))

        # Barrier to synchronize channels
        build.barrier("drive", "readout")

    print(f"Created sequence with {len(seq.items)} operations")
    print(seq.model_dump_json(indent=2))
    print()
    return seq


def example_schedule_with_positioning():
    """Example 2: Creating a schedule with relative positioning."""
    print("=" * 70)
    print("Example 2: Schedule with Relative Positioning")
    print("=" * 70)

    with build.schedule() as sched:
        # First operation starts at default time
        op1 = build.play("qubit", build.square_pulse(duration="10us", amplitude="100mV"), name="drive_pulse")

        # Second operation starts 5us after the first one ends
        op2 = build.play(
            "qubit",
            build.square_pulse(duration="10us", amplitude="50mV"),
            ref_op=op1,
            ref_pt="end",
            rel_time="5us",
            name="second_pulse",
        )

        # Readout happens at the same time as second pulse
        build.wait("readout", duration="10us", ref_op=op2, ref_pt="start", ref_pt_new="start", rel_time=0)

    print(f"Created schedule with {len(sched.items)} operations")
    print(sched.model_dump_json(indent=2))
    print()
    return sched


def example_with_repetition():
    """Example 3: Using repetition (loop)."""
    print("=" * 70)
    print("Example 3: Repetition (Loop)")
    print("=" * 70)

    with build.sequence() as seq:
        # Repeat a pulse sequence 10 times
        with build.repeat(10):
            build.play("qubit", build.square_pulse(duration="50ns", amplitude="100mV"))
            build.wait("qubit", duration="50ns")

    print(f"Created sequence with {len(seq.items)} operation(s)")
    print(seq.model_dump_json(indent=2))
    print()
    return seq


def example_with_iteration():
    """Example 4: Using iteration (for loop)."""
    print("=" * 70)
    print("Example 4: Iteration (For Loop)")
    print("=" * 70)

    with build.sequence() as seq:
        # Iterate over frequency values
        with build.for_loop("freq", range(4000, 6000, 100)):
            build.set_frequency("qubit", build.var("freq"))
            build.play("qubit", build.square_pulse(duration="100ns", amplitude="50mV"))
            build.wait("qubit", duration="100ns")

    print(f"Created sequence with {len(seq.items)} operation(s)")
    print(seq.model_dump_json(indent=2))
    print()
    return seq


def example_with_conditional():
    """Example 5: Using conditional."""
    print("=" * 70)
    print("Example 5: Conditional")
    print("=" * 70)

    with build.sequence() as seq:
        # Measure first
        build.measure("qubit", "readout", "result", duration="1us", amplitude="50mV", integration="demod")

        # Conditionally apply correction based on result
        with build.if_condition("result"):
            build.play("qubit", build.square_pulse(duration="50ns", amplitude="100mV"))

    print(f"Created sequence with {len(seq.items)} operation(s)")
    print(seq.model_dump_json(indent=2))
    print()
    return seq


def example_measurement():
    """Example 6: Measurement (simultaneous play + record)."""
    print("=" * 70)
    print("Example 6: Measurement Operation")
    print("=" * 70)

    with build.sequence() as seq:
        # Simple measurement
        build.measure("qubit", "readout", "result", duration="1us", amplitude="50mV", integration="full")

        # Measurement with demodulation
        build.measure(
            "qubit", "readout", "result_demod", duration="1us", amplitude="50mV", integration="demod", phase="90deg"
        )

    print(f"Created sequence with {len(seq.items)} operation(s)")
    print(seq.model_dump_json(indent=2))
    print()
    return seq


def example_complex_program():
    """Example 7: Complex program combining multiple features."""
    print("=" * 70)
    print("Example 7: Complex Program")
    print("=" * 70)

    with build.sequence() as seq:
        # Initialize
        build.set_frequency("qubit", "5GHz")
        build.set_phase("qubit", "0deg")

        # Repeated Rabi experiment
        with build.repeat(100):
            # Sweep pulse amplitude
            with build.for_loop("amp", range(0, 200, 10)):
                # Apply pulse with variable amplitude
                amp_ref = build.var("amp")
                build.play("qubit", build.square_pulse(duration="100ns", amplitude="1mV"), scale_amp=amp_ref)

                # Measure
                build.measure("qubit", "readout", "measurement", duration="1us", amplitude="50mV")

                # Reset if needed
                with build.if_condition("measurement"):
                    build.play("qubit", build.square_pulse(duration="1us", amplitude="200mV"))

                # Wait between experiments
                build.wait("qubit", "readout", duration="10us")

    print(f"Created complex sequence with {len(seq.items)} operation(s)")
    print(seq.model_dump_json(indent=2))
    print()
    return seq


def main():
    """Run all examples."""
    print("\n")
    print("*" * 70)
    print("PULSE BUILDER INTERFACE EXAMPLES")
    print("*" * 70)
    print("\n")

    # Run all examples
    example_simple_sequence()
    example_schedule_with_positioning()
    example_with_repetition()
    example_with_iteration()
    example_with_conditional()
    example_measurement()
    example_complex_program()

    print("*" * 70)
    print("All examples completed successfully!")
    print("*" * 70)


if __name__ == "__main__":
    main()
