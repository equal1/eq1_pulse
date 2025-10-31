"""Generate diagram showing @nested_sequence decorator usage."""

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

# Create figure
fig, ax = plt.subplots(1, 1, figsize=(12, 4))

# Colors
gate_color = "#8B5CF6"  # Purple

ax.set_xlim(0, 12)
ax.set_ylim(0, 3.5)
ax.axis("off")
ax.set_title("@nested_sequence: Implicit Sequential Timing", fontsize=13, fontweight="bold", pad=15)

# ============================================================================
# Timeline Visualization
# ============================================================================

timeline_y = 2.0
ax.text(
    6,
    2.8,
    "Sequence operations execute in order automatically",
    fontsize=10,
    ha="center",
    style="italic",
    color="#6B7280",
)

# Draw timeline
ax.plot([1, 11], [timeline_y, timeline_y], "k-", linewidth=2)
ax.text(1, timeline_y + 0.45, "Channel:", fontsize=9, fontweight="bold")

# Sequential blocks
blocks = [
    {"x": 2.0, "label": "hadamard", "width": 1.5},
    {"x": 3.8, "label": "x_gate", "width": 1.5},
    {"x": 5.6, "label": "hadamard", "width": 1.5},
    {"x": 7.4, "label": "readout", "width": 2.0},
]

for block in blocks:
    rect = FancyBboxPatch(
        (block["x"], timeline_y - 0.25),
        block["width"],
        0.5,
        boxstyle="round,pad=0.05",
        edgecolor=gate_color,
        facecolor=gate_color,
        linewidth=2,
        alpha=0.7,
    )
    ax.add_patch(rect)
    ax.text(
        block["x"] + block["width"] / 2,
        timeline_y,
        block["label"],
        fontsize=9,
        ha="center",
        va="center",
        color="white",
        fontweight="bold",
    )

# Arrow showing sequential flow
ax.annotate(
    "",
    xy=(3.7, timeline_y - 0.6),
    xytext=(2.2, timeline_y - 0.6),
    arrowprops=dict(arrowstyle="->", color="#6B7280", lw=2),
)
ax.text(2.95, timeline_y - 0.95, "sequential", fontsize=9, ha="center", style="italic", color="#6B7280")

ax.annotate(
    "",
    xy=(5.5, timeline_y - 0.6),
    xytext=(4.0, timeline_y - 0.6),
    arrowprops=dict(arrowstyle="->", color="#6B7280", lw=2),
)
ax.text(4.75, timeline_y - 0.95, "sequential", fontsize=9, ha="center", style="italic", color="#6B7280")

# Key concept
ax.text(
    6,
    0.3,
    "Function calls automatically create sub-sequences in order",
    fontsize=9,
    ha="center",
    va="center",
    style="italic",
    color="#059669",
)

plt.tight_layout()

# Save in multiple formats
plt.savefig("nested_sequence_diagram.svg", format="svg", bbox_inches="tight", dpi=300)
plt.savefig("nested_sequence_diagram.pdf", format="pdf", bbox_inches="tight", dpi=300)
plt.savefig("nested_sequence_diagram.png", format="png", bbox_inches="tight", dpi=300)

print("Generated nested_sequence_diagram.{svg,pdf,png}")
