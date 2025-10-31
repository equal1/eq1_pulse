#!/usr/bin/env python3
"""
Generate all pulse sequence diagrams for the documentation.

This script should be run before building the documentation to ensure
all diagrams are up to date.
"""

import subprocess
import sys
from pathlib import Path

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent

# List of all diagram generator scripts
GENERATORS = [
    "generate_basic_usage_diagram.py",
    "generate_rabi_diagram.py",
    "generate_pulse_sequence_diagram.py",
    "generate_duration_rabi_diagram.py",
    "generate_frequency_spectroscopy_diagram.py",
    "generate_t2star_ramsey_diagram.py",
    "generate_ramsey_detuning_diagram.py",
    "generate_hahn_echo_diagram.py",
    "generate_barrier_diagram.py",
    "generate_schedule_refop_diagram.py",
]


def main():
    """Run all diagram generators."""
    print("=" * 60)
    print("Generating all pulse sequence diagrams...")
    print("=" * 60)

    success_count = 0
    fail_count = 0

    for generator in GENERATORS:
        script_path = SCRIPT_DIR / generator
        if not script_path.exists():
            print(f"⚠️  Skipping {generator} (not found)")
            continue

        print(f"\n📊 Running {generator}...")
        try:
            result = subprocess.run(
                [sys.executable, str(script_path)], cwd=SCRIPT_DIR, check=True, capture_output=True, text=True
            )
            print(result.stdout)
            success_count += 1
        except subprocess.CalledProcessError as e:
            print(f"❌ Error running {generator}:")
            print(e.stderr)
            fail_count += 1

    print("\n" + "=" * 60)
    print(f"✅ Successfully generated {success_count} diagram(s)")
    if fail_count > 0:
        print(f"❌ Failed to generate {fail_count} diagram(s)")
        return 1
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
