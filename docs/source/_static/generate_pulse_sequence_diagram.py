#!/usr/bin/env python3
"""
Generate pulse sequence timing diagram for the builder guide documentation.

This script creates a visual representation of the Rabi oscillation experiment
described in docs/source/user_guide/builder_guide.rst (Complete Example section).
It visualizes the JSON output structure as a timeline showing:
- Drive pulses with variable amplitudes on the qubit channel
- Readout pulses on the readout channel
- Wait periods for qubit relaxation

The generated files are saved in the same directory as this script (docs/source/_static/).

Usage:
    cd docs/source/_static
    python generate_pulse_sequence_diagram.py

Output:
    - pulse_sequence_diagram.pdf (vector format for LaTeX/PDF)
    - pulse_sequence_diagram.png (raster format for compatibility)
    - pulse_sequence_diagram.svg (vector format for HTML)
"""

import os

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

# Output to the same directory as this script (_static folder)
script_dir = os.path.dirname(os.path.abspath(__file__))

# Set up the figure with more vertical space for title and bottom labels
fig, ax = plt.subplots(1, 1, figsize=(14, 6.5))
fig.subplots_adjust(top=0.92, bottom=0.12)  # Leave more space at top and bottom

ax.set_title("Rabi Oscillation Pulse Sequence - Timeline Visualization", fontsize=14, fontweight="bold", pad=15)

# Define channels
channels = ["qubit", "readout"]
n_channels = len(channels)

# Time parameters for visualization (showing 3 iterations out of 50)
iterations_to_show = 3
pulse_duration = 0.1  # 100 ns (scaled for visualization)
readout_duration = 1.0  # 1 us
wait_duration = 10.0  # 10 us
total_iteration_time = pulse_duration + readout_duration + wait_duration

# Colors
qubit_color = "#8B4789"  # Purple
readout_color = "#FF8C42"  # Orange
wait_color = "#E0E0E0"  # Light gray

# Set up the axes
ax.set_ylim(-0.5, n_channels + 0.5)
ax.set_xlim(0, iterations_to_show * total_iteration_time + 2)
ax.set_yticks(range(n_channels))
ax.set_yticklabels([f"Channel: {ch}" for ch in channels], fontsize=11)
ax.set_xlabel("Time", fontsize=12, fontweight="bold")
ax.xaxis.set_label_coords(0.5, -0.15)  # Move xlabel down to avoid overlap
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.spines["left"].set_visible(False)
ax.grid(True, axis="x", alpha=0.3, linestyle="--")

# Draw iterations
amplitudes = [25, 50, 75]  # Example amplitudes for the 3 iterations shown

for i in range(iterations_to_show):
    t_start = i * total_iteration_time
    amp = amplitudes[i]

    # Qubit channel (index 0)
    # Drive pulse
    pulse_height = 0.6 * (amp / 100)  # Scale height by amplitude
    pulse_rect = FancyBboxPatch(
        (t_start, 0 - pulse_height / 2),
        pulse_duration,
        pulse_height,
        boxstyle="round,pad=0.01",
        edgecolor=qubit_color,
        facecolor=qubit_color,
        linewidth=2,
        alpha=0.7,
    )
    ax.add_patch(pulse_rect)

    # Add amplitude label on pulse
    ax.text(
        t_start + pulse_duration / 2,
        0,
        f"{amp} mV",
        ha="center",
        va="center",
        fontsize=8,
        fontweight="bold",
        color="white",
        bbox=dict(boxstyle="round,pad=0.2", facecolor=qubit_color, alpha=0.8),
    )

    # Wait period on qubit channel
    wait_rect = Rectangle(
        (t_start + pulse_duration + readout_duration, 0 - 0.15),
        wait_duration,
        0.3,
        edgecolor="gray",
        facecolor=wait_color,
        linewidth=1,
        alpha=0.5,
        linestyle="--",
    )
    ax.add_patch(wait_rect)

    # Readout channel (index 1)
    # Readout pulse (constant amplitude)
    readout_height = 0.4
    readout_rect = FancyBboxPatch(
        (t_start + pulse_duration, 1 - readout_height / 2),
        readout_duration,
        readout_height,
        boxstyle="round,pad=0.01",
        edgecolor=readout_color,
        facecolor=readout_color,
        linewidth=2,
        alpha=0.7,
    )
    ax.add_patch(readout_rect)

    # Add label
    ax.text(
        t_start + pulse_duration + readout_duration / 2,
        1,
        "Measure\n30 mV",
        ha="center",
        va="center",
        fontsize=8,
        fontweight="bold",
        color="white",
    )

    # Wait period on readout channel
    wait_rect2 = Rectangle(
        (t_start + pulse_duration + readout_duration, 1 - 0.15),
        wait_duration,
        0.3,
        edgecolor="gray",
        facecolor=wait_color,
        linewidth=1,
        alpha=0.5,
        linestyle="--",
    )
    ax.add_patch(wait_rect2)

    # Add iteration label - positioned lower to avoid overlap
    ax.text(
        t_start + total_iteration_time / 2,
        -1.0,
        f"Iteration {i + 1}",
        ha="center",
        fontsize=9,
        style="italic",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="lightblue", alpha=0.3),
    )

    # Add vertical separators between iterations
    if i < iterations_to_show - 1:
        ax.axvline(t_start + total_iteration_time, color="black", linestyle=":", linewidth=1, alpha=0.3)

