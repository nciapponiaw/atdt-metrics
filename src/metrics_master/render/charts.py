"""Chart renderers — one function per chart type, returns a saved PNG path."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

OUTPUT_DIR = Path("output")

COLORS = {
    "green": "#2CA02C",
    "red": "#D62728",
    "blue": "#4C78A8",
    "purple": "#7B4F9E",
    "orange": "#FF7F0E",
    "grey": "#999999",
}


def _ensure_output_dir() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _apply_style() -> None:
    plt.style.use("seaborn-v0_8-whitegrid")


def _save(fig: plt.Figure, name: str) -> Path:
    _ensure_output_dir()
    path = OUTPUT_DIR / f"{name}.png"
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def render_bar(name: str, title: str, data: dict[str, Any], **kwargs) -> Path:
    """Simple bar chart."""
    _apply_style()
    fig, ax = plt.subplots(figsize=(10, 5))

    labels = list(data.keys())
    values = [v if v is not None else 0 for v in data.values()]
    bars = ax.bar(labels, values, color=COLORS["blue"])
    for bar, val in zip(bars, values):
        if val:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                    str(val), ha="center", va="bottom", fontsize=10, fontweight="bold")

    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.set_ylabel(kwargs.get("ylabel", ""))
    return _save(fig, name)


def render_stacked_bar(name: str, title: str, data: dict[str, dict[str, int]], **kwargs) -> Path:
    """Stacked bar chart. data = {x_label: {series_name: value}}.

    Uses green for 'Completed'/'Done'/'Resolved' and red for others.
    """
    _apply_style()
    fig, ax = plt.subplots(figsize=(10, 5))

    x_labels = list(data.keys())
    if not x_labels:
        ax.text(0.5, 0.5, "No Data", ha="center", va="center", transform=ax.transAxes)
        ax.set_title(title, fontsize=13, fontweight="bold")
        return _save(fig, name)

    segments = sorted({s for d in data.values() for s in d.keys()})
    x = np.arange(len(x_labels))
    bottoms = np.zeros(len(x_labels))

    positive_names = {"Completed", "Done", "Resolved"}
    for seg in segments:
        values = [data[xl].get(seg, 0) for xl in x_labels]
        color = COLORS["green"] if seg in positive_names else COLORS["red"]
        ax.bar(x, values, bottom=bottoms, label=seg, color=color, alpha=0.85)
        bottoms += np.array(values)

    ax.set_xticks(x)
    ax.set_xticklabels(x_labels, rotation=45, ha="right")
    ax.legend(loc="upper left", fontsize=9)
    ax.set_title(title, fontsize=13, fontweight="bold")
    return _save(fig, name)


def render_dual_area(name: str, title: str, data: dict[str, dict[str, int]], **kwargs) -> Path:
    """Dual area/line chart for created vs resolved."""
    _apply_style()
    fig, ax = plt.subplots(figsize=(10, 5))

    x_labels = list(data.keys())
    if not x_labels:
        ax.text(0.5, 0.5, "No Data", ha="center", va="center", transform=ax.transAxes)
        ax.set_title(title, fontsize=13, fontweight="bold")
        return _save(fig, name)

    created = [data[wk].get("Created", 0) for wk in x_labels]
    resolved = [data[wk].get("Resolved", 0) for wk in x_labels]
    x = range(len(x_labels))

    ax.fill_between(x, created, alpha=0.2, color=COLORS["red"])
    ax.plot(x, created, color=COLORS["red"], linewidth=2, marker="o", label="Created")
    ax.fill_between(x, resolved, alpha=0.2, color=COLORS["green"])
    ax.plot(x, resolved, color=COLORS["green"], linewidth=2, marker="o", label="Resolved")

    ax.set_xticks(list(x))
    ax.set_xticklabels(x_labels, rotation=45, ha="right")
    ax.legend(loc="upper left", fontsize=9)
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.set_ylabel("Count")
    return _save(fig, name)


def render_bar_with_trend(name: str, title: str, data: dict[str, int], **kwargs) -> Path:
    """Bar chart with rolling average trend line."""
    _apply_style()
    fig, ax = plt.subplots(figsize=(10, 5))

    labels = list(data.keys())
    values = [v if v is not None else 0 for v in data.values()]

    bars = ax.bar(labels, values, color=COLORS["purple"], alpha=0.8, label="Weekly")
    for bar, val in zip(bars, values):
        if val:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                    str(val), ha="center", va="bottom", fontsize=9, fontweight="bold")

    # Rolling average trend line
    if len(values) >= 3:
        window = min(4, len(values))
        avg = []
        for i in range(len(values)):
            start = max(0, i - window + 1)
            avg.append(sum(values[start:i + 1]) / (i - start + 1))
        ax.plot(range(len(labels)), avg, color=COLORS["orange"], linewidth=2.5,
                linestyle="--", marker="", label=f"Rolling Avg ({window}w)")

    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.legend(loc="upper left", fontsize=9)
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.set_ylabel("Emulations Completed")
    return _save(fig, name)


def render_big_number(name: str, title: str, value: Any, target: Any = None, **kwargs) -> Path:
    """Single big number display."""
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.axis("off")

    if value is not None:
        display_val = f"{value}%"
    else:
        display_val = "N/A"

    color = "#333333"
    if target is not None and value is not None:
        if value <= target:
            color = COLORS["green"]
        elif value <= target * 1.5:
            color = COLORS["orange"]
        else:
            color = COLORS["red"]

    ax.text(0.5, 0.55, display_val, ha="center", va="center",
            fontsize=48, fontweight="bold", color=color, transform=ax.transAxes)
    ax.text(0.5, 0.15, title, ha="center", va="center",
            fontsize=11, color="#666666", transform=ax.transAxes)

    return _save(fig, name)


def render_horizontal_bar(name: str, title: str, data: dict[str, float], **kwargs) -> Path:
    """Horizontal bar chart."""
    _apply_style()
    fig, ax = plt.subplots(figsize=(10, max(4, len(data) * 0.8)))

    labels = list(data.keys())
    values = [v if v is not None else 0 for v in data.values()]

    colors = plt.cm.Set2(np.linspace(0, 1, max(len(labels), 1)))
    bars = ax.barh(labels, values, color=colors)

    for bar, val in zip(bars, values):
        if val:
            ax.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2,
                    str(int(val)), va="center", fontsize=10, fontweight="bold")

    ax.set_xlabel("Count")
    ax.set_title(title, fontsize=13, fontweight="bold")
    return _save(fig, name)


def render_area(name: str, title: str, data: dict[str, int], **kwargs) -> Path:
    """Area chart (single series)."""
    _apply_style()
    fig, ax = plt.subplots(figsize=(10, 5))

    labels = list(data.keys())
    values = [v if v is not None else 0 for v in data.values()]

    ax.fill_between(range(len(labels)), values, alpha=0.3, color=COLORS["blue"])
    ax.plot(range(len(labels)), values, color=COLORS["blue"], linewidth=2)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_title(title, fontsize=13, fontweight="bold")
    return _save(fig, name)


def render_heatmap(name: str, title: str, data: dict[str, dict[str, int]], **kwargs) -> Path:
    """Heatmap."""
    _apply_style()

    y_labels = list(data.keys())
    if not y_labels:
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.text(0.5, 0.5, "No Data", ha="center", va="center", transform=ax.transAxes)
        ax.set_title(title, fontsize=13, fontweight="bold")
        return _save(fig, name)

    x_labels = sorted({x for row in data.values() for x in row.keys()})
    matrix = [[data[y].get(x, 0) for x in x_labels] for y in y_labels]

    fig, ax = plt.subplots(figsize=(max(10, len(x_labels) * 1.2), max(4, len(y_labels) * 0.8)))
    arr = np.array(matrix)
    im = ax.imshow(arr, aspect="auto", cmap="YlOrRd")

    ax.set_xticks(range(len(x_labels)))
    ax.set_xticklabels(x_labels, rotation=45, ha="right", fontsize=9)
    ax.set_yticks(range(len(y_labels)))
    ax.set_yticklabels(y_labels, fontsize=9)

    for i in range(len(y_labels)):
        for j in range(len(x_labels)):
            val = arr[i, j]
            if val > 0:
                ax.text(j, i, str(int(val)), ha="center", va="center", fontsize=9)

    fig.colorbar(im, ax=ax, shrink=0.8)
    ax.set_title(title, fontsize=13, fontweight="bold")
    return _save(fig, name)


def render_stacked_bar_with_trend(name: str, title: str, data: dict[str, dict[str, int]], **kwargs) -> Path:
    """Stacked bar chart with rolling average trend line on total."""
    _apply_style()
    fig, ax = plt.subplots(figsize=(10, 5))

    x_labels = list(data.keys())
    if not x_labels:
        ax.text(0.5, 0.5, "No Data", ha="center", va="center", transform=ax.transAxes)
        ax.set_title(title, fontsize=13, fontweight="bold")
        return _save(fig, name)

    segments = sorted({s for d in data.values() for s in d.keys()})
    x = np.arange(len(x_labels))
    bottoms = np.zeros(len(x_labels))
    totals = np.zeros(len(x_labels))

    seg_colors = plt.cm.Set2(np.linspace(0, 1, max(len(segments), 1)))
    for i, seg in enumerate(segments):
        values = np.array([data[xl].get(seg, 0) for xl in x_labels])
        ax.bar(x, values, bottom=bottoms, label=seg, color=seg_colors[i % len(seg_colors)], alpha=0.85)
        bottoms += values
        totals += values

    # Trend line on total
    if len(totals) >= 3:
        window = min(4, len(totals))
        avg = []
        for i in range(len(totals)):
            start = max(0, i - window + 1)
            avg.append(totals[start:i + 1].sum() / (i - start + 1))
        ax.plot(x, avg, color=COLORS["orange"], linewidth=2.5, linestyle="--", label=f"Avg ({window}w)")

    ax.set_xticks(x)
    ax.set_xticklabels(x_labels, rotation=45, ha="right")
    ax.legend(loc="upper left", fontsize=9)
    ax.set_title(title, fontsize=13, fontweight="bold")
    return _save(fig, name)


RENDERERS = {
    "bar": render_bar,
    "stacked_bar": render_stacked_bar,
    "stacked_bar_with_trend": render_stacked_bar_with_trend,
    "dual_area": render_dual_area,
    "bar_with_trend": render_bar_with_trend,
    "big_number": render_big_number,
    "horizontal_bar": render_horizontal_bar,
    "area": render_area,
    "heatmap": render_heatmap,
}
