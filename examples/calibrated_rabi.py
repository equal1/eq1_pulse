#!/usr/bin/env python3
"""Rabi experiment driven by externally-calibrated values.

This mirrors ``spin_qubit_rabi.py`` but replaces hardcoded numbers with two kinds of
late-bound value:

- a **parameter** (:func:`~eq1_pulse.builder.param_decl`), supplied by the caller when the
  program is submitted -- here, the number of shots to average per point;
- **external constants** (:func:`~eq1_pulse.builder.extern_decl`), looked up in a calibration
  store by name at submission time -- here, the qubit drive frequency, its pi-pulse amplitude,
  and the readout discrimination threshold.

The same serialized program can be resubmitted after calibration drifts, without rebuilding the
IR: only the values resolved for ``q0.f01``, ``q0.pi_amp`` and ``readout.threshold`` change.

Note:
    These examples are for illustration purposes only and may not represent
    realistic experimental parameters or physical hardware configurations.
"""

import sys
from pathlib import Path

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eq1_pulse.builder import *


def example_calibrated_rabi():
    """Run a Rabi sequence with values resolved outside the program.

    Drive frequency, drive amplitude and discrimination threshold are all resolved from a
    calibration store at submission time, and the shot count is supplied by the caller.
    """
    print("=" * 70)
    print("Example: Calibrated Rabi")
    print("=" * 70)
    print("Drive frequency, pi-pulse amplitude and threshold come from calibration;")
    print("shot count is a submission-time parameter.")
    print()

    with build_sequence() as seq:
        # Supplied at submission time, with a fallback.
        param_decl("n_shots", "int", default=1000, min=1, max=100_000)

        # Resolved from the calibration store at submission time.
        extern_decl("q0.f01", "float", unit="GHz")
        extern_decl("q0.pi_amp", "float", unit="mV")
        extern_decl("readout.threshold", "float", unit="mV")

        var_decl("iq", "complex", unit="mV")
        var_decl("state", "bool")

        set_frequency("q0_drive", ext("q0.f01"))

        with repeat(var("n_shots")):
            play("q0_drive", square_pulse(duration="25ns", amplitude=ext("q0.pi_amp")))
            record("q0_readout", "iq", duration="1us", integration=full_integration())
            discriminate("state", "iq", threshold=ext("readout.threshold"))
            store("p1", "state", mode="average")
            wait("q0_drive", duration="10us")

    print(f"Created sequence with {len(seq.items)} operations")
    print(seq.model_dump_json(indent=2))
    print()
    return seq


if __name__ == "__main__":
    example_calibrated_rabi()