# Add annotations for timing
first_pulse_end = pulse_duration
ax.annotate("", xy=(first_pulse_end, 0.7), xytext=(0, 0.7), arrowprops=dict(arrowstyle="<->", color="blue", lw=1.5))
ax.text(pulse_duration / 2, 0.85, "100 ns", ha="center", fontsize=8, color="blue", fontweight="bold")

first_readout_end = pulse_duration + readout_duration
ax.annotate(
    "",
    xy=(first_readout_end, 1.7),
    xytext=(pulse_duration, 1.7),
    arrowprops=dict(arrowstyle="<->", color="blue", lw=1.5),
)
ax.text(pulse_duration + readout_duration / 2, 1.85, "1 μs", ha="center", fontsize=8, color="blue", fontweight="bold")

first_wait_end = pulse_duration + readout_duration + wait_duration
ax.annotate(
    "",
    xy=(first_wait_end, -0.55),
    xytext=(pulse_duration + readout_duration, -0.55),
    arrowprops=dict(arrowstyle="<->", color="green", lw=1.5),
)
ax.text(
    pulse_duration + readout_duration + wait_duration / 2,
    -0.7,
    "Wait: 10 μs",
    ha="center",
    fontsize=8,
    color="green",
    fontweight="bold",
)

# Add legend
legend_elements = [
    mpatches.Patch(facecolor=qubit_color, edgecolor=qubit_color, alpha=0.7, label="Drive Pulse (variable amplitude)"),
    mpatches.Patch(facecolor=readout_color, edgecolor=readout_color, alpha=0.7, label="Readout Pulse (30 mV)"),
    mpatches.Patch(facecolor=wait_color, edgecolor="gray", alpha=0.5, label="Wait Period (10 μs)"),
]
ax.legend(handles=legend_elements, loc="upper right", fontsize=9, framealpha=0.9)

# Add note about loop
note_x = iterations_to_show * total_iteration_time + 1
ax.text(note_x, 1, "...", fontsize=20, ha="center", va="center", style="italic", color="gray")
ax.text(
    note_x,
    0.5,
    "continues for\n50 iterations\ntotal",
    ha="center",
    va="center",
    fontsize=8,
    style="italic",
    bbox=dict(boxstyle="round,pad=0.4", facecolor="yellow", alpha=0.2),
)

# Add title annotation showing the sweep - moved lower to avoid overlap
ax.text(
    0.5,
    0.98,
    "Amplitude sweep: 0 → 100 mV (50 steps)",
    transform=ax.transAxes,
    ha="center",
    fontsize=10,
    style="italic",
    fontweight="bold",
    bbox=dict(boxstyle="round,pad=0.5", facecolor="wheat", alpha=0.5),
)

plt.tight_layout()

# Save as PDF (vector format for LaTeX) - primary output
output_pdf = os.path.join(script_dir, "pulse_sequence_diagram.pdf")
plt.savefig(output_pdf, bbox_inches="tight", facecolor="white")
print(f"PDF saved to: {output_pdf}")

# Also save PNG for compatibility
output_png = os.path.join(script_dir, "pulse_sequence_diagram.png")
plt.savefig(output_png, dpi=150, bbox_inches="tight", facecolor="white")
print(f"PNG saved to: {output_png}")

# Also save SVG for HTML
output_svg = os.path.join(script_dir, "pulse_sequence_diagram.svg")
plt.savefig(output_svg, bbox_inches="tight", facecolor="white")
print(f"SVG saved to: {output_svg}")
