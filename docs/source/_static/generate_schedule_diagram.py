#!/usr/bin/env python3
"""
Generate pulse schedule diagram with barrier for the basic usage example.

This script creates a schedule diagram showing parallel pulses synchronized with a barrier.
Outputs PDF (for LaTeX), PNG (compatibility), and SVG (for HTML) formats.
"""

from pathlib import Path

import matplotlib.patches as patches
import matplotlib.pyplot as plt

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent
OUTPUT_FILE = SCRIPT_DIR / "schedule_barrier_diagram"


def create_schedule_diagram():
    """Create a schedule diagram with barrier."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 4), sharex=True)
    fig.suptitle("Schedule with Barrier", fontsize=14, fontweight="bold", y=0.98)

    # Time axis (microseconds)
    t_start = 0
    t_end = 60

    # Channel 1: Drive
    ax1.set_ylabel("drive", fontsize=11, fontweight="bold")
    ax1.set_ylim(-0.2, 1.2)
    ax1.set_xlim(t_start, t_end)
    ax1.axhline(0, color="gray", linewidth=0.8, linestyle="--", alpha=0.5)
    ax1.set_yticks([])
    ax1.spines["left"].set_visible(False)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    # First pulse: 0-10 μs, 100mV
    square1 = patches.Rectangle((0, 0), 10, 1, linewidth=2, edgecolor="blue", facecolor="lightblue", alpha=0.7)
    ax1.add_patch(square1)
    ax1.plot([0, 0, 10, 10], [0, 1, 1, 0], "b-", linewidth=2)
    ax1.text(5, 0.5, "100mV\n10 μs", ha="center", va="center", fontsize=9)

    # Barrier at 15 μs
    ax1.axvline(15, color="red", linewidth=3, linestyle="-", alpha=0.8)
    ax1.text(15, 1.1, "barrier", ha="center", va="bottom", fontsize=9, color="red", fontweight="bold")

    # Second pulse: 15-35 μs, 80mV
    square2 = patches.Rectangle((15, 0), 20, 0.8, linewidth=2, edgecolor="blue", facecolor="lightblue", alpha=0.7)
    ax1.add_patch(square2)
    ax1.plot([15, 15, 35, 35], [0, 0.8, 0.8, 0], "b-", linewidth=2)
    ax1.text(25, 0.4, "80mV\n20 μs", ha="center", va="center", fontsize=9)

    # Channel 2: Readout
    ax2.set_ylabel("readout", fontsize=11, fontweight="bold")
    ax2.set_ylim(-0.2, 1.2)
    ax2.set_xlim(t_start, t_end)
    ax2.axhline(0, color="gray", linewidth=0.8, linestyle="--", alpha=0.5)
    ax2.set_yticks([])
    ax2.spines["left"].set_visible(False)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.set_xlabel("Time (μs)", fontsize=11)

    # First pulse: 0-5 μs, 50mV
    readout1 = patches.Rectangle((0, 0), 5, 0.5, linewidth=2, edgecolor="orange", facecolor="peachpuff", alpha=0.7)
    ax2.add_patch(readout1)
    ax2.plot([0, 0, 5, 5], [0, 0.5, 0.5, 0], color="orange", linewidth=2)
    ax2.text(2.5, 0.25, "50mV\n5 μs", ha="center", va="center", fontsize=9)

    # Barrier at 15 μs
    ax2.axvline(15, color="red", linewidth=3, linestyle="-", alpha=0.8)

    # Second pulse: 15-35 μs, 40mV
    readout2 = patches.Rectangle((15, 0), 20, 0.4, linewidth=2, edgecolor="orange", facecolor="peachpuff", alpha=0.7)
    ax2.add_patch(readout2)
    ax2.plot([15, 15, 35, 35], [0, 0.4, 0.4, 0], color="orange", linewidth=2)
    ax2.text(25, 0.2, "40mV\n20 μs", ha="center", va="center", fontsize=9)

    # Add baselines
    ax1.plot([10, 15], [0, 0], "k-", linewidth=1.5)
    ax1.plot([35, 60], [0, 0], "k-", linewidth=1.5)
    ax2.plot([5, 15], [0, 0], "k-", linewidth=1.5)
    ax2.plot([35, 60], [0, 0], "k-", linewidth=1.5)

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
    create_schedule_diagram()
