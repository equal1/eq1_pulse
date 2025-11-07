"""Example demonstrating multi-channel wait operations in sequences.

This example shows how to use wait with multiple channels to synchronize
operations across different quantum channels.

Note: Multi-channel wait is only allowed in sequences, not schedules.
In schedules, wait can only be applied to a single channel because
multi-channel wait would have complex semantics (equivalent to a subschedule
where all channels idle), which contradicts the sequence definition where
wait time is appended independently to each channel.
"""

from eq1_pulse.builder import (
    barrier,
    build_sequence,
    play,
    square_pulse,
    wait,
)


def example_sequence_multi_channel_wait():
    """Example of multi-channel wait in a sequence."""
    print("\n=== Multi-Channel Wait in Sequence ===")

    with build_sequence() as seq:
        # Operations on different channels
        play("qubit0", square_pulse(duration="100ns", amplitude="200mV"))
        play("qubit1", square_pulse(duration="50ns", amplitude="150mV"))
        play("qubit2", square_pulse(duration="75ns", amplitude="180mV"))

        # Wait on all three channels simultaneously
        wait("qubit0", "qubit1", "qubit2", duration="200ns")

        # More operations after the wait
        play("qubit0", square_pulse(duration="20ns", amplitude="100mV"))
        play("qubit1", square_pulse(duration="20ns", amplitude="100mV"))
        play("qubit2", square_pulse(duration="20ns", amplitude="100mV"))

    print(f"Sequence has {len(seq.items)} items")
    print("Structure:")
    print("  - 3 play operations (one per qubit)")
    print("  - 1 multi-channel wait (all 3 qubits)")
    print("  - 3 more play operations")

    return seq


def example_barrier_vs_wait():
    """Example showing the difference between barrier and multi-channel wait."""
    print("\n=== Barrier vs Multi-Channel Wait ===")

    with build_sequence() as seq:
        # Different duration operations
        play("qubit0", square_pulse(duration="100ns", amplitude="200mV"))
        play("qubit1", square_pulse(duration="50ns", amplitude="150mV"))

        # Barrier: synchronizes channels (no additional time)
        # Both channels will wait until the slower one (qubit0) finishes
        barrier("qubit0", "qubit1")

        # After barrier, both start together
        play("qubit0", square_pulse(duration="30ns", amplitude="100mV"))
        play("qubit1", square_pulse(duration="30ns", amplitude="100mV"))

        # Multi-channel wait: adds fixed time to all channels
        wait("qubit0", "qubit1", duration="200ns")

        # Final operations
        play("qubit0", square_pulse(duration="20ns", amplitude="80mV"))
        play("qubit1", square_pulse(duration="20ns", amplitude="80mV"))

    print(f"Sequence has {len(seq.items)} items")
    print("Timeline:")
    print("  1. Two plays (different durations)")
    print("  2. Barrier - synchronizes both channels")
    print("  3. Two plays (same duration, start together)")
    print("  4. Wait 200ns on both channels")
    print("  5. Two final plays")

    return seq


def example_multi_qubit_measurement():
    """Example of multi-channel wait for synchronized measurement."""
    print("\n=== Multi-Qubit Synchronized Measurement ===")

    with build_sequence() as seq:
        # Apply gates to different qubits
        play("qubit0", square_pulse(duration="20ns", amplitude="150mV"))
        play("qubit1", square_pulse(duration="25ns", amplitude="160mV"))
        play("qubit2", square_pulse(duration="30ns", amplitude="170mV"))

        # Synchronize all qubits before measurement
        barrier("qubit0", "qubit1", "qubit2")

        # Wait a bit for coherence
        wait("qubit0", "qubit1", "qubit2", duration="50ns")

        # Perform simultaneous readout drives
        play("drive0", square_pulse(duration="1us", amplitude="50mV"))
        play("drive1", square_pulse(duration="1us", amplitude="50mV"))
        play("drive2", square_pulse(duration="1us", amplitude="50mV"))

    print(f"Sequence has {len(seq.items)} items")
    print("Workflow:")
    print("  1. Apply gates to all qubits (different durations)")
    print("  2. Barrier - wait for all gates to complete")
    print("  3. Multi-channel wait - coherence time")
    print("  4. Simultaneous readout on all qubits")

    return seq


if __name__ == "__main__":
    # Run all examples
    example_sequence_multi_channel_wait()
    example_barrier_vs_wait()
    example_multi_qubit_measurement()

    print("\n✓ All multi-channel wait examples completed successfully!")
