#!/usr/bin/env python3
"""
Generate pulse sequence diagram for the Rabi oscillation example.

This script creates a timing diagram showing the variable amplitude drive pulse
followed by readout.
Outputs PDF (for LaTeX), PNG (compatibility), and SVG (for HTML) formats.
"""

from pathlib import Path

import matplotlib.patches as patches
import matplotlib.pyplot as plt

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent
OUTPUT_FILE = SCRIPT_DIR / "rabi_pulse_diagram"


def create_rabi_diagram():
    """Create Rabi pulse sequence diagram."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 4), sharex=True)
    fig.suptitle("Rabi Oscillation Pulse Sequence", fontsize=14, fontweight="bold", y=0.98)

    # Time axis (nanoseconds)
    t_start = 0
    t_end = 300

    # Channel 1: Drive (Variable amplitude square pulse)
    ax1.set_ylabel("drive", fontsize=11, fontweight="bold")
    ax1.set_ylim(-0.2, 1.2)
    ax1.set_xlim(t_start, t_end)
    ax1.axhline(0, color="gray", linewidth=0.8, linestyle="--", alpha=0.5)
    ax1.set_yticks([])
    ax1.spines["left"].set_visible(False)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    # Variable amplitude square pulse: 0-100 ns
    amp_var = 0.8  # Example amplitude (varies in actual experiment)
    square = patches.Rectangle((0, 0), 100, amp_var, linewidth=2, edgecolor="purple", facecolor="plum", alpha=0.7)
    ax1.add_patch(square)
    ax1.plot([0, 0, 100, 100], [0, amp_var, amp_var, 0], color="purple", linewidth=2)
    ax1.text(
        50,
        amp_var / 2,
        "Square\nVariable amplitude\n25-75 mV\n100 ns",
        ha="center",
        va="center",
        fontsize=9,
    )

    # Add annotation for variable amplitude
    ax1.annotate(
        "",
        xy=(105, 0),
        xytext=(105, amp_var),
        arrowprops=dict(arrowstyle="<->", color="purple", lw=1.5),
    )
    ax1.text(115, amp_var / 2, "varies", ha="left", va="center", fontsize=8, color="purple")

    # Channel 2: Readout (Fixed pulse)
    ax2.set_ylabel("readout", fontsize=11, fontweight="bold")
    ax2.set_ylim(-0.2, 1.2)
    ax2.set_xlim(t_start, t_end)
    ax2.axhline(0, color="gray", linewidth=0.8, linestyle="--", alpha=0.5)
    ax2.set_yticks([])
    ax2.spines["left"].set_visible(False)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.set_xlabel("Time (ns)", fontsize=11)

    # Readout pulse: 110-210 ns (10 ns wait after drive)
    readout = patches.Rectangle((110, 0), 100, 1.0, linewidth=2, edgecolor="orange", facecolor="peachpuff", alpha=0.7)
    ax2.add_patch(readout)
    ax2.plot([110, 110, 210, 210], [0, 1.0, 1.0, 0], color="orange", linewidth=2)
    ax2.text(160, 0.5, "Square\n30 mV\n100 ns", ha="center", va="center", fontsize=9)

    # Add wait period annotation
    ax2.annotate(
        "",
        xy=(100, -0.1),
        xytext=(110, -0.1),
        arrowprops=dict(arrowstyle="<->", color="gray", lw=1),
    )
    ax2.text(105, -0.15, "10 ns\nwait", ha="center", va="top", fontsize=7, color="gray")

    # Add baseline
    ax2.plot([210, 300], [0, 0], "k-", linewidth=1.5)
    ax1.plot([100, 300], [0, 0], "k-", linewidth=1.5)

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
    create_rabi_diagram()
