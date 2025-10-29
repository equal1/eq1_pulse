#!/usr/bin/env python3
"""Rabi oscillation experiment for spin qubits.

This script demonstrates how to implement Rabi oscillation measurements
using the builder interface. Rabi oscillations characterize the coupling
strength between a qubit and a driving field by sweeping the drive amplitude
or duration while measuring the excited state population.

For spin qubits, Rabi oscillations are used to:
- Calibrate π and π/2 pulses
- Measure the Rabi frequency (proportional to drive amplitude)
- Characterize qubit-photon coupling strength
- Optimize pulse parameters for gate operations
"""

# ruff: noqa: SIM117 RUF100

import sys
from pathlib import Path

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eq1_pulse.builder import *
from eq1_pulse.models.basic_types import LinSpace


def example_amplitude_rabi():
    """Example 1: Amplitude Rabi - sweep drive amplitude.

    This is the most common Rabi experiment where we sweep the amplitude
    of a fixed-duration pulse and measure the excited state population.
    The oscillation frequency is proportional to the drive amplitude.
    """
    print("=" * 70)
    print("Example 1: Amplitude Rabi Oscillation")
    print("=" * 70)
    print("Sweep drive amplitude to calibrate π pulse")
    print()

    with sequence() as seq:
        # Declare amplitude variable with unit
        var_decl("amp", "float", unit="mV")

        # Sweep amplitude from 0 to 100 mV in 50 steps
        amplitude_sweep = LinSpace(start=0.0, stop=100.0, num=50)

        with for_loop("amp", amplitude_sweep):
            # Apply drive pulse with variable amplitude
            # Note: amp variable represents mV, use variable reference
            play(
                "qubit",
                square_pulse(
                    duration="100ns",  # Fixed duration
                    amplitude=var("amp"),  # type: ignore[arg-type]  # Variable amplitude in mV
                ),
            )

            # Measure qubit state
            measure_and_discriminate(
                "qubit",
                "readout",
                "raw_result",
                "qubit_state",
                threshold="0.5mV",
                duration="1us",
                amplitude="50mV",
            )

            # Store the result
            store("rabi_amp", "qubit_state", mode="average")

            # Wait for qubit to relax back to ground state
            wait("qubit", duration="10us")

    print(f"Created sequence with {len(seq.items)} operations")
    print(seq.model_dump_json(indent=2))
    print()
    print("Expected result: Sinusoidal oscillation in excited state probability")
    print("π pulse amplitude: First minimum in oscillation")
    print()
    return seq


def example_time_rabi():
    """Example 2: Time Rabi - sweep pulse duration.

    Here we sweep the duration of a fixed-amplitude pulse. This is useful
    when the amplitude is already set and we want to find the π pulse duration.
    """
    print("=" * 70)
    print("Example 2: Time Rabi Oscillation")
    print("=" * 70)
    print("Sweep pulse duration to calibrate π pulse timing")
    print()

    with sequence() as seq:
        # Declare duration variable with unit
        var_decl("t_drive", "float", unit="ns")

        # Sweep duration from 0 to 200 ns in 100 steps
        duration_sweep = LinSpace(start=0.0, stop=200.0, num=100)

        with for_loop("t_drive", duration_sweep):
            # Apply drive pulse with variable duration
            play(
                "qubit",
                square_pulse(
                    duration=var("t_drive"),  # type: ignore[arg-type]  # Variable duration in ns
                    amplitude="80mV",  # Fixed amplitude
                ),
            )

            # Measure and discriminate
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
            store("rabi_time", "qubit_state", mode="average")

            # Relaxation time
            wait("qubit", duration="10us")

    print(f"Created sequence with {len(seq.items)} operations")
    print(seq.model_dump_json(indent=2))
    print()
    print("Expected result: Sinusoidal oscillation in time domain")
    print("π pulse duration: First zero crossing of oscillation")
    print()
    return seq


