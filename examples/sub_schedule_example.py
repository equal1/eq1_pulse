"""Example demonstrating the use of sub_schedule for modular quantum programs.

This example shows how to use the sub_schedule context manager to create
reusable, composable blocks of operations in a schedule. Sub-schedules are
useful for organizing complex quantum programs into logical units.
"""

from eq1_pulse.builder import (
    build_schedule,
    play,
    record,
    set_frequency,
    square_pulse,
    sub_schedule,
    wait,
)


def example_basic_sub_schedule():
    """Basic example of using sub_schedule."""
    print("\n=== Basic Sub-Schedule Example ===")

    with build_schedule() as sched:
        # Create a simple sub-schedule
        with sub_schedule(name="init_block"):
            play("qubit", square_pulse(duration="100ns", amplitude="200mV"))
            wait("qubit", duration="50ns")

        # Add operation relative to the sub-schedule
        play(
            "qubit",
            square_pulse(duration="20ns", amplitude="150mV"),
            ref_op="init_block",
            ref_pt="end",
            rel_time="10ns",
        )

    print(f"Schedule has {len(sched.items)} items")
    print(f"First item: {sched.items[0].name} (sub-schedule)")
    print(f"Second item: {sched.items[1].name} (play operation)")
    return sched


def example_quantum_experiment_with_sub_schedules():
    """Example of a complete quantum experiment using sub-schedules."""
    print("\n=== Quantum Experiment with Sub-Schedules ===")

    with build_schedule() as main:
        # Initialization block
        with sub_schedule(name="initialization"):
            # Reset qubit to ground state
            play("qubit", square_pulse(duration="100ns", amplitude="200mV"))
            wait("qubit", duration="200ns")  # Relaxation time

        # Gate sequence block
        with sub_schedule(name="gates", ref_op="initialization", ref_pt="end", rel_time="50ns"):
            # Apply sequence of gates
            set_frequency("qubit", "5.1GHz")
            play("qubit", square_pulse(duration="20ns", amplitude="150mV"))  # X gate
            wait("qubit", duration="10ns")
            play("qubit", square_pulse(duration="10ns", amplitude="150mV"))  # Half X gate

        # Measurement block
        with sub_schedule(name="measurement", ref_op="gates", ref_pt="end", rel_time="100ns"):
            play("readout_drive", square_pulse(duration="1us", amplitude="50mV"))
            record("readout", var="result", duration="1us")

    print(f"Main schedule has {len(main.items)} sub-schedules/operations")
    print("Structure:")
    for i, item in enumerate(main.items):
        print(f"  {i + 1}. {item.name}: {type(item.op).__name__}")
        if hasattr(item, "ref_op") and item.ref_op:
            print(f"     → positioned relative to '{item.ref_op}' at {item.ref_pt}")

    return main


def example_parallel_operations_with_sub_schedules():
    """Example showing parallel execution with overlapping sub-schedules."""
    print("\n=== Parallel Operations with Sub-Schedules ===")

    with build_schedule() as parallel:
        # Qubit 1 operations - starts at t=0
        with sub_schedule(name="qubit1_ops"):
            play("qubit1", square_pulse(duration="50ns", amplitude="100mV"))
            wait("qubit1", duration="100ns")
            play("qubit1", square_pulse(duration="30ns", amplitude="80mV"))

        # Qubit 2 operations - starts at t=0 (parallel with qubit1)
        with sub_schedule(name="qubit2_ops", ref_pt_new="start"):
            wait("qubit2", duration="20ns")  # Small delay
            play("qubit2", square_pulse(duration="40ns", amplitude="120mV"))
            wait("qubit2", duration="80ns")
            play("qubit2", square_pulse(duration="40ns", amplitude="90mV"))

        # Synchronized measurement - after both qubits are done
        with sub_schedule(name="joint_measurement", ref_op="qubit1_ops", ref_pt="end", rel_time="50ns"):
            play("readout_drive1", square_pulse(duration="1us", amplitude="50mV"))
            play("readout_drive2", square_pulse(duration="1us", amplitude="50mV"))

    print(f"Schedule has {len(parallel.items)} blocks")
    print("Timeline:")
    for item in parallel.items:
        timing = f"ref_op={item.ref_op}, ref_pt={item.ref_pt}" if item.ref_op else "t=0 (start)"
        print(f"  - {item.name}: {timing}")

    return parallel


def example_reusable_sub_schedules():
    """Example showing how to create reusable sub-schedule patterns."""
    print("\n=== Reusable Sub-Schedule Patterns ===")

    # Define a common initialization pattern as a function
    def create_init_block(name, qubit_channel):
        """Create a reusable initialization sub-schedule."""
        with sub_schedule(name=name):
            play(qubit_channel, square_pulse(duration="100ns", amplitude="200mV"))
            wait(qubit_channel, duration="200ns")

    # Define a common measurement pattern
    def create_measurement_block(name, drive_channel, readout_channel, var_name, **timing):
        """Create a reusable measurement sub-schedule."""
        with sub_schedule(name=name, **timing):
            play(drive_channel, square_pulse(duration="1us", amplitude="50mV"))
            record(readout_channel, var=var_name, duration="1us")

    # Use the reusable patterns
    with build_schedule() as multi_qubit:
        # Initialize both qubits
        create_init_block("init_q0", "qubit0")
        create_init_block("init_q1", "qubit1")

        # Apply gates (example: just simple pulses)
        gate0 = play(
            "qubit0", square_pulse(duration="20ns", amplitude="150mV"), ref_op="init_q0", ref_pt="end", rel_time="50ns"
        )
        gate1 = play(
            "qubit1", square_pulse(duration="20ns", amplitude="150mV"), ref_op="init_q1", ref_pt="end", rel_time="50ns"
        )

        # Measure both qubits
        create_measurement_block(
            "meas_q0", "drive0", "readout0", "q0_result", ref_op=gate0, ref_pt="end", rel_time="100ns"
        )
        create_measurement_block(
            "meas_q1", "drive1", "readout1", "q1_result", ref_op=gate1, ref_pt="end", rel_time="100ns"
        )

    print(f"Multi-qubit schedule has {len(multi_qubit.items)} items")
    print("Using reusable patterns for:")
    print("  - 2 initialization blocks")
    print("  - 2 gate operations")
    print("  - 2 measurement blocks")

    return multi_qubit


if __name__ == "__main__":
    # Run all examples
    example_basic_sub_schedule()
    example_quantum_experiment_with_sub_schedules()
    example_parallel_operations_with_sub_schedules()
    example_reusable_sub_schedules()

    print("\n✓ All sub_schedule examples completed successfully!")
