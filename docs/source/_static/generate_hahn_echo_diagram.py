#!/usr/bin/env python3
"""Generate pulse sequence diagram for Hahn echo (spin echo) experiment."""

from pathlib import Path

import matplotlib.patches as patches
import matplotlib.pyplot as plt


def generate_hahn_echo_diagram():
    """Create a pulse sequence diagram for Hahn echo experiment."""
    fig, ax = plt.subplots(figsize=(14, 3))

    # Channel name
    channel_y = 0.5
    ax.text(-0.5, channel_y, "qubit", ha="right", va="center", fontsize=11, weight="bold")

    # Timeline
    ax.plot([0, 14], [channel_y, channel_y], "k-", linewidth=1.5, zorder=1)

    # First π/2 pulse
    pulse1_start = 1.5
    pulse1_width = 0.8
    pulse_height = 0.3
    pulse1_rect = patches.Rectangle(
        (pulse1_start, channel_y - pulse_height / 2),
        pulse1_width,
        pulse_height,
        linewidth=2,
        edgecolor="#2E86AB",
        facecolor="#A9D6E5",
        zorder=2,
    )
    ax.add_patch(pulse1_rect)
    ax.text(pulse1_start + pulse1_width / 2, channel_y, "π/2", ha="center", va="center", fontsize=10, weight="bold")
    ax.text(
        pulse1_start + pulse1_width / 2, channel_y - pulse_height / 2 - 0.15, "25ns", ha="center", va="top", fontsize=8
    )

    # First wait period (τ/2)
    wait1_start = pulse1_start + pulse1_width + 0.3
    wait1_width = 2.5
    wait_y = channel_y - 0.3
    ax.text(
        wait1_start + wait1_width / 2,
        wait_y,
        "wait(τ)",
        ha="center",
        va="top",
        fontsize=9,
        style="italic",
        color="gray",
    )

    # τ/2 annotation
    tau_y = channel_y + 0.45
    ax.plot([wait1_start, wait1_start + wait1_width], [tau_y, tau_y], "k-", linewidth=1.5, marker="|", markersize=8)
    ax.text(wait1_start + wait1_width / 2, tau_y + 0.1, "τ/2", ha="center", va="bottom", fontsize=9, style="italic")

    # π pulse (refocusing)
    pi_pulse_start = wait1_start + wait1_width + 0.3
    pi_pulse_width = 1.0
    pi_rect = patches.Rectangle(
        (pi_pulse_start, channel_y - pulse_height / 2),
        pi_pulse_width,
        pulse_height,
        linewidth=2,
        edgecolor="#C1121F",
        facecolor="#FFB3BA",
        zorder=2,
    )
    ax.add_patch(pi_rect)
    ax.text(pi_pulse_start + pi_pulse_width / 2, channel_y, "π", ha="center", va="center", fontsize=10, weight="bold")
    ax.text(
        pi_pulse_start + pi_pulse_width / 2,
        channel_y - pulse_height / 2 - 0.15,
        "50ns",
        ha="center",
        va="top",
        fontsize=8,
    )

    # Refocus annotation
    ax.text(
        pi_pulse_start + pi_pulse_width / 2,
        channel_y + 0.65,
        "(refocus)",
        ha="center",
        va="bottom",
        fontsize=8,
        style="italic",
        color="#C1121F",
    )

    # Second wait period (τ/2)
    wait2_start = pi_pulse_start + pi_pulse_width + 0.3
    wait2_width = 2.5
    ax.text(
        wait2_start + wait2_width / 2,
        wait_y,
        "wait(τ)",
        ha="center",
        va="top",
        fontsize=9,
        style="italic",
        color="gray",
    )

    # τ/2 annotation for second wait
    ax.plot([wait2_start, wait2_start + wait2_width], [tau_y, tau_y], "k-", linewidth=1.5, marker="|", markersize=8)
    ax.text(wait2_start + wait2_width / 2, tau_y + 0.1, "τ/2", ha="center", va="bottom", fontsize=9, style="italic")

    # Second π/2 pulse
    pulse2_start = wait2_start + wait2_width + 0.3
    pulse2_width = 0.8
    pulse2_rect = patches.Rectangle(
        (pulse2_start, channel_y - pulse_height / 2),
        pulse2_width,
        pulse_height,
        linewidth=2,
        edgecolor="#2E86AB",
        facecolor="#A9D6E5",
        zorder=2,
    )
    ax.add_patch(pulse2_rect)
    ax.text(pulse2_start + pulse2_width / 2, channel_y, "π/2", ha="center", va="center", fontsize=10, weight="bold")
    ax.text(
        pulse2_start + pulse2_width / 2, channel_y - pulse_height / 2 - 0.15, "25ns", ha="center", va="top", fontsize=8
    )

    # Short wait
    wait3_start = pulse2_start + pulse2_width + 0.3
    wait3_width = 0.5

    # Readout pulse
    readout_start = wait3_start + wait3_width + 0.3
    readout_width = 2.0
    readout_rect = patches.Rectangle(
        (readout_start, channel_y - pulse_height / 2),
        readout_width,
        pulse_height,
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
    sweep_y = -0.65
    ax.text(
        7,
        sweep_y,
        "Sweep: τ from 0 → 50 μs",
        ha="center",
        va="center",
        fontsize=10,
        style="italic",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="wheat", alpha=0.3),
    )

    # Set axis limits and appearance
    ax.set_xlim(-1, 14)
    ax.set_ylim(-1.0, 1.2)
    ax.axis("off")

    plt.tight_layout()
    return fig


def main():
    """Generate and save the diagram in multiple formats."""
    output_dir = Path(__file__).parent
    base_name = "hahn_echo_pulse_diagram"

    fig = generate_hahn_echo_diagram()

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
