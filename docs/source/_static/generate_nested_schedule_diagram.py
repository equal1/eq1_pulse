"""Generate diagram showing @nested_schedule decorator timing."""

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

# Create figure - simplified to show only timing
fig, ax = plt.subplots(1, 1, figsize=(12, 4))

# Colors
block_colors = ["#8B5CF6", "#3B82F6", "#10B981"]  # Purple, Blue, Green
arrow_color = "#EF4444"

ax.set_xlim(0, 13)
ax.set_ylim(0, 3.5)
ax.axis("off")
ax.set_title("@nested_schedule: Explicit Timing Control", fontsize=13, fontweight="bold", pad=15)

# ============================================================================
# Timeline Visualization
# ============================================================================

timeline_y = 2.0
ax.text(
    6.5,
    2.8,
    "Schedule blocks positioned with ref_op, ref_pt, and rel_time",
    fontsize=10,
    ha="center",
    style="italic",
    color="#6B7280",
)

# Draw timeline
timeline_start = 1
timeline_end = 12
ax.plot([timeline_start, timeline_end], [timeline_y, timeline_y], "k-", linewidth=2)

# Time axis
time_positions = [timeline_start, 3.5, 6.5, 10, timeline_end]
time_labels = ["0", "150ns", "160ns", "260ns", "310ns"]
for pos, label in zip(time_positions, time_labels, strict=True):
    ax.plot([pos, pos], [timeline_y - 0.1, timeline_y + 0.1], "k-", linewidth=1.5)
    ax.text(pos, timeline_y - 0.35, label, fontsize=9, ha="center", fontweight="bold")

# Block 1: Initialize (150ns duration)
block1_start = timeline_start
block1_width = 2.5
block1 = FancyBboxPatch(
    (block1_start, timeline_y + 0.3),
    block1_width,
    0.5,
    boxstyle="round,pad=0.05",
    edgecolor=block_colors[0],
    facecolor=block_colors[0],
    linewidth=2,
    alpha=0.7,
)
ax.add_patch(block1)
ax.text(
    block1_start + block1_width / 2,
    timeline_y + 0.55,
    "init",
    fontsize=10,
    ha="center",
    va="center",
    fontweight="bold",
    color="white",
)
ax.text(
    block1_start + block1_width / 2, timeline_y + 1.1, "150ns", fontsize=8, ha="center", va="center", style="italic"
)

# Arrow: 10ns delay
delay1_start = block1_start + block1_width
delay1_end = delay1_start + 0.5
ax.annotate(
    "",
    xy=(delay1_end, timeline_y + 0.55),
    xytext=(delay1_start, timeline_y + 0.55),
    arrowprops=dict(arrowstyle="<->", color=arrow_color, lw=1.5),
)
ax.text(
    (delay1_start + delay1_end) / 2,
    timeline_y + 1.0,
    "10ns",
    fontsize=8,
    ha="center",
    color=arrow_color,
    fontweight="bold",
)

# Block 2: Rabi (100ns duration)
block2_start = delay1_end
block2_width = 2.5
block2 = FancyBboxPatch(
    (block2_start, timeline_y + 0.3),
    block2_width,
    0.5,
    boxstyle="round,pad=0.05",
    edgecolor=block_colors[1],
    facecolor=block_colors[1],
    linewidth=2,
    alpha=0.7,
)
ax.add_patch(block2)
ax.text(
    block2_start + block2_width / 2,
    timeline_y + 0.55,
    "rabi",
    fontsize=10,
    ha="center",
    va="center",
    fontweight="bold",
    color="white",
)
ax.text(
    block2_start + block2_width / 2, timeline_y + 1.1, "100ns", fontsize=8, ha="center", va="center", style="italic"
)

# Arrow: 50ns delay
delay2_start = block2_start + block2_width
delay2_end = delay2_start + 1.0
ax.annotate(
    "",
    xy=(delay2_end, timeline_y + 0.55),
    xytext=(delay2_start, timeline_y + 0.55),
    arrowprops=dict(arrowstyle="<->", color=arrow_color, lw=1.5),
)
ax.text(
    (delay2_start + delay2_end) / 2,
    timeline_y + 1.0,
    "50ns",
    fontsize=8,
    ha="center",
    color=arrow_color,
    fontweight="bold",
)

# Block 3: Measure (50ns duration)
block3_start = delay2_end
block3_width = 2.0
block3 = FancyBboxPatch(
    (block3_start, timeline_y + 0.3),
    block3_width,
    0.5,
    boxstyle="round,pad=0.05",
    edgecolor=block_colors[2],
    facecolor=block_colors[2],
    linewidth=2,
    alpha=0.7,
)
ax.add_patch(block3)
ax.text(
    block3_start + block3_width / 2,
    timeline_y + 0.55,
    "measure",
    fontsize=10,
    ha="center",
    va="center",
    fontweight="bold",
    color="white",
)
ax.text(block3_start + block3_width / 2, timeline_y + 1.1, "50ns", fontsize=8, ha="center", va="center", style="italic")

# Reference point annotations
ref_pt_y = timeline_y - 0.7
# init.end
ax.plot(
    [block1_start + block1_width, block1_start + block1_width], [timeline_y, ref_pt_y], "k--", linewidth=1, alpha=0.5
)
ax.text(
    block1_start + block1_width,
    ref_pt_y - 0.2,
    "ref_pt='end'",
    fontsize=7,
    ha="center",
    style="italic",
    color="#6B7280",
)

# rabi.end
ax.plot(
    [block2_start + block2_width, block2_start + block2_width], [timeline_y, ref_pt_y], "k--", linewidth=1, alpha=0.5
)
ax.text(
    block2_start + block2_width,
    ref_pt_y - 0.2,
    "ref_pt='end'",
    fontsize=7,
    ha="center",
    style="italic",
    color="#6B7280",
)

# Key concept
ax.text(
    6.5,
    0.3,
    "Each block positioned using add_block(block, ref_op=..., ref_pt=..., rel_time=...)",
    fontsize=9,
    ha="center",
    va="center",
    style="italic",
    color="#2563EB",
)

plt.tight_layout()

# Save in multiple formats
plt.savefig("nested_schedule_diagram.svg", format="svg", bbox_inches="tight", dpi=300)
plt.savefig("nested_schedule_diagram.pdf", format="pdf", bbox_inches="tight", dpi=300)
plt.savefig("nested_schedule_diagram.png", format="png", bbox_inches="tight", dpi=300)

print("Generated nested_schedule_diagram.{svg,pdf,png}")
