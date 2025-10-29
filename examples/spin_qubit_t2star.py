#!/usr/bin/env python3
"""T2* (dephasing time) measurement for spin qubits.

This script demonstrates how to implement T2* dephasing measurements
using the builder interface. T2* characterizes the inhomogeneous dephasing
time of a qubit, which includes both intrinsic decoherence and quasi-static
noise sources.

For spin qubits, T2* measurements are used to:
- Characterize charge noise and nuclear spin bath
- Optimize qubit operating points
- Assess qubit quality and identify noise sources
- Determine limits for gate operation fidelity

T2* is measured using a Ramsey experiment: π/2 - wait(τ) - π/2 - measure
The oscillating signal decays with characteristic time T2*.
"""

# ruff: noqa: SIM117

import sys
from pathlib import Path

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eq1_pulse.builder import *
from eq1_pulse.models.basic_types import LinSpace


def example_basic_t2star():
    """Example 1: Basic T2* (Ramsey) measurement.

    Standard Ramsey sequence to measure dephasing time.
    Applies π/2 - τ - π/2 sequence and sweeps the free evolution time τ.
    """
    print("=" * 70)
    print("Example 1: Basic T2* Ramsey Measurement")
    print("=" * 70)
    print("π/2 - wait(τ) - π/2 sequence to measure dephasing")
    print()

    with sequence() as seq:
        # Declare tau variable with unit
        var_decl("tau", "float", unit="us")

        # Sweep free evolution time from 0 to 10 μs in 100 steps
        delay_sweep = LinSpace(start=0.0, stop=10.0, num=100)

        with for_loop("tau", delay_sweep):
            # First π/2 pulse (superposition)
            play(
                "qubit",
                square_pulse(
                    duration="25ns",  # π/2 pulse duration
                    amplitude="80mV",  # Calibrated amplitude
                ),
            )

            # Free evolution time (variable)
            wait("qubit", duration=var("tau"))  # type: ignore[arg-type]  # tau in μs

            # Second π/2 pulse (projection)
            play(
                "qubit",
                square_pulse(
                    duration="25ns",
                    amplitude="80mV",
                ),
            )

            # Measurement and discrimination
            measure_and_discriminate(
                "qubit",
                "readout",
                "raw_result",
                "qubit_state",
                threshold="0.5mV",
                duration="1us",
                amplitude="50mV",
            )

            # Store result
            store("ramsey", "qubit_state", mode="average")

            # Wait for qubit to relax
            wait("qubit", duration="20us")

    print(f"Created sequence with {len(seq.items)} operations")
    print(seq.model_dump_json(indent=2))
    print()
    print("Expected result: Damped oscillation")
    print("T2*: Extract from exponential decay envelope")
    print("Detuning: Extract from oscillation frequency")
    print()
    return seq


def example_t2star_with_detuning():
    """Example 2: T2* measurement with intentional detuning.

    Add a known detuning to create faster oscillations, making it
    easier to observe both the oscillation frequency and decay.
    """
    print("=" * 70)
    print("Example 2: T2* with Detuning")
    print("=" * 70)
    print("Add detuning to observe oscillations more clearly")
    print()

    with sequence() as seq:
        # Declare tau variable with unit
        var_decl("tau", "float", unit="us")

        # Detuning from qubit resonance (in MHz)
        detuning = "5MHz"  # Creates oscillations at 5 MHz

        # Sweep delay time
        delay_sweep = LinSpace(start=0.0, stop=5.0, num=150)

        with for_loop("tau", delay_sweep):
            # Apply detuning
            shift_frequency("qubit", detuning)

            # π/2 pulse
            play(
                "qubit",
                square_pulse(duration="25ns", amplitude="80mV"),
            )

            # Free evolution
            wait("qubit", duration=var("tau"))  # type: ignore[arg-type]  # tau in μs

            # π/2 pulse
            play(
                "qubit",
                square_pulse(duration="25ns", amplitude="80mV"),
            )

            # Reset frequency
            shift_frequency("qubit", "-5MHz")

            # Measure
            measure_and_discriminate(
                "qubit",
                "readout",
                "raw_result",
                "qubit_state",
                threshold="0.5mV",
                duration="1us",
                amplitude="50mV",
            )

            # Store
            store("ramsey_detuned", "qubit_state", mode="average")

            # Wait
            wait("qubit", duration="20us")

    print(f"Created sequence with {len(seq.items)} operations")
    print(seq.model_dump_json(indent=2))
    print()
    print("Expected result: Oscillating signal with exponential decay")
    print("Oscillation frequency = detuning frequency")
    print()
    return seq


