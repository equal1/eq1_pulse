#!/usr/bin/env python3
"""Advanced pulse shape examples.

This script demonstrates how to use arbitrary and external pulse shapes
using the builder interface. These advanced pulse types allow for:

- Arbitrary waveforms defined by explicit samples
- External pulse libraries with parameterized shapes
- Complex IQ modulation patterns
- Custom pulse envelopes for specific applications

For spin qubits, advanced pulse shapes are useful for:
- DRAG pulses to reduce leakage
- Optimized control pulses (GRAPE, CRAB, etc.)
- Shaped readout pulses for improved SNR
- Composite pulses for error suppression
"""

# ruff: noqa:

import sys
from pathlib import Path

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eq1_pulse.builder import *


def example_gaussian_pulse():
    """Example 1: Gaussian pulse using external pulse library.

    Gaussian pulses are commonly used in quantum computing for their
    smooth spectral profile and reduced leakage to non-computational states.
    """
    print("=" * 70)
    print("Example 1: Gaussian Pulse (External)")
    print("=" * 70)
    print("Use external Gaussian pulse for smooth transitions")
    print()

    with build_sequence() as seq:
        # Declare amplitude variable
        var_decl("amp", "float", unit="mV")

        # Gaussian pulse from external library
        play(
            "qubit",
            external_pulse(
                "pulses.gaussian",
                duration="50ns",
                amplitude="100mV",
                params={"sigma": "10"},  # Width parameter
            ),
        )

        var_decl("result", "complex", unit="mV")
        # Measurement
        measure("qubit", result_var="result", duration="1us", amplitude="50mV")

    print(f"Created sequence with {len(seq.items)} operations")
    print(seq.model_dump_json(indent=2))
    print()
    print("Gaussian pulse reduces spectral leakage compared to square pulse")
    print()
    return seq


def example_drag_pulse():
    """Example 2: DRAG pulse for suppressing leakage.

    Derivative Removal by Adiabatic Gate (DRAG) pulses compensate
    for unwanted transitions to non-computational states.
    """
    print("=" * 70)
    print("Example 2: DRAG Pulse (External)")
    print("=" * 70)
    print("DRAG pulse with derivative compensation")
    print()

    with build_sequence() as seq:
        # DRAG pulse with beta parameter
        play(
            "qubit",
            external_pulse(
                "pulses.drag",
                duration="50ns",
                amplitude="120mV",
                params={
                    "beta": 0.5,  # DRAG coefficient
                    "sigma": "10ns",  # Gaussian width
                    "delta": "200MHz",  # Anharmonicity
                },
            ),
        )

        var_decl("result", "complex", unit="mV")
        # Measurement
        measure("qubit", result_var="result", duration="1us", amplitude="50mV")

    print(f"Created sequence with {len(seq.items)} operations")
    print(seq.model_dump_json(indent=2))
    print()
    print("DRAG pulse reduces leakage to |2⟩ state")
    print()
    return seq


def example_triangle_pulse():
    """Example 3: Triangle pulse using arbitrary samples.

    Demonstrates how to define a custom waveform using explicit samples.
    """
    print("=" * 70)
    print("Example 3: Triangle Pulse (Arbitrary)")
    print("=" * 70)
    print("Custom triangle waveform from samples")
    print()

    with build_sequence() as seq:
        # Triangle pulse with explicit samples
        play(
            "qubit",
            arbitrary_pulse(
                samples=[0.0, 0.25, 0.5, 0.75, 1.0, 0.75, 0.5, 0.25, 0.0], duration="100ns", amplitude="80mV"
            ),
        )

        var_decl("result", "complex", unit="mV")
        # Measurement
        measure("qubit", result_var="result", duration="1us", amplitude="50mV")

    print(f"Created sequence with {len(seq.items)} operations")
    print(seq.model_dump_json(indent=2))
    print()
    print("Triangle pulse can provide smoother transitions than square")
    print()
    return seq


