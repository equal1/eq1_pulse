"""Example demonstrating zipped iteration in the builder interface.

Zipped iteration allows simultaneous iteration over multiple variables with
corresponding iterables, similar to Python's zip() function.
"""

from eq1_pulse.builder import (
    build_sequence,
    for_,
    full_integration,
    measure,
    play,
    square_pulse,
    var,
    var_decl,
)
from eq1_pulse.models import LinSpace, Range


def example_zipped_iteration_two_variables():
    """Example 1: Zipped iteration with two variables."""
    print("=" * 70)
    print("Example 1: Zipped Iteration with Two Variables")
    print("=" * 70)

    with build_sequence() as seq:
        # Declare loop variables
        var_decl("freq", "float", unit="MHz")
        var_decl("amp", "float", unit="mV")

        # Zipped iteration: iterate simultaneously over frequency and amplitude
        with for_(
            ["freq", "amp"],
            [
                range(4000, 4010),  # Frequency sweep from 4000 to 4009 MHz
                [10, 20, 30, 40, 50, 60, 70, 80, 90, 100],  # Corresponding amplitudes
            ],
        ):
            # Use variables in operations
            play("qubit", square_pulse(duration="100ns", amplitude=var("amp")))

    print(f"Created sequence with {len(seq.items)} items")
    print(seq.model_dump_json(indent=2))
    print()
    return seq


def example_zipped_iteration_three_variables():
    """Example 2: Zipped iteration with three variables using Range and LinSpace."""
    print("=" * 70)
    print("Example 2: Zipped Iteration with Range and LinSpace")
    print("=" * 70)

    with build_sequence() as seq:
        # Declare two loop variables
        var_decl("freq", "float", unit="MHz")
        var_decl("amp", "float", unit="mV")

        # Use Range and LinSpace for zipped iteration
        # Both must produce the same number of elements
        with for_(
            ["freq", "amp"],
            [
                Range(start=4000, stop=4008, step=2),  # 5 elements: 4000, 4002, 4004, 4006, 4008
                LinSpace(start=10, stop=100, num=5),  # 5 elements
            ],
        ):
            # Both variables are available inside the loop
            play("ch1", square_pulse(duration="100ns", amplitude=var("amp")))

    print(f"Created sequence with {len(seq.items)} items")
    print("Model structure (JSON):")
    print(seq.model_dump_json(indent=2))
    print()
    return seq


def example_zipped_iteration_with_measurements():
    """Example 3: Zipped iteration with three variables and measurements."""
    print("=" * 70)
    print("Example 3: Zipped Iteration with Three Variables")
    print("=" * 70)

    with build_sequence() as seq:
        var_decl("freq", "float", unit="MHz")
        var_decl("amp", "float", unit="mV")
        var_decl("phase", "float", unit="deg")
        var_decl("result", "complex", unit="mV")

        # Rabi experiment with variable frequency, amplitude, and phase
        num_steps = 5
        with for_(
            ["freq", "amp", "phase"],
            [
                LinSpace(start=4000, stop=4100, num=num_steps),
                LinSpace(start=10, stop=100, num=num_steps),
                [0, 90, 180, 270, 360],
            ],
        ):
            # Play pulse with variable parameters
            play("qubit", square_pulse(duration="100ns", amplitude=var("amp")))

            # Measure with full integration
            measure("qubit", result_var="result", duration="1us", amplitude="50mV", integration=full_integration())

    print(f"Created sequence with {len(seq.items)} items")
    print("Model structure (JSON):")
    print(seq.model_dump_json(indent=2))
    print()
    return seq


def example_single_iteration_compatibility():
    """Example 4: Single iteration still works as before."""
    print("=" * 70)
    print("Example 4: Single Variable Iteration (Backward Compatibility)")
    print("=" * 70)

    with build_sequence() as seq:
        var_decl("i", "int", unit="MHz")

        # Single variable iteration - unchanged behavior
        with for_("i", range(4000, 4100, 10)):
            play("qubit", square_pulse(duration="100ns", amplitude="50mV"))

    print(f"Created sequence with {len(seq.items)} items")
    print()
    return seq


if __name__ == "__main__":
    print("\n")
    print("*" * 70)
    print("ZIPPED ITERATION EXAMPLES")
    print("*" * 70)
    print("\n")

    example_zipped_iteration_two_variables()
    example_zipped_iteration_three_variables()
    example_zipped_iteration_with_measurements()
    example_single_iteration_compatibility()

    print("*" * 70)
    print("All examples completed successfully!")
    print("*" * 70)
