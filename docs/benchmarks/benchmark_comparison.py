"""Figure 4.1 - latency comparison, host laptop vs Raspberry Pi Zero 2W.

Reads the two live benchmark result files produced by `make benchmark ARGS=--live`
(tables re-computed with `system_benchmark.py --rebuild`) and draws one panel per
MEASURED latency metric (each on its own linear scale) with min/max whiskers and the
target threshold as a dashed line. Unmeasured (N/A) and simulated rows are not plotted.
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: render straight to PNG
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
PLATFORMS = [
    ("Host laptop (x86_64)", HERE / "laptop_benchmark_results.json", "#257de0"),
    ("Raspberry Pi Zero 2W (ARM)", HERE / "pi_benchmark_results.json", "#f47230"),
]
# (row index in table_4_1_rows, panel title, target in ms)
METRICS = [
    (3, "AI inference (model v1)", 10),
    (4, "Serial command round-trip", 150),
    (5, "Telegram API round-trip", 1500),
]
INK, INK_2, GRID = "#1f1f1f", "#6b6b6b", "#e4e4e4"


def load(path):
    rows = json.loads(path.read_text())["table_4_1_rows"]
    out = {}
    for idx, *_ in METRICS:
        mean = float(rows[idx][3])
        lo, hi = (float(v) for v in rows[idx][4].split("/"))
        out[idx] = (mean, lo, hi)
    return out


data = [(name, color, load(p)) for name, p, color in PLATFORMS]

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9,
                     "axes.edgecolor": INK_2, "axes.labelcolor": INK,
                     "xtick.color": INK_2, "ytick.color": INK_2})
fig, axes = plt.subplots(1, len(METRICS), figsize=(8.5, 3.8), dpi=300)

for ax, (idx, title, target) in zip(axes, METRICS):
    top = max(target, *(d[idx][2] for _, _, d in data)) * 1.18
    for i, (name, color, d) in enumerate(data):
        mean, lo, hi = d[idx]
        ax.bar(i, mean, width=0.62, color=color, label=name, zorder=2)
        ax.errorbar(i, mean, yerr=[[mean - lo], [hi - mean]], fmt="none",
                    ecolor=INK, elinewidth=1, capsize=4, zorder=3)
        ax.annotate(f"{mean:.1f}" if mean >= 10 else f"{mean:.2f}",
                    xy=(i + 0.33, mean), xytext=(3, 0), textcoords="offset points",
                    ha="left", va="center", fontsize=8.5, color=INK, fontweight="bold", zorder=4,
                    bbox=dict(boxstyle="square,pad=0.15", fc="white", ec="none"))
    ax.axhline(target, color=INK, linestyle=(0, (4, 3)), linewidth=1, zorder=1)
    ax.set_title(f"{title}\n", color=INK, fontsize=10, pad=8)
    ax.text(0.5, 1.03, f"target < {target} ms (dashed)", transform=ax.transAxes,
            ha="center", va="bottom", fontsize=8, color=INK_2)
    ax.set_xticks([])
    ax.set_xlim(-0.55, 1.55)
    ax.set_ylim(0, top)
    ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
    ax.spines[["top", "right"]].set_visible(False)

axes[0].set_ylabel("Latency (ms) — mean, whiskers = min / max")
handles, labels = axes[0].get_legend_handles_labels()
fig.legend(handles, labels, loc="upper center", ncol=2, frameon=False,
           bbox_to_anchor=(0.5, 1.0), fontsize=9)
fig.tight_layout(rect=(0, 0, 1, 0.92))

out = HERE / "figure_4_1_benchmarks.png"
fig.savefig(out, facecolor="white")
print(f"Saved {out}")