def example_iq_modulation():
    """Example 4: Complex IQ pulse with arbitrary samples.

    Use complex samples to define both I and Q quadratures explicitly.
    Useful for SSB modulation and advanced control sequences.
    """
    print("=" * 70)
    print("Example 4: IQ Modulated Pulse (Arbitrary)")
    print("=" * 70)
    print("Complex waveform with explicit IQ components")
    print()

    with build_sequence() as seq:
        # Complex samples for IQ modulation
        # This creates a rotating frame pulse
        iq_samples = [
            0.0 + 0.0j,
            0.3 + 0.3j,
            0.7 + 0.7j,
            1.0 + 0.0j,
            0.7 - 0.7j,
            0.3 - 0.3j,
            0.0 + 0.0j,
        ]

        play(
            "qubit",
            arbitrary_pulse(samples=iq_samples, duration="80ns", amplitude="90mV", interpolation="linear"),
        )

        var_decl("result", "complex", unit="mV")
        # Measurement
        measure("qubit", result_var="result", duration="1us", amplitude="50mV")

    print(f"Created sequence with {len(seq.items)} operations")
    print(seq.model_dump_json(indent=2))
    print()
    print("IQ pulse enables single-sideband modulation")
    print()
    return seq


def example_shaped_readout():
    """Example 5: Shaped readout pulse for improved SNR.

    Custom readout pulse shape can improve signal-to-noise ratio
    by matching the cavity response.
    """
    print("=" * 70)
    print("Example 5: Shaped Readout Pulse")
    print("=" * 70)
    print("Optimized readout pulse envelope")
    print()

    with build_sequence() as seq:
        # π pulse
        play(
            "qubit",
            external_pulse("pulses.gaussian", duration="50ns", amplitude="100mV", params={"sigma": "10ns"}),
        )

        # Shaped readout pulse
        # Exponential rise matched to cavity fill time
        play(
            "readout",
            external_pulse(
                "pulses.exp_rise",
                duration="2us",
                amplitude="50mV",
                params={"tau": "200ns"},  # Cavity time constant
            ),
        )

        # Record during shaped pulse
        record("readout", "iq_trace", duration="2us")

    print(f"Created sequence with {len(seq.items)} operations")
    print(seq.model_dump_json(indent=2))
    print()
    print("Shaped readout matches cavity response for better SNR")
    print()
    return seq


def example_composite_pulse():
    """Example 6: Composite pulse sequence.

    Combine multiple pulse shapes for error-robust gates.
    BB1 sequence: X(φ) - X(3φ) - X(φ) is robust to pulse amplitude errors.
    """
    print("=" * 70)
    print("Example 6: Composite Pulse (BB1)")
    print("=" * 70)
    print("Error-robust pulse sequence")
    print()

    with build_sequence() as seq:
        # BB1 composite pulse for amplitude-error robustness
        # First pulse: X(φ)
        set_phase("qubit", "0deg")
        play(
            "qubit",
            external_pulse("pulses.gaussian", duration="50ns", amplitude="100mV", params={"sigma": "10ns"}),
        )

        # Second pulse: X(3φ) with 3x longer duration
        set_phase("qubit", "180deg")
        play(
            "qubit",
            external_pulse("pulses.gaussian", duration="150ns", amplitude="100mV", params={"sigma": "30ns"}),
        )

        # Third pulse: X(φ)
        set_phase("qubit", "0deg")
        play(
            "qubit",
            external_pulse("pulses.gaussian", duration="50ns", amplitude="100mV", params={"sigma": "10ns"}),
        )

        # Reset phase
        set_phase("qubit", "0deg")

        var_decl("result", "complex", unit="mV")
        # Measurement
        measure("qubit", result_var="result", duration="1us", amplitude="50mV")

    print(f"Created sequence with {len(seq.items)} operations")
    print(seq.model_dump_json(indent=2))
    print()
    print("BB1 composite pulse provides robustness to amplitude errors")
    print()
    return seq


def main():
    """Run all pulse shape examples."""
    print()
    print("*" * 70)
    print("ADVANCED PULSE SHAPE EXAMPLES")
    print("*" * 70)
    print()

    example_gaussian_pulse()
    example_drag_pulse()
    example_triangle_pulse()
    example_iq_modulation()
    example_shaped_readout()
    example_composite_pulse()

    print("*" * 70)
    print("All pulse shape examples completed!")
    print("*" * 70)


if __name__ == "__main__":
    main()
