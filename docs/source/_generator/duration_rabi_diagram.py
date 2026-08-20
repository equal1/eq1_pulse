#!/usr/bin/env python3
"""Generate pulse sequence diagram for duration Rabi experiment."""

import matplotlib.patches as patches
import matplotlib.pyplot as plt


def create_duration_rabi_diagram():
    """Create a pulse sequence diagram for duration Rabi experiment."""
    fig, ax = plt.subplots(figsize=(10, 3))

    # Channel name
    channel_y = 0.5
    ax.text(-0.5, channel_y, "qubit", ha="right", va="center", fontsize=11, weight="bold")

    # Timeline
    ax.plot([0, 10], [channel_y, channel_y], "k-", linewidth=1.5, zorder=1)

    # Variable width drive pulse (X gate)
    drive_start = 1.5
    drive_width = 2.0  # Variable width represented
    drive_height = 0.3
    drive_rect = patches.Rectangle(
        (drive_start, channel_y - drive_height / 2),
        drive_width,
        drive_height,
        linewidth=2,
        edgecolor="#2E86AB",
        facecolor="#A9D6E5",
        zorder=2,
    )
    ax.add_patch(drive_rect)
    ax.text(drive_start + drive_width / 2, channel_y, "X", ha="center", va="center", fontsize=10, weight="bold")
    ax.text(
        drive_start + drive_width / 2, channel_y - drive_height / 2 - 0.15, "80mV", ha="center", va="top", fontsize=9
    )

    # Variable duration indicator
    ax.plot(
        [drive_start, drive_start + drive_width],
        [channel_y + drive_height / 2 + 0.08, channel_y + drive_height / 2 + 0.08],
        "k-",
        linewidth=1.5,
        marker="|",
        markersize=8,
    )
    ax.text(
        drive_start + drive_width / 2,
        channel_y + drive_height / 2 + 0.18,
        "var",
        ha="center",
        va="bottom",
        fontsize=9,
        style="italic",
        color="#C1121F",
    )

    # Wait period
    wait_start = drive_start + drive_width + 0.5
    wait_width = 1.0
    ax.text(
        wait_start + wait_width / 2,
        channel_y - 0.25,
        "wait",
        ha="center",
        va="top",
        fontsize=9,
        style="italic",
        color="gray",
    )

    # Readout pulse
    readout_start = wait_start + wait_width + 0.5
    readout_width = 2.5
    readout_height = 0.3
    readout_rect = patches.Rectangle(
        (readout_start, channel_y - readout_height / 2),
        readout_width,
        readout_height,
        linewidth=2,
        edgecolor="#6A994E",
        facecolor="#A7C957",
        zorder=2,
    )
    ax.add_patch(readout_rect)
    ax.text(
        readout_start + readout_width / 2, channel_y, "Readout", ha="center", va="center", fontsize=10, weight="bold"
    )

    # Sweep annotation
    sweep_y = -0.5
    ax.text(
        5,
        sweep_y,
        "Sweep: duration from 0 → 200 ns",
        ha="center",
        va="center",
        fontsize=10,
        style="italic",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="wheat", alpha=0.3),
    )

    # Set axis limits and appearance
    ax.set_xlim(-1, 10)
    ax.set_ylim(-0.8, 1.0)
    ax.axis("off")

    plt.tight_layout()
    return fig


if __name__ == "__main__":
    # Standalone mode: show the plot
    create_duration_rabi_diagram()
    plt.show()
