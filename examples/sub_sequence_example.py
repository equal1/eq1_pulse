"""Example demonstrating the use of sub_sequence for modular quantum programs.

This example shows how to use the sub_sequence context manager to create
reusable, composable blocks of operations in a sequence. Sub-sequences are
useful for organizing complex quantum programs into logical units.
"""

from eq1_pulse.builder import (
    build_sequence,
    for_,
    measure_and_discriminate_and_if_,
    play,
    repeat,
    square_pulse,
    sub_sequence,
    var_decl,
    wait,
)
from eq1_pulse.models import OpSequence


def example_basic_sub_sequence():
    """Basic example of using sub_sequence."""
    print("\n=== Basic Sub-Sequence Example ===")

    with build_sequence() as seq:
        var_decl("readout", "complex", unit="mV")

        # Create a simple sub-sequence for initialization
        with sub_sequence():
            play("qubit", square_pulse(duration="100ns", amplitude="200mV"))
            wait("qubit", duration="50ns")

        # Main operations
        play("qubit", square_pulse(duration="20ns", amplitude="150mV"))

        # Create a sub-sequence for measurement
        with sub_sequence():
            play("drive", square_pulse(duration="1us", amplitude="50mV"))

    print(f"Sequence has {len(seq.items)} items")
    print("Structure:")
    for i, item in enumerate(seq.items):
        item_type = type(item).__name__
        if isinstance(item, OpSequence):
            print(f"  {i + 1}. Sub-sequence with {len(item.items)} operations")
        else:
            print(f"  {i + 1}. {item_type}")

    return seq


def example_reusable_blocks():
    """Example showing reusable sub-sequences as functions."""
    print("\n=== Reusable Sub-Sequence Blocks ===")

    def init_block(qubit_channel):
        """Create a reusable initialization sub-sequence."""
        with sub_sequence():
            play(qubit_channel, square_pulse(duration="100ns", amplitude="200mV"))
            wait(qubit_channel, duration="200ns")

    def x_gate(qubit_channel):
        """Create a reusable X gate sub-sequence."""
        with sub_sequence():
            play(qubit_channel, square_pulse(duration="20ns", amplitude="150mV"))

    def half_x_gate(qubit_channel):
        """Create a reusable half-X gate sub-sequence."""
        with sub_sequence():
            play(qubit_channel, square_pulse(duration="10ns", amplitude="150mV"))

    # Build a sequence using the reusable blocks
    with build_sequence() as seq:
        var_decl("result", "complex", unit="mV")

        init_block("qubit")
        x_gate("qubit")
        wait("qubit", duration="50ns")
        half_x_gate("qubit")

    print(f"Sequence has {len(seq.items)} items")
    print("Using reusable blocks:")
    print("  - 1 var_decl")
    print("  - 1 init_block (sub-sequence)")
    print("  - 1 x_gate (sub-sequence)")
    print("  - 1 wait")
    print("  - 1 half_x_gate (sub-sequence)")

    return seq


def example_sub_sequence_in_loops():
    """Example of sub-sequences inside control flow."""
    print("\n=== Sub-Sequences in Control Flow ===")

    with build_sequence() as seq:
        var_decl("i", "int")
        var_decl("amplitude", "float", unit="mV")

        # Use sub-sequence inside a for loop
        with for_("i", range(5)):
            # Each iteration has a modular block
            with sub_sequence():
                play("qubit", square_pulse(duration="20ns", amplitude="100mV"))
                wait("qubit", duration="10ns")
                play("qubit", square_pulse(duration="10ns", amplitude="50mV"))

            # Additional operation after the block
            wait("qubit", duration="50ns")

    print(f"Sequence has {len(seq.items)} items")
    print("Structure:")
    print("  - 2 var_decl")
    print("  - 1 for_loop containing:")
    print("    - 1 sub-sequence (3 operations)")
    print("    - 1 wait")

    return seq


def example_nested_sub_sequences():
    """Example showing nested sub-sequences."""
    print("\n=== Nested Sub-Sequences ===")

    with build_sequence() as seq:
        var_decl("result", "complex", unit="mV")

        # Outer sub-sequence
        with sub_sequence():
            play("qubit", square_pulse(duration="50ns", amplitude="100mV"))

            # Inner sub-sequence
            with sub_sequence():
                wait("qubit", duration="10ns")
                play("qubit", square_pulse(duration="20ns", amplitude="80mV"))

            play("qubit", square_pulse(duration="30ns", amplitude="120mV"))

    print(f"Sequence has {len(seq.items)} items")
    print("Structure:")
    print("  - 1 var_decl")
    print("  - 1 outer sub-sequence containing:")
    print("    - 1 play")
    print("    - 1 inner sub-sequence (2 operations)")
    print("    - 1 play")

    # Verify structure
    outer_subseq = seq.items[1]
    assert isinstance(outer_subseq, OpSequence)
    print(f"\nOuter sub-sequence has {len(outer_subseq.items)} items")
    inner_subseq = outer_subseq.items[1]
    assert isinstance(inner_subseq, OpSequence)
    print(f"Inner sub-sequence has {len(inner_subseq.items)} items")

    return seq


def example_active_reset_with_sub_sequences():
    """Example of active reset protocol using sub-sequences."""
    print("\n=== Active Reset Protocol with Sub-Sequences ===")

    with build_sequence() as seq:
        var_decl("raw", "complex", unit="mV")
        var_decl("is_excited", "bool")

        # Active reset: repeat measurement and conditional reset
        with repeat(3):
            # Measurement block
            with sub_sequence():
                with measure_and_discriminate_and_if_(
                    "qubit",
                    raw_var="raw",
                    result_var="is_excited",
                    threshold="0.5mV",
                    duration="1us",
                    amplitude="50mV",
                ):
                    # If excited, apply correction pulse
                    play("qubit", square_pulse(duration="50ns", amplitude="100mV"))

            # Wait between attempts
            wait("qubit", duration="100ns")

    print(f"Sequence has {len(seq.items)} items")
    print("Structure:")
    print("  - 2 var_decl")
    print("  - 1 repeat block containing:")
    print("    - 1 sub-sequence (measurement + conditional)")
    print("    - 1 wait")

    return seq


def example_multi_qubit_with_sub_sequences():
    """Example of multi-qubit operations with sub-sequences."""
    print("\n=== Multi-Qubit Operations with Sub-Sequences ===")

    def qubit_operation_block(qubit_name):
        """Create a standard qubit operation block."""
        with sub_sequence():
            play(qubit_name, square_pulse(duration="100ns", amplitude="200mV"))
            wait(qubit_name, duration="50ns")
            play(qubit_name, square_pulse(duration="20ns", amplitude="150mV"))

    with build_sequence() as seq:
        # Apply the same operation block to multiple qubits
        qubit_operation_block("qubit0")
        qubit_operation_block("qubit1")
        qubit_operation_block("qubit2")

        # Global wait on all qubits
        wait("qubit0", "qubit1", "qubit2", duration="100ns")

    print(f"Sequence has {len(seq.items)} items")
    print("Structure:")
    print("  - 3 qubit operation sub-sequences")
    print("  - 1 multi-channel wait operation")

    return seq


if __name__ == "__main__":
    # Run all examples
    example_basic_sub_sequence()
    example_reusable_blocks()
    example_sub_sequence_in_loops()
    example_nested_sub_sequences()
    example_active_reset_with_sub_sequences()
    example_multi_qubit_with_sub_sequences()

    print("\n✓ All sub_sequence examples completed successfully!")
