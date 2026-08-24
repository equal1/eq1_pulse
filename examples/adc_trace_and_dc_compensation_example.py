#!/usr/bin/env python3
"""Raw ADC trace acquisition and DC offset compensation.

This script demonstrates two debug/calibration operations that sit alongside ordinary
measurement:

- ``trace()``: like ``record()``, but array-valued -- one entry per sample, rather than a single
  accumulated result. With no ``integration`` (the default), it is the raw ADC trace: every sample
  of the readout signal kept as-is. This is the tool used to calibrate ``time_of_flight`` (the
  delay between playing a readout pulse and the reflected signal arriving back at the ADC), and
  more generally for debug measurements where the demodulation reference isn't known yet.
- ``compensate_dc()``: plays a square wave sized to bring a channel's accumulated (integrated)
  output back to a zero average, to counter DC offset built up by asymmetric pulse sequences.

NOTE: These examples are for illustration purposes only and demonstrate the
builder API syntax. Real experimental sequences would require calibrated
parameters, proper channel configuration, and integration with hardware backends.
"""

import sys
from pathlib import Path

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eq1_pulse.builder import *


def example_raw_adc_trace_for_time_of_flight():
    """Example 1: Capture a raw ADC trace to calibrate time_of_flight.

    time_of_flight is the delay between playing a readout pulse and the reflected signal
    arriving back at the ADC. It is found by playing a readout pulse and capturing a raw,
    unintegrated trace of everything the ADC sees; the delay to the first real signal in that
    trace is the value to feed back into time_of_flight= on later record()/trace() calls.
    """
    print("=" * 70)
    print("Example 1: Raw ADC Trace for time_of_flight Calibration")
    print("=" * 70)

    with build_sequence() as seq:
        # trace() writes an array, so the target variable needs a shape -- one entry per
        # sample of the acquisition window (here, 1000 samples over 1us).
        var_decl("raw_trace", "complex", shape=(1000,), unit="mV")

        play("readout_drive", square_pulse(duration="1us", amplitude="50mV"))
        # No integration: every ADC sample is kept as-is.
        trace("readout", "raw_trace", duration="1us")

    print(f"Created sequence with {len(seq.items)} operations")
    print(seq.model_dump_json(indent=2))
    print()
    print("Inspect 'raw_trace' offline to find the delay to the reflected signal --")
    print("that duration is what you then pass as time_of_flight= below.")
    print()
    return seq


def example_trace_with_time_of_flight_and_integration():
    """Example 2: Once time_of_flight is known, acquire an integrated trace with it applied."""
    print("=" * 70)
    print("Example 2: Trace With time_of_flight and Per-Sample Demodulation")
    print("=" * 70)

    with build_sequence() as seq:
        var_decl("iq_trace", "complex", shape=(1000,), unit="mV")

        play("readout_drive", square_pulse(duration="1us", amplitude="50mV"))
        trace(
            "readout",
            "iq_trace",
            duration="1us",
            integration=demod_integration(),
            time_of_flight="148ns",  # e.g. measured from Example 1's raw_trace
        )

    print(f"Created sequence with {len(seq.items)} operations")
    print(seq.model_dump_json(indent=2))
    print()
    return seq


def example_dc_compensation():
    """Example 3: Cancel accumulated DC offset after an asymmetric drive pulse."""
    print("=" * 70)
    print("Example 3: DC Offset Compensation")
    print("=" * 70)

    with build_sequence() as seq:
        # An asymmetric pulse (e.g. always positive) accumulates a DC offset on the channel.
        play("qubit", square_pulse(duration="200ns", amplitude="100mV"))

        # Bring the accumulated offset back to zero, capping the compensation pulse amplitude.
        compensate_dc("qubit", duration="200ns", max_amp="150mV")

    print(f"Created sequence with {len(seq.items)} operations")
    print(seq.model_dump_json(indent=2))
    print()
    return seq


def example_dc_compensation_reset():
    """Example 4: Reset the accumulator without playing a compensation pulse."""
    print("=" * 70)
    print("Example 4: Reset DC Accumulator")
    print("=" * 70)

    with build_sequence() as seq:
        play("qubit", square_pulse(duration="200ns", amplitude="100mV"))
        # duration=None resets the accumulated value to zero without playing anything --
        # useful at the start of a new shot, so compensation doesn't carry over between shots.
        compensate_dc("qubit", duration=None)

    print(f"Created sequence with {len(seq.items)} operations")
    print(seq.model_dump_json(indent=2))
    print()
    return seq


def main():
    """Run all ADC trace and DC compensation examples."""
    print()
    print("*" * 70)
    print("ADC TRACE AND DC COMPENSATION EXAMPLES")
    print("*" * 70)
    print()

    example_raw_adc_trace_for_time_of_flight()
    example_trace_with_time_of_flight_and_integration()
    example_dc_compensation()
    example_dc_compensation_reset()

    print("*" * 70)
    print("All examples completed!")
    print("*" * 70)


if __name__ == "__main__":
    main()
