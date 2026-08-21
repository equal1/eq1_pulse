"""Example demonstrating the @nested_sequence decorator.

The decorator allows you to create reusable, composable building blocks for
pulse programs without manually managing context managers.

See ``examples/experimental/nested_schedule_example.py`` for the equivalent
``@nested_schedule`` decorator, which lives under the unused, experimental
schedule API.
"""

from eq1_pulse.builder import (
    build_sequence,
    full_integration,
    nested_sequence,
    play,
    record,
    shift_phase,
    square_pulse,
    var_decl,
)

# ============================================================================
# Defining reusable blocks with @nested_sequence
# ============================================================================


@nested_sequence
def hadamard_gate(qubit: str):
    """Apply a Hadamard gate (simplified)."""
    play(qubit, square_pulse(duration="20ns", amplitude="100mV"))
    shift_phase(qubit, "90deg")
    play(qubit, square_pulse(duration="20ns", amplitude="100mV"))
    shift_phase(qubit, "-90deg")


@nested_sequence
def x_gate(qubit: str):
    """Apply an X gate."""
    play(qubit, square_pulse(duration="20ns", amplitude="150mV"))


@nested_sequence
def readout_sequence(drive_ch: str, readout_ch: str, result_var: str):
    """Perform readout measurement."""
    play(drive_ch, square_pulse(duration="1us", amplitude="50mV"))
    record(readout_ch, var=result_var, duration="1us", integration=full_integration())


def example_nested_sequence():
    """Example using @nested_sequence decorated functions in a sequence."""
    print("\n=== Using @nested_sequence in build_sequence ===")

    with build_sequence() as seq:
        var_decl("readout", "complex", unit="mV")

        # Use the decorated functions - they automatically create sub-sequences
        hadamard_gate("qubit0")
        x_gate("qubit0")
        hadamard_gate("qubit0")

        # Measurement block
        readout_sequence("drive0", "readout0", "readout")

    print(f"Sequence has {len(seq.items)} items")
    print("Structure:")
    print("  1. Variable declaration")
    print("  2. Hadamard gate (sub-sequence)")
    print("  3. X gate (sub-sequence)")
    print("  4. Hadamard gate (sub-sequence)")
    print("  5. Readout sequence (sub-sequence)")

    return seq


# ============================================================================
# Advanced: Parameterized building blocks
# ============================================================================


@nested_sequence
def bell_state_prep(qubit1: str, qubit2: str):
    """Prepare a Bell state between two qubits."""
    hadamard_gate(qubit1)  # Nested decorator calls work!
    # CNOT would go here (simplified)
    play(qubit1, square_pulse(duration="30ns", amplitude="120mV"))
    play(qubit2, square_pulse(duration="30ns", amplitude="120mV"))


def example_advanced_composition():
    """Example showing composition of decorated functions."""
    print("\n=== Advanced: Composing @nested decorated functions ===")

    with build_sequence() as seq:
        # Bell state preparation using nested decorator calls
        bell_state_prep("qubit0", "qubit1")

        # Multiple measurements
        var_decl("result0", "complex", unit="mV")
        var_decl("result1", "complex", unit="mV")
        readout_sequence("drive0", "readout0", "result0")
        readout_sequence("drive1", "readout1", "result1")

    print(f"Sequence has {len(seq.items)} items")
    print("Demonstrates:")
    print("  - Nested decorator calls (hadamard_gate inside bell_state_prep)")
    print("  - Reusing decorated functions multiple times")
    print("  - Mixing decorated and regular builder functions")

    return seq


if __name__ == "__main__":
    # Run all examples
    example_nested_sequence()
    example_advanced_composition()

    print("\n✓ All nested decorator examples completed successfully!")
