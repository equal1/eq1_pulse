#!/usr/bin/env python3
"""
Generate pulse sequence diagram for duration Rabi oscillation.

This script creates a timing diagram showing variable duration drive pulse
followed by readout.
"""

import matplotlib.patches as patches
import matplotlib.pyplot as plt


def create_duration_rabi_diagram():
    """Create duration Rabi pulse sequence diagram."""
    fig, ax = plt.subplots(1, 1, figsize=(12, 2.5))
    fig.suptitle("Duration Rabi Pulse Sequence", fontsize=14, fontweight="bold", y=0.98)

    # Time axis (nanoseconds)
    t_start = 0
    t_end = 300

    # Single channel: qubit
    ax.set_ylabel("qubit", fontsize=11, fontweight="bold")
    ax.set_ylim(-0.5, 1.5)
    ax.set_xlim(t_start, t_end)
    ax.axhline(0, color="gray", linewidth=0.8, linestyle="--", alpha=0.5)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_xlabel("Time (ns)", fontsize=11)

    # Variable duration drive pulse: 0-80 ns (example duration)
    dur_var = 80  # Example duration (varies in actual experiment)
    drive = patches.Rectangle((0, 0), dur_var, 0.8, linewidth=2, edgecolor="purple", facecolor="plum", alpha=0.7)
    ax.add_patch(drive)
    ax.plot([0, 0, dur_var, dur_var], [0, 0.8, 0.8, 0], color="purple", linewidth=2)
    ax.text(
        dur_var / 2,
        0.4,
        "X pulse\n80 mV\nVariable duration\n0-200 ns",
        ha="center",
        va="center",
        fontsize=9,
    )

    # Add annotation for variable duration
    ax.annotate(
        "",
        xy=(0, -0.2),
        xytext=(dur_var, -0.2),
        arrowprops=dict(arrowstyle="<->", color="purple", lw=1.5),
    )
    ax.text(dur_var / 2, -0.3, "varies", ha="center", va="top", fontsize=8, color="purple")

    # Wait period
    wait_start = dur_var
    wait_end = dur_var + 10
    ax.annotate(
        "",
        xy=(wait_start, -0.05),
        xytext=(wait_end, -0.05),
        arrowprops=dict(arrowstyle="<->", color="gray", lw=1),
    )
    ax.text((wait_start + wait_end) / 2, -0.15, "wait", ha="center", va="top", fontsize=7, color="gray")

    # Readout pulse: 90-190 ns (after 10 ns wait)
    readout_start = wait_end
    readout_end = readout_start + 100
    readout = patches.Rectangle(
        (readout_start, 0),
        100,
        1.0,
        linewidth=2,
        edgecolor="orange",
        facecolor="peachpuff",
        alpha=0.7,
    )
    ax.add_patch(readout)
    ax.plot(
        [readout_start, readout_start, readout_end, readout_end],
        [0, 1.0, 1.0, 0],
        color="orange",
        linewidth=2,
    )
    ax.text(readout_start + 50, 0.5, "Readout", ha="center", va="center", fontsize=10, fontweight="bold")

    # Add baseline
    ax.plot([readout_end, t_end], [0, 0], "k-", linewidth=1.5)

    plt.tight_layout()
    fig.subplots_adjust(top=0.90, bottom=0.15)
    return fig


if __name__ == "__main__":
    # Standalone mode: show the plot
    create_duration_rabi_diagram()
    plt.show()