def example_t2star_echo():
    """Example 3: Spin echo (Hahn echo) for T2 measurement.

    Spin echo refocuses low-frequency noise to measure the intrinsic
    T2 time (> T2*). Sequence: π/2 - τ/2 - π - τ/2 - π/2
    """
    print("=" * 70)
    print("Example 3: Spin Echo (T2 measurement)")
    print("=" * 70)
    print("π/2 - τ/2 - π - τ/2 - π/2 to refocus slow noise")
    print()

    with sequence() as seq:
        # Declare tau variable with unit
        var_decl("tau", "float", unit="us")

        # Sweep total evolution time
        delay_sweep = LinSpace(start=0.0, stop=20.0, num=100)

        with for_loop("tau", delay_sweep):
            # First π/2 pulse
            play(
                "qubit",
                square_pulse(duration="25ns", amplitude="80mV"),
            )

            # Wait τ/2
            # Note: Would need tau/2 calculation in real implementation
            wait("qubit", duration=var("tau"))  # type: ignore[arg-type]  # tau/2 in μs

            # π pulse (refocusing)
            play(
                "qubit",
                square_pulse(
                    duration="50ns",  # Twice the π/2 duration
                    amplitude="80mV",
                ),
            )

            # Wait τ/2
            wait("qubit", duration=var("tau"))  # type: ignore[arg-type]  # tau/2 in μs

            # Final π/2 pulse
            play(
                "qubit",
                square_pulse(duration="25ns", amplitude="80mV"),
            )

            # Measure
            measure_and_discriminate(
                "qubit",
                "readout",
                "raw_result",
                "qubit_state",
                threshold="0.5mV",
                duration="1us",
                amplitude="50mV",
            )

            # Store
            store("echo", "qubit_state", mode="average")

            # Wait
            wait("qubit", duration="30us")

    print(f"Created sequence with {len(seq.items)} operations")
    print(seq.model_dump_json(indent=2))
    print()
    print("Expected result: Slower decay than T2* (T2 > T2*)")
    print("T2: Intrinsic decoherence time without low-frequency noise")
    print()
    return seq


def example_cpmg_sequence():
    """Example 4: CPMG (Carr-Purcell-Meiboom-Gill) for enhanced T2.

    Multiple π pulses to further suppress noise and measure T2.
    Sequence: π/2 - [τ/2 - π - τ/2]_n - π/2
    """
    print("=" * 70)
    print("Example 4: CPMG Sequence (Dynamical Decoupling)")
    print("=" * 70)
    print("Multiple refocusing pulses for noise suppression")
    print()

    with sequence() as seq:
        # Declare tau variable with unit
        var_decl("tau", "float", unit="us")

        # Number of refocusing pulses
        n_pulses = [1, 2, 4, 8, 16]

        # Sweep evolution time
        delay_sweep = LinSpace(start=0.0, stop=50.0, num=50)

        with for_loop("n", n_pulses):
            with for_loop("tau", delay_sweep):
                # Initial π/2 pulse
                play(
                    "qubit",
                    square_pulse(duration="25ns", amplitude="80mV"),
                )

                # Apply n refocusing pulses
                # Note: In real implementation, would repeat based on n
                with repeat(16):  # Max number
                    # Wait τ/(2n)
                    wait("qubit", duration="100ns")  # Simplified

                    # π pulse
                    play(
                        "qubit",
                        square_pulse(duration="50ns", amplitude="80mV"),
                    )

                    # Wait τ/(2n)
                    wait("qubit", duration="100ns")

                # Final π/2 pulse
                play(
                    "qubit",
                    square_pulse(duration="25ns", amplitude="80mV"),
                )

                # Measure
                measure_and_discriminate(
                    "qubit",
                    "readout",
                    "raw_result",
                    "qubit_state",
                    threshold="0.5mV",
                    duration="1us",
                    amplitude="50mV",
                )

                # Store
                store("cpmg", "qubit_state", mode="average")

                # Wait
                wait("qubit", duration="50us")

    print(f"Created sequence with {len(seq.items)} operations")
    print(seq.model_dump_json(indent=2))
    print()
    print("Expected result: Extended coherence time with more pulses")
    print("Useful for identifying noise spectrum")
    print()
    return seq


