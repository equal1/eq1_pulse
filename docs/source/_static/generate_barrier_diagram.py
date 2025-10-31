#!/usr/bin/env python3
"""Generate pulse sequence diagram for schedule with barriers."""

from pathlib import Path

import matplotlib.patches as patches
import matplotlib.pyplot as plt


def generate_barrier_diagram():
    """Create a pulse sequence diagram showing barrier synchronization."""
    fig, ax = plt.subplots(figsize=(14, 4))

    # Drive channel
    drive_y = 0.7
    ax.text(-0.5, drive_y, "drive", ha="right", va="center", fontsize=11, weight="bold")
    ax.plot([0, 14], [drive_y, drive_y], "k-", linewidth=1.5, zorder=1)

    # First drive pulse
    drive1_start = 1.0
    drive1_width = 3.0
    pulse_height = 0.25
    drive1_rect = patches.Rectangle(
        (drive1_start, drive_y - pulse_height / 2),
        drive1_width,
        pulse_height,
        linewidth=2,
        edgecolor="#2E86AB",
        facecolor="#A9D6E5",
        zorder=2,
    )
    ax.add_patch(drive1_rect)
    ax.text(drive1_start + drive1_width / 2, drive_y, "100mV", ha="center", va="center", fontsize=9, weight="bold")
    ax.text(
        drive1_start + drive1_width / 2, drive_y - pulse_height / 2 - 0.15, "10μs", ha="center", va="top", fontsize=8
    )

    # Barrier for drive
    barrier_x = 5.0
    barrier_width = 0.15
    ax.add_patch(
        patches.Rectangle(
            (barrier_x, drive_y - 0.4),
            barrier_width,
            0.8,
            linewidth=1,
            edgecolor="#C1121F",
            facecolor="#FFB3BA",
            zorder=3,
        )
    )
    ax.text(
        barrier_x + barrier_width / 2,
        drive_y + 0.55,
        "barrier",
        ha="center",
        va="bottom",
        fontsize=9,
        weight="bold",
        color="#C1121F",
    )

    # Second drive pulse (after barrier)
    drive2_start = barrier_x + barrier_width + 0.3
    drive2_width = 5.0
    drive2_rect = patches.Rectangle(
        (drive2_start, drive_y - pulse_height / 2),
        drive2_width,
        pulse_height,
        linewidth=2,
        edgecolor="#2E86AB",
        facecolor="#A9D6E5",
        zorder=2,
    )
    ax.add_patch(drive2_rect)
    ax.text(drive2_start + drive2_width / 2, drive_y, "80mV", ha="center", va="center", fontsize=9, weight="bold")
    ax.text(
        drive2_start + drive2_width / 2, drive_y - pulse_height / 2 - 0.15, "20μs", ha="center", va="top", fontsize=8
    )

    # Readout channel
    readout_y = 0.0
    ax.text(-0.5, readout_y, "readout", ha="right", va="center", fontsize=11, weight="bold")
    ax.plot([0, 14], [readout_y, readout_y], "k-", linewidth=1.5, zorder=1)

    # First readout pulse
    readout1_start = 1.0
    readout1_width = 1.5
    readout1_rect = patches.Rectangle(
        (readout1_start, readout_y - pulse_height / 2),
        readout1_width,
        pulse_height,
        linewidth=2,
        edgecolor="#6A994E",
        facecolor="#A7C957",
        zorder=2,
    )
    ax.add_patch(readout1_rect)
    ax.text(readout1_start + readout1_width / 2, readout_y, "50mV", ha="center", va="center", fontsize=9, weight="bold")
    ax.text(
        readout1_start + readout1_width / 2,
        readout_y - pulse_height / 2 - 0.15,
        "5μs",
        ha="center",
        va="top",
        fontsize=8,
    )

    # Barrier for readout (extended to show wait)
    ax.add_patch(
        patches.Rectangle(
            (barrier_x, readout_y - 0.4),
            barrier_width,
            0.8,
            linewidth=1,
            edgecolor="#C1121F",
            facecolor="#FFB3BA",
            zorder=3,
        )
    )

    # Wait period annotation for readout
    wait_start = readout1_start + readout1_width
    wait_end = barrier_x
    ax.plot([wait_start, wait_end], [readout_y - 0.55, readout_y - 0.55], "k--", linewidth=1, alpha=0.5)
    ax.text(
        (wait_start + wait_end) / 2,
        readout_y - 0.65,
        "wait for barrier",
        ha="center",
        va="top",
        fontsize=8,
        style="italic",
        color="gray",
    )

    # Second readout pulse (after barrier, aligned with drive)
    readout2_start = barrier_x + barrier_width + 0.3
    readout2_width = 5.0
    readout2_rect = patches.Rectangle(
        (readout2_start, readout_y - pulse_height / 2),
        readout2_width,
        pulse_height,
        linewidth=2,
        edgecolor="#6A994E",
        facecolor="#A7C957",
        zorder=2,
    )
    ax.add_patch(readout2_rect)
    ax.text(readout2_start + readout2_width / 2, readout_y, "40mV", ha="center", va="center", fontsize=9, weight="bold")
    ax.text(
        readout2_start + readout2_width / 2,
        readout_y - pulse_height / 2 - 0.15,
        "20μs",
        ha="center",
        va="top",
        fontsize=8,
    )

    # Synchronization annotation
    sync_y = -1.2
    ax.text(
        7,
        sync_y,
        "After barrier: both channels start simultaneously",
        ha="center",
        va="center",
        fontsize=10,
        style="italic",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="lightcoral", alpha=0.3),
    )

    # Set axis limits and appearance
    ax.set_xlim(-1, 14)
    ax.set_ylim(-1.5, 1.5)
    ax.axis("off")

    plt.tight_layout()
    return fig


def main():
    """Generate and save the diagram in multiple formats."""
    output_dir = Path(__file__).parent
    base_name = "barrier_sync_pulse_diagram"

    fig = generate_barrier_diagram()

    # Save in multiple formats
    formats = {
        "svg": {"format": "svg", "bbox_inches": "tight"},
        "pdf": {"format": "pdf", "bbox_inches": "tight"},
        "png": {"format": "png", "dpi": 150, "bbox_inches": "tight"},
    }

    for ext, kwargs in formats.items():
        output_file = output_dir / f"{base_name}.{ext}"
        fig.savefig(output_file, **kwargs)
        print(f"Generated: {output_file}")

    plt.close(fig)


if __name__ == "__main__":
    main()
