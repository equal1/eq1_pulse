#!/usr/bin/env python3
"""
Generate pulse sequence diagram for the basic usage example.

This script creates a timing diagram showing pulses on drive and readout channels.
Outputs PDF (for LaTeX), PNG (compatibility), and SVG (for HTML) formats.
"""

from pathlib import Path

import matplotlib.patches as patches
import matplotlib.pyplot as plt

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent
OUTPUT_FILE = SCRIPT_DIR / "basic_usage_pulse_diagram"


def create_pulse_diagram():
    """Create a simple pulse sequence diagram."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 4), sharex=True)
    fig.suptitle("Pulse Sequence Diagram", fontsize=14, fontweight="bold", y=0.98)

    # Time axis (microseconds)
    t_start = 0
    t_end = 20

    # Channel 1: Drive (Square pulse)
    ax1.set_ylabel("drive", fontsize=11, fontweight="bold")
    ax1.set_ylim(-0.2, 1.2)
    ax1.set_xlim(t_start, t_end)
    ax1.axhline(0, color="gray", linewidth=0.8, linestyle="--", alpha=0.5)
    ax1.set_yticks([])
    ax1.spines["left"].set_visible(False)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    # Square pulse: 0-10 μs, 100mV
    square = patches.Rectangle((0, 0), 10, 1, linewidth=2, edgecolor="blue", facecolor="lightblue", alpha=0.7)
    ax1.add_patch(square)
    ax1.text(5, 0.5, "Square\n100mV\n10 μs", ha="center", va="center", fontsize=9)
    ax1.plot([0, 0, 10, 10], [0, 1, 1, 0], "b-", linewidth=2)

    # Channel 2: Readout (Sine pulse)
    ax2.set_ylabel("readout", fontsize=11, fontweight="bold")
    ax2.set_ylim(-0.2, 1.2)
    ax2.set_xlim(t_start, t_end)
    ax2.axhline(0, color="gray", linewidth=0.8, linestyle="--", alpha=0.5)
    ax2.set_yticks([])
    ax2.spines["left"].set_visible(False)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.set_xlabel("Time (μs)", fontsize=11)

    # Sine pulse: 0-5 μs, 50mV, 5 GHz
    import numpy as np

    t_sine = np.linspace(0, 5, 200)
    # 5 GHz = many oscillations in 5 μs, but we'll show a few cycles for visualization
    sine_wave = 0.5 + 0.5 * np.sin(2 * np.pi * 3 * t_sine)  # 3 cycles for visibility
    ax2.fill_between(t_sine, 0, sine_wave, color="orange", alpha=0.3)
    ax2.plot(t_sine, sine_wave, "orange", linewidth=2)
    ax2.text(2.5, 0.5, "Sine 50mV\n5 GHz\n5 μs", ha="center", va="center", fontsize=9)

    # Add baseline
    ax2.plot([5, 20], [0, 0], "k-", linewidth=1.5)
    ax1.plot([10, 20], [0, 0], "k-", linewidth=1.5)

    plt.tight_layout()
    fig.subplots_adjust(top=0.92, hspace=0.3)

    # Save in multiple formats
    output_pdf = OUTPUT_FILE.with_suffix(".pdf")
    output_png = OUTPUT_FILE.with_suffix(".png")
    output_svg = OUTPUT_FILE.with_suffix(".svg")

    fig.savefig(output_pdf, format="pdf", bbox_inches="tight", dpi=150)
    print(f"PDF saved to: {output_pdf}")

    fig.savefig(output_png, format="png", bbox_inches="tight", dpi=150)
    print(f"PNG saved to: {output_png}")

    fig.savefig(output_svg, format="svg", bbox_inches="tight")
    print(f"SVG saved to: {output_svg}")

    plt.close()


if __name__ == "__main__":
    create_pulse_diagram()
