"""Example demonstrating the @nested_schedule decorator.

The decorator allows you to create reusable, composable building blocks for
pulse programs without manually managing context managers.

.. warning::

    ``eq1_pulse.builder.experimental`` is unused and scheduled for removal
    (equal1/eq1_pulse#8). New code should use :mod:`eq1_pulse.builder`
    sequences and the ``@nested_sequence`` decorator instead -- see
    ``examples/nested_decorator_example.py``.
"""

from eq1_pulse.builder import experimental, full_integration, square_pulse

# ============================================================================
# Defining reusable blocks with @nested_schedule
# ============================================================================


@experimental.nested_schedule
def initialize_qubit(qubit: str):
    """Initialize a qubit to ground state."""
    experimental.play(qubit, square_pulse(duration="100ns", amplitude="200mV"))
    experimental.wait(qubit, duration="50ns")


@experimental.nested_schedule
def rabi_drive(qubit: str, amplitude: str):
    """Apply a Rabi drive pulse."""
    experimental.play(qubit, square_pulse(duration="50ns", amplitude=amplitude))


@experimental.nested_schedule
def measure_qubit(drive_ch: str, readout_ch: str, result_var: str):
    """Measure a qubit."""
    experimental.play(drive_ch, square_pulse(duration="1us", amplitude="50mV"))
    experimental.record(readout_ch, var=result_var, duration="1us", integration=full_integration())


def example_nested_schedule():
    """Example using @nested_schedule decorated functions in a schedule."""
    print("\n=== Using @nested_schedule in build_schedule ===")

    with experimental.build_schedule() as sched:
        # Declare variables that will be used in nested schedules
        experimental.var_decl("result", "complex", unit="mV")

        # Create blocks and add them with timing parameters using add_block()
        init_token = experimental.add_block(initialize_qubit("qubit0"), op_name="init")

        # Rabi pulse positioned after initialization
        rabi_token = experimental.add_block(
            rabi_drive("qubit0", "150mV"),
            op_name="rabi",
            ref_op=init_token,
            ref_pt="end",
            rel_time="10ns",
        )

        # Measurement positioned after Rabi pulse
        experimental.add_block(
            measure_qubit("drive0", "readout0", "result"),
            op_name="measure",
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

    return sched


# ============================================================================
# Parallel operations
# ============================================================================


@experimental.nested_schedule
def two_qubit_gate(control: str, target: str, angle: str):
    """Two-qubit controlled rotation gate."""
    experimental.play(control, square_pulse(duration="40ns", amplitude="100mV"))
    experimental.play(target, square_pulse(duration="40ns", amplitude="100mV"))
    experimental.shift_phase(target, angle)


def example_schedule_with_parallel_operations():
    """Example using schedule to run operations in parallel."""
    print("\n=== Schedule: Parallel Operations ===")

    with experimental.build_schedule() as sched:
        # Declare variables for measurement results
        experimental.var_decl("r0", "complex", unit="mV")
        experimental.var_decl("r1", "complex", unit="mV")

        # Initialize both qubits in parallel (same timing)
        init0 = experimental.add_block(initialize_qubit("qubit0"), op_name="init0")
        experimental.add_block(initialize_qubit("qubit1"), op_name="init1", ref_op=init0, ref_pt="start")

        # Apply gates in parallel
        gate0 = experimental.add_block(
            rabi_drive("qubit0", "140mV"), op_name="gate0", ref_op=init0, ref_pt="end", rel_time="20ns"
        )
        gate1 = experimental.add_block(
            two_qubit_gate("qubit0", "qubit1", "45deg"),
            op_name="cnot",
            ref_op=gate0,
            ref_pt="start",  # Start at same time as gate0
        )

        # Measure both (in parallel)
        meas0 = experimental.add_block(
            measure_qubit("drive0", "readout0", "r0"),
            ref_op=gate1,
            ref_pt="end",
            rel_time="100ns",
        )
        experimental.add_block(measure_qubit("drive1", "readout1", "r1"), ref_op=meas0, ref_pt="start")

    print(f"Schedule has {len(sched.items)} items")
    print("Timing structure:")
    print("  - qubit0 and qubit1 initialized at the same time (ref_pt='start')")
    print("  - Two-qubit gate starts when single-qubit gate starts")
    print("  - Both measurements start at the same time")

    return sched


if __name__ == "__main__":
    # Run all examples
    example_nested_schedule()
    example_schedule_with_parallel_operations()

    print("\n✓ All nested schedule examples completed successfully!")
