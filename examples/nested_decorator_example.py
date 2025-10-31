"""Example demonstrating the @nested_sequence and @nested_schedule decorators.

These decorators allow you to create reusable, composable building blocks for
pulse programs without manually managing context managers.
"""

from eq1_pulse.builder import (
    add_block,
    build_schedule,
    build_sequence,
    nested_schedule,
    nested_sequence,
    play,
    record,
    shift_phase,
    square_pulse,
    var_decl,
    wait,
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
    record(readout_ch, var=result_var, duration="1us")


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
# Defining reusable blocks with @nested_schedule
# ============================================================================


@nested_schedule
def initialize_qubit(qubit: str):
    """Initialize a qubit to ground state."""
    play(qubit, square_pulse(duration="100ns", amplitude="200mV"))
    wait(qubit, duration="50ns")


@nested_schedule
def rabi_drive(qubit: str, amplitude: str):
    """Apply a Rabi drive pulse."""
    play(qubit, square_pulse(duration="50ns", amplitude=amplitude))


@nested_schedule
def measure_qubit(drive_ch: str, readout_ch: str, result_var: str):
    """Measure a qubit."""
    play(drive_ch, square_pulse(duration="1us", amplitude="50mV"))
    record(readout_ch, var=result_var, duration="1us")


def example_nested_schedule():
    """Example using @nested_schedule decorated functions in a schedule."""
    print("\n=== Using @nested_schedule in build_schedule ===")

    with build_schedule() as sched:
        # Create blocks and add them with timing parameters using add_block()
        init_token = add_block(initialize_qubit("qubit0"), name="init")

        # Rabi pulse positioned after initialization
        rabi_token = add_block(
            rabi_drive("qubit0", "150mV"),
            name="rabi",
            ref_op=init_token,
            ref_pt="end",
            rel_time="10ns",
        )

        # Measurement positioned after Rabi pulse
        add_block(
            measure_qubit("drive0", "readout0", "result"),
            name="measure",
            ref_op=rabi_token,
            ref_pt="end",
            rel_time="50ns",
        )

    print(f"Schedule has {len(sched.items)} items")
    print("Structure:")
    print("  1. Initialization (sub-schedule named 'init')")
    print("  2. Rabi drive (sub-schedule named 'rabi', 10ns after init)")
    print("  3. Measurement (sub-schedule named 'measure', 50ns after rabi)")
    print("\nKey concept:")
    print("  - @nested_schedule functions return ScheduleBlock objects")
    print("  - Use add_block() to add them with timing parameters")
    print("  - add_block() returns a token for positioning subsequent operations")
    print("  3. Rabi drive (sub-schedule named 'rabi', 10ns after init)")
    print("  4. Measurement (sub-schedule named 'measure', 50ns after rabi)")

    return sched


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


@nested_schedule
def two_qubit_gate(control: str, target: str, angle: str):
    """Two-qubit controlled rotation gate."""
    play(control, square_pulse(duration="40ns", amplitude="100mV"))
    play(target, square_pulse(duration="40ns", amplitude="100mV"))
    shift_phase(target, angle)


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


def example_schedule_with_parallel_operations():
    """Example using schedule to run operations in parallel."""
    print("\n=== Schedule: Parallel Operations ===")

    with build_schedule() as sched:
        # Initialize both qubits in parallel (same timing)
        init0 = add_block(initialize_qubit("qubit0"), name="init0")
        add_block(initialize_qubit("qubit1"), name="init1", ref_op=init0, ref_pt="start")

        # Apply gates in parallel
        gate0 = add_block(rabi_drive("qubit0", "140mV"), name="gate0", ref_op=init0, ref_pt="end", rel_time="20ns")
        gate1 = add_block(
            two_qubit_gate("qubit0", "qubit1", "45deg"),
            name="cnot",
            ref_op=gate0,
            ref_pt="start",  # Start at same time as gate0
        )

        # Measure both (in parallel)
        meas0 = add_block(
            measure_qubit("drive0", "readout0", "r0"),
            ref_op=gate1,
            ref_pt="end",
            rel_time="100ns",
        )
        add_block(measure_qubit("drive1", "readout1", "r1"), ref_op=meas0, ref_pt="start")

    print(f"Schedule has {len(sched.items)} items")
    print("Timing structure:")
    print("  - qubit0 and qubit1 initialized at the same time (ref_pt='start')")
    print("  - Two-qubit gate starts when single-qubit gate starts")
    print("  - Both measurements start at the same time")

    return sched


if __name__ == "__main__":
    # Run all examples
    example_nested_sequence()
    example_nested_schedule()
    example_advanced_composition()
    example_schedule_with_parallel_operations()

    print("\n✓ All nested decorator examples completed successfully!")
