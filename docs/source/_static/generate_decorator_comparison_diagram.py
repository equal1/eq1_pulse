"""Generate comparison diagram: @nested_sequence vs @nested_schedule."""

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

# Create figure with two columns
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

# Colors
seq_color = "#8B5CF6"
sched_color = "#3B82F6"

# Left Panel: nested_sequence
ax1.set_xlim(0, 6)
ax1.set_ylim(0, 4)
ax1.axis("off")

ax1.text(3, 3.6, "@nested_sequence", fontsize=12, fontweight="bold", ha="center", color=seq_color)
ax1.text(3, 3.2, "Sequential Timing", fontsize=10, ha="center", style="italic", color="#6B7280")

timeline_y = 2.0
ax1.plot([0.5, 5.5], [timeline_y, timeline_y], "k-", linewidth=2)
ax1.text(0.5, timeline_y + 0.4, "ch:", fontsize=8, fontweight="bold")

blocks = [
    {"x": 1.2, "label": "op1", "width": 0.8},
    {"x": 2.2, "label": "op2", "width": 0.8},
    {"x": 3.2, "label": "op3", "width": 0.8},
    {"x": 4.2, "label": "op4", "width": 1.0},
]

for block in blocks:
    rect = FancyBboxPatch(
        (block["x"], timeline_y - 0.2),
        block["width"],
        0.4,
        boxstyle="round,pad=0.04",
        edgecolor=seq_color,
        facecolor=seq_color,
        linewidth=2,
        alpha=0.7,
    )
    ax1.add_patch(rect)
    ax1.text(
        block["x"] + block["width"] / 2,
        timeline_y,
        block["label"],
        fontsize=8,
        ha="center",
        va="center",
        color="white",
        fontweight="bold",
    )

ax1.annotate(
    "",
    xy=(2.1, timeline_y - 0.5),
    xytext=(1.4, timeline_y - 0.5),
    arrowprops=dict(arrowstyle="->", color="#6B7280", lw=2),
)

ax1.text(3, 1.0, "Implicit timing", fontsize=9, ha="center", fontweight="bold")
ax1.text(3, 0.6, "Operations in order", fontsize=8, ha="center", color="#6B7280")
ax1.text(3, 0.2, "No parallel operations", fontsize=8, ha="center", color="#6B7280")

# Right Panel: nested_schedule
ax2.set_xlim(0, 6)
ax2.set_ylim(0, 4)
ax2.axis("off")

ax2.text(3, 3.6, "@nested_schedule", fontsize=12, fontweight="bold", ha="center", color=sched_color)
ax2.text(3, 3.2, "Explicit Timing", fontsize=10, ha="center", style="italic", color="#6B7280")

timeline_y = 2.3
timeline_y2 = 1.7

ax2.plot([0.5, 5.5], [timeline_y, timeline_y], "k-", linewidth=2)
ax2.text(0.5, timeline_y + 0.4, "q0:", fontsize=8, fontweight="bold")

ax2.plot([0.5, 5.5], [timeline_y2, timeline_y2], "k-", linewidth=2)
ax2.text(0.5, timeline_y2 + 0.4, "q1:", fontsize=8, fontweight="bold")

rect1 = FancyBboxPatch(
    (1.0, timeline_y - 0.2),
    1.0,
    0.4,
    boxstyle="round,pad=0.04",
    edgecolor=sched_color,
    facecolor=sched_color,
    linewidth=2,
    alpha=0.7,
)
ax2.add_patch(rect1)
ax2.text(1.5, timeline_y, "init", fontsize=8, ha="center", va="center", color="white", fontweight="bold")

gap_start = 2.0
gap_end = 2.4
ax2.annotate(
    "",
    xy=(gap_end, timeline_y - 0.45),
    xytext=(gap_start, timeline_y - 0.45),
    arrowprops=dict(arrowstyle="<->", color="#EF4444", lw=1.5),
)
ax2.text(
    (gap_start + gap_end) / 2, timeline_y - 0.75, "dt", fontsize=7, ha="center", color="#EF4444", fontweight="bold"
)

rect2 = FancyBboxPatch(
    (2.4, timeline_y - 0.2),
    0.9,
    0.4,
    boxstyle="round,pad=0.04",
    edgecolor=sched_color,
    facecolor=sched_color,
    linewidth=2,
    alpha=0.7,
)
ax2.add_patch(rect2)
ax2.text(2.85, timeline_y, "gate", fontsize=8, ha="center", va="center", color="white", fontweight="bold")

rect3 = FancyBboxPatch(
    (2.4, timeline_y2 - 0.2),
    0.9,
    0.4,
    boxstyle="round,pad=0.04",
    edgecolor=sched_color,
    facecolor=sched_color,
    linewidth=2,
    alpha=0.7,
)
ax2.add_patch(rect3)
ax2.text(2.85, timeline_y2, "gate", fontsize=8, ha="center", va="center", color="white", fontweight="bold")

ax2.plot([2.4, 2.4], [timeline_y - 0.2, timeline_y2 + 0.2], "k--", linewidth=1.5, alpha=0.4)
ax2.plot([3.3, 3.3], [timeline_y - 0.2, timeline_y2 + 0.2], "k--", linewidth=1.5, alpha=0.4)

ax2.text(3, 1.0, "Explicit ref_op/ref_pt", fontsize=9, ha="center", fontweight="bold")
ax2.text(3, 0.6, "Precise timing control", fontsize=8, ha="center", color="#6B7280")
ax2.text(3, 0.2, "Parallel operations", fontsize=8, ha="center", color="#6B7280")

plt.tight_layout()

plt.savefig("decorator_comparison_diagram.svg", format="svg", bbox_inches="tight", dpi=300)
plt.savefig("decorator_comparison_diagram.pdf", format="pdf", bbox_inches="tight", dpi=300)
plt.savefig("decorator_comparison_diagram.png", format="png", bbox_inches="tight", dpi=300)

print("Generated decorator_comparison_diagram.{svg,pdf,png}")