def example_frequency_rabi():
    """Example 3: Frequency Rabi - sweep drive frequency.

    Sweep the frequency of the drive tone around the qubit resonance
    while keeping amplitude and duration fixed. This helps find the
    qubit transition frequency.
    """
    print("=" * 70)
    print("Example 3: Frequency Rabi (Qubit Spectroscopy)")
    print("=" * 70)
    print("Sweep drive frequency to find qubit resonance")
    print()

    with sequence() as seq:
        # Declare frequency variable with unit
        var_decl("freq", "float", unit="GHz")

        # Sweep frequency around expected qubit frequency
        # For spin qubits in GaAs: typically 10-20 GHz
        # Values in GHz
        freq_sweep = LinSpace(start=14.0, stop=16.0, num=200)

        with for_loop("freq", freq_sweep):
            # Set drive frequency
            set_frequency("qubit", var("freq"))  # type: ignore[arg-type]  # freq in GHz

            # Apply π/2 pulse (or saturating pulse)
            play(
                "qubit",
                square_pulse(
                    duration="50ns",
                    amplitude="100mV",
                ),
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
            store("spectroscopy", "qubit_state", mode="average")

            # Wait
            wait("qubit", duration="10us")

    print(f"Created sequence with {len(seq.items)} operations")
    print(seq.model_dump_json(indent=2))
    print()
    print("Expected result: Peak in excited state population at resonance")
    print("Qubit frequency: Center of resonance peak")
    print()
    return seq


def example_2d_rabi():
    """Example 4: 2D Rabi - sweep both amplitude and duration.

    This creates a 2D map of Rabi oscillations by sweeping both
    amplitude and duration. Useful for complete pulse calibration.
    """
    print("=" * 70)
    print("Example 4: 2D Rabi Oscillation (Amplitude vs Duration)")
    print("=" * 70)
    print("Create 2D map for comprehensive pulse calibration")
    print()

    with sequence() as seq:
        # Declare variables with units
        var_decl("amp", "float", unit="mV")
        var_decl("dur", "float", unit="ns")

        # Amplitude sweep
        amp_sweep = LinSpace(start=20.0, stop=100.0, num=20)
        # Duration sweep
        dur_sweep = LinSpace(start=10.0, stop=200.0, num=40)

        # Nested loops for 2D sweep
        with for_loop("amp", amp_sweep):
            with for_loop("dur", dur_sweep):
                # Drive pulse with both parameters varying
                play(
                    "qubit",
                    square_pulse(
                        duration=var("dur"),  # type: ignore[arg-type]  # Variable duration in ns
                        amplitude=var("amp"),  # type: ignore[arg-type]  # Variable amplitude in mV
                    ),
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

                # Store with 2D coordinates
                store("rabi_2d", "qubit_state", mode="average")

                # Wait
                wait("qubit", duration="10us")

    print(f"Created sequence with {len(seq.items)} operations")
    print(seq.model_dump_json(indent=2))
    print()
    print("Expected result: 2D map showing Rabi chevron pattern")
    print("Use to identify optimal π and π/2 pulse parameters")
    print()
    return seq


def example_rabi_with_detuning():
    """Example 5: Rabi oscillations with frequency detuning.

    Perform Rabi oscillations at different detunings from resonance.
    This characterizes how robust the qubit operations are to frequency errors.
    """
    print("=" * 70)
    print("Example 5: Rabi with Detuning")
    print("=" * 70)
    print("Characterize Rabi oscillations off-resonance")
    print()

    with sequence() as seq:
        # Declare variables with units
        var_decl("detuning", "float", unit="MHz")
        var_decl("t_pulse", "float", unit="ns")

        # Detuning values (offset from qubit frequency) in MHz
        detuning_sweep = LinSpace(start=-50.0, stop=50.0, num=11)
        # Pulse duration sweep in ns
        duration_sweep = LinSpace(start=0.0, stop=200.0, num=50)

        with for_loop("detuning", detuning_sweep):
            # Set frequency with detuning
            # Assumes base frequency is already set
            shift_frequency("qubit", var("detuning"))  # type: ignore[arg-type]  # detuning in MHz

            with for_loop("t_pulse", duration_sweep):
                # Drive pulse
                play(
                    "qubit",
                    square_pulse(
                        duration=var("t_pulse"),  # type: ignore[arg-type]  # Variable duration in ns
                        amplitude="80mV",
                    ),
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
                store("rabi_detuned", "qubit_state", mode="average")

                # Wait
                wait("qubit", duration="10us")

            # Reset frequency shift for next detuning
            shift_frequency("qubit", var("detuning"))  # Undo shift

    print(f"Created sequence with {len(seq.items)} operations")
    print(seq.model_dump_json(indent=2))
    print()
    print("Expected result: Rabi oscillations with detuning-dependent frequency")
    print("Effective Rabi frequency: sqrt(Omega^2 + Delta^2)")
    print()
    return seq


def example_pulsed_rabi():
    """Example 6: Pulsed Rabi with shaped pulses.

    Use shaped (e.g., Gaussian) pulses instead of square pulses
    for better spectral properties and reduced leakage.
    """
    print("=" * 70)
    print("Example 6: Pulsed Rabi with Shaped Pulses")
    print("=" * 70)
    print("Use Gaussian pulses for cleaner spectral properties")
    print()

    with sequence() as seq:
        # Declare amplitude variable with unit
        var_decl("amp", "float", unit="mV")

        # Amplitude sweep for shaped pulses in mV
        amp_sweep = LinSpace(start=0.0, stop=100.0, num=50)

        with for_loop("amp", amp_sweep):
            # Use external Gaussian pulse shape
            play(
                "qubit",
                external_pulse(
                    "pulses.gaussian",
                    duration="100ns",
                    amplitude=var("amp"),  # type: ignore[arg-type]  # Variable amplitude in mV
                    params={"sigma": "20ns"},  # Gaussian width
                ),
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
            store("rabi_gaussian", "qubit_state", mode="average")

            # Wait
            wait("qubit", duration="10us")

    print(f"Created sequence with {len(seq.items)} operations")
    print(seq.model_dump_json(indent=2))
    print()
    print("Expected result: Smoother Rabi oscillations with less leakage")
    print("Gaussian pulses reduce off-resonant excitation")
    print()
    return seq


def main():
    """Run all Rabi oscillation examples."""
    print()
    print("*" * 70)
    print("RABI OSCILLATION EXPERIMENTS FOR SPIN QUBITS")
    print("*" * 70)
    print()
    print("These examples demonstrate fundamental qubit characterization")
    print("experiments using the builder interface.")
    print()

    example_amplitude_rabi()
    example_time_rabi()
    example_frequency_rabi()
    example_2d_rabi()
    example_rabi_with_detuning()
    example_pulsed_rabi()

    print("*" * 70)
    print("All Rabi oscillation examples completed!")
    print("*" * 70)
    print()
    print("Next steps:")
    print("- Fit oscillations to extract Rabi frequency")
    print("- Calibrate π and π/2 pulse parameters")
    print("- Proceed to coherence measurements (T1, T2)")
    print()


if __name__ == "__main__":
    main()