def example_t2star_vs_magnetic_field():
    """Example 5: T2* as a function of magnetic field.

    Sweep both delay time and magnetic field to map out
    the dephasing landscape and find optimal operating points.
    """
    print("=" * 70)
    print("Example 5: T2* vs Magnetic Field")
    print("=" * 70)
    print("2D map to find optimal operating point (sweet spot)")
    print()

    with sequence() as seq:
        # Declare variables with units
        var_decl("field", "float", unit="mT")
        var_decl("tau", "float", unit="us")

        # Magnetic field sweep (arbitrary units or field values)
        field_sweep = LinSpace(start=-10.0, stop=10.0, num=20)

        # Delay sweep
        delay_sweep = LinSpace(start=0.0, stop=10.0, num=80)

        with for_loop("field", field_sweep):
            # Set magnetic field via some control channel
            # (implementation-specific)
            set_frequency("qubit", var("field"))  # type: ignore[arg-type]  # Proxy for B-field

            with for_loop("tau", delay_sweep):
                # Ramsey sequence
                # π/2 pulse
                play(
                    "qubit",
                    square_pulse(duration="25ns", amplitude="80mV"),
                )

                # Free evolution
                wait("qubit", duration=var("tau"))  # type: ignore[arg-type]  # tau in μs

                # π/2 pulse
                play(
                    "qubit",
                    square_pulse(duration="25ns", amplitude="80mV"),
                )

                # Measure
                measure_and_discriminate(
                    "qubit",
                    "readout",
                    "raw_result",
                    "qubit_state",
                    threshold="0.5mV",
                    duration="1us",
                    amplitude="50mV",
                )

                # Store
                store("t2_vs_field", "qubit_state", mode="average")

                # Wait
                wait("qubit", duration="20us")

    print(f"Created sequence with {len(seq.items)} operations")
    print(seq.model_dump_json(indent=2))
    print()
    print("Expected result: 2D map showing T2* variation with field")
    print("Sweet spots: Local maxima in T2* where noise is minimized")
    print()
    return seq


def example_phase_tomography():
    """Example 6: Phase tomography to extract full qubit state.

    Measure in different bases by varying the phase of the final π/2 pulse.
    This gives more information than just Z-basis measurement.
    """
    print("=" * 70)
    print("Example 6: Phase Tomography During Ramsey")
    print("=" * 70)
    print("Measure qubit state in different bases")
    print()

    with sequence() as seq:
        # Declare variables with units
        var_decl("tau", "float", unit="us")
        var_decl("phi", "float", unit="deg")

        # Delay sweep
        delay_sweep = LinSpace(start=0.0, stop=5.0, num=50)

        # Phase sweep for tomography
        phase_sweep = LinSpace(start=0.0, stop=360.0, num=8)

        with for_loop("tau", delay_sweep):
            with for_loop("phi", phase_sweep):
                # First π/2 pulse
                play(
                    "qubit",
                    square_pulse(duration="25ns", amplitude="80mV"),
                )

                # Free evolution
                wait("qubit", duration=var("tau"))  # type: ignore[arg-type]  # tau in μs

                # Set phase for second pulse
                set_phase("qubit", var("phi"))  # type: ignore[arg-type]  # phi in degrees

                # Second π/2 pulse with phase
                play(
                    "qubit",
                    square_pulse(duration="25ns", amplitude="80mV"),
                )

                # Reset phase
                set_phase("qubit", "0deg")

                # Measure
                measure_and_discriminate(
                    "qubit",
                    "readout",
                    "raw_result",
                    "qubit_state",
                    threshold="0.5mV",
                    duration="1us",
                    amplitude="50mV",
                )

                # Store
                store("tomography", "qubit_state", mode="average")

                # Wait
                wait("qubit", duration="20us")

    print(f"Created sequence with {len(seq.items)} operations")
    print(seq.model_dump_json(indent=2))
    print()
    print("Expected result: Complete qubit state evolution on Bloch sphere")
    print("Extract both amplitude and phase of coherences")
    print()
    return seq


def main():
    """Run all T2* measurement examples."""
    print()
    print("*" * 70)
    print("T2* DEPHASING MEASUREMENTS FOR SPIN QUBITS")
    print("*" * 70)
    print()
    print("These examples demonstrate coherence time characterization")
    print("experiments using the builder interface.")
    print()

    example_basic_t2star()
    example_t2star_with_detuning()
    example_t2star_echo()
    example_cpmg_sequence()
    example_t2star_vs_magnetic_field()
    example_phase_tomography()

    print("*" * 70)
    print("All T2* measurement examples completed!")
    print("*" * 70)
    print()
    print("Key insights:")
    print("- T2* measures dephasing from all noise sources")
    print("- T2 (from echo) > T2* (pure dephasing without low-freq noise)")
    print("- CPMG extends T2 by suppressing more noise")
    print("- Sweet spots minimize dephasing")
    print()
    print("Next steps:")
    print("- Fit decay curves to extract T2* and T2")
    print("- Identify noise sources from field dependence")
    print("- Optimize qubit operating point")
    print("- Implement dynamical decoupling for longer coherence")
    print()


if __name__ == "__main__":
    main()
