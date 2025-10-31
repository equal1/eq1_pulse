#!/usr/bin/env python3
"""Generate pulse sequence diagram for schedule with ref_op timing."""

from pathlib import Path

import matplotlib.patches as patches
import matplotlib.pyplot as plt


def generate_schedule_refop_diagram():
    """Create a pulse sequence diagram for schedule with ref_op timing."""
    fig, ax = plt.subplots(figsize=(14, 3.5))

    # Qubit channel
    qubit_y = 0.7
    ax.text(-0.5, qubit_y, "qubit", ha="right", va="center", fontsize=11, weight="bold")
    ax.plot([0, 14], [qubit_y, qubit_y], "k-", linewidth=1.5, zorder=1)

    # First qubit pulse (op1)
    op1_start = 1.5
    op1_width = 1.5
    pulse_height = 0.25
    op1_rect = patches.Rectangle(
        (op1_start, qubit_y - pulse_height / 2),
        op1_width,
        pulse_height,
        linewidth=2,
        edgecolor="#2E86AB",
        facecolor="#A9D6E5",
        zorder=2,
    )
    ax.add_patch(op1_rect)
    ax.text(op1_start + op1_width / 2, qubit_y, "50mV", ha="center", va="center", fontsize=9, weight="bold")
    ax.text(op1_start + op1_width / 2, qubit_y - pulse_height / 2 - 0.15, "100ns", ha="center", va="top", fontsize=8)
    ax.text(
        op1_start + op1_width / 2,
        qubit_y - pulse_height / 2 - 0.35,
        "op1",
        ha="center",
        va="top",
        fontsize=9,
        style="italic",
        color="#2E86AB",
    )

    # Delay annotation (500ns)
    delay_start = op1_start + op1_width
    delay_end = op1_start + op1_width + 3.0
    delay_y = qubit_y - 0.55
    ax.annotate(
        "",
        xy=(delay_end, delay_y),
        xytext=(delay_start, delay_y),
        arrowprops=dict(arrowstyle="->", lw=2, color="#C1121F"),
    )
    ax.text(
        (delay_start + delay_end) / 2, delay_y - 0.12, "500ns delay", ha="center", va="top", fontsize=9, color="#C1121F"
    )

    # Second qubit pulse (op2)
    op2_start = delay_end
    op2_width = 1.5
    op2_rect = patches.Rectangle(
        (op2_start, qubit_y - pulse_height / 2),
        op2_width,
        pulse_height,
        linewidth=2,
        edgecolor="#2E86AB",
        facecolor="#A9D6E5",
        zorder=2,
    )
    ax.add_patch(op2_rect)
    ax.text(op2_start + op2_width / 2, qubit_y, "30mV", ha="center", va="center", fontsize=9, weight="bold")
    ax.text(op2_start + op2_width / 2, qubit_y - pulse_height / 2 - 0.15, "100ns", ha="center", va="top", fontsize=8)
    ax.text(
        op2_start + op2_width / 2,
        qubit_y - pulse_height / 2 - 0.35,
        "op2",
        ha="center",
        va="top",
        fontsize=9,
        style="italic",
        color="#2E86AB",
    )

    # Readout channel
    readout_y = 0.0
    ax.text(-0.5, readout_y, "readout", ha="right", va="center", fontsize=11, weight="bold")
    ax.plot([0, 14], [readout_y, readout_y], "k-", linewidth=1.5, zorder=1)

    # Readout pulse (starts with op2)
    readout_start = op2_start
    readout_width = 3.0
    readout_rect = patches.Rectangle(
        (readout_start, readout_y - pulse_height / 2),
        readout_width,
        pulse_height,
        linewidth=2,
        edgecolor="#6A994E",
        facecolor="#A7C957",
        zorder=2,
    )
    ax.add_patch(readout_rect)
    ax.text(readout_start + readout_width / 2, readout_y, "20mV", ha="center", va="center", fontsize=9, weight="bold")
    ax.text(
        readout_start + readout_width / 2, readout_y - pulse_height / 2 - 0.15, "1μs", ha="center", va="top", fontsize=8
    )

    # Synchronization annotation (starts with op2)
    sync_y = readout_y - 0.55
    ax.text(
        readout_start + readout_width / 2,
        sync_y,
        "(starts with op2)",
        ha="center",
        va="top",
        fontsize=9,
        style="italic",
        color="gray",
    )

    # Timing relationship annotation
    timing_y = -1.3
    ax.text(
        7,
        timing_y,
        "ref_op timing: op2 starts 500ns after op1 ends",
        ha="center",
        va="center",
        fontsize=10,
        style="italic",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="wheat", alpha=0.3),
    )

    # Set axis limits and appearance
    ax.set_xlim(-1, 14)
    ax.set_ylim(-1.6, 1.3)
    ax.axis("off")

    plt.tight_layout()
    return fig


def main():
    """Generate and save the diagram in multiple formats."""
    output_dir = Path(__file__).parent
    base_name = "schedule_refop_timing_diagram"

    fig = generate_schedule_refop_diagram()

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
