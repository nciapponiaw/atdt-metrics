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

    Uses green for 'Completed'/'Done'/'Resolved'/'Emulation Completed' and red for others.
    """
    _apply_style()
    hide_title = kwargs.get("hide_title", False)
    fig, ax = plt.subplots(figsize=(14, 9))

    x_labels = list(data.keys())
    if not x_labels:
        ax.text(0.5, 0.5, "No Data", ha="center", va="center", transform=ax.transAxes, fontsize=14)
        if not hide_title:
            ax.set_title(title, fontsize=15, fontweight="bold")
        return _save(fig, name)

    segments = sorted({s for d in data.values() for s in d.keys()})
    x = np.arange(len(x_labels))
    bottoms = np.zeros(len(x_labels))

    positive_names = {"Completed", "Done", "Resolved", "Emulation Completed", "IDD Completed"}
    for seg in segments:
        values = [data[xl].get(seg, 0) for xl in x_labels]
        color = COLORS["green"] if seg in positive_names else COLORS["red"]
        ax.bar(x, values, bottom=bottoms, label=seg, color=color, alpha=0.85)
        bottoms += np.array(values)

    ax.set_xticks(x)
    ax.set_xticklabels(x_labels, rotation=45, ha="right", fontsize=18)
    ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
    ax.tick_params(axis="y", labelsize=18)
    ax.set_ylabel(kwargs.get("ylabel", "Issues"), fontsize=20)

    if not hide_title:
        ax.set_title(title, fontsize=22, fontweight="bold", pad=30)

    ax.legend(
        loc="lower center", bbox_to_anchor=(0.5, 1.02),
        ncol=len(segments), fontsize=20, frameon=False,
        handlelength=2.5, handletextpad=1.0, columnspacing=3.5,
        markerscale=1.5,
    )

    footer = kwargs.get("footer")
    if footer:
        fig.subplots_adjust(bottom=0.25, top=0.86)
        fig.text(0.5, 0.02, footer, ha="center", fontsize=16, color="#666666")
    else:
        fig.subplots_adjust(bottom=0.20, top=0.86)

    return _save(fig, name)


def render_dual_area(name: str, title: str, data: dict[str, dict[str, int]], **kwargs) -> Path:
    """Dual area/line chart for created vs resolved."""
    _apply_style()
    hide_title = kwargs.get("hide_title", False)
    fig, ax = plt.subplots(figsize=(14, 9))

    x_labels = list(data.keys())
    if not x_labels:
        ax.text(0.5, 0.5, "No Data", ha="center", va="center", transform=ax.transAxes, fontsize=14)
        if not hide_title:
            ax.set_title(title, fontsize=22, fontweight="bold")
        return _save(fig, name)

    created = [data[wk].get("Created", 0) for wk in x_labels]
    resolved = [data[wk].get("Resolved", 0) for wk in x_labels]
    x = range(len(x_labels))

    ax.fill_between(x, created, alpha=0.25, color=COLORS["red"])
    ax.plot(x, created, color=COLORS["red"], linewidth=3, marker="o", markersize=8, label="Created")
    ax.fill_between(x, resolved, alpha=0.25, color=COLORS["green"])
    ax.plot(x, resolved, color=COLORS["green"], linewidth=3, marker="o", markersize=8, label="Resolved")

    ax.set_xticks(list(x))
    ax.set_xticklabels(x_labels, rotation=0, ha="center", fontsize=18)
    ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
    ax.tick_params(axis="y", labelsize=18)
    ax.set_ylabel(kwargs.get("ylabel", "Issues"), fontsize=20)

    if not hide_title:
        ax.set_title(title, fontsize=22, fontweight="bold", pad=30)

    ax.legend(
        loc="lower center", bbox_to_anchor=(0.5, -0.22),
        ncol=2, fontsize=20, frameon=False,
        handlelength=2.5, handletextpad=1.0, columnspacing=3.5,
    )

    footer = kwargs.get("footer")
    if footer:
        fig.subplots_adjust(bottom=0.25, top=0.92)
        fig.text(0.5, 0.02, footer, ha="center", fontsize=16, color="#666666")
    else:
        fig.subplots_adjust(bottom=0.22, top=0.92)

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


def render_bar_with_velocity(name: str, title: str, data: dict[str, Any], **kwargs) -> Path:
    """Combo bar + line chart for team velocity."""
    _apply_style()
    hide_title = kwargs.get("hide_title", False)
    fig, ax = plt.subplots(figsize=(14, 9))

    weeks_data = data.get("weeks", {})
    last_completed = data.get("last_completed", 0)
    avg_velocity = data.get("avg_velocity", 0)

    if not weeks_data:
        ax.text(0.5, 0.5, "No Data", ha="center", va="center", transform=ax.transAxes, fontsize=14)
        return _save(fig, name)

    x_labels = list(weeks_data.keys())
    completed = [weeks_data[wk]["completed"] for wk in x_labels]
    avg_line = [weeks_data[wk]["avg_velocity"] for wk in x_labels]
    x = np.arange(len(x_labels))

    # Summary stats above chart
    fig.text(0.25, 0.92, str(last_completed), ha="center", fontsize=36, fontweight="bold", color=COLORS["purple"])
    fig.text(0.25, 0.88, "Completed in last interval", ha="center", fontsize=14, color="#555555")
    fig.text(0.75, 0.92, f"{avg_velocity:.2f}", ha="center", fontsize=36, fontweight="bold", color=COLORS["orange"])
    fig.text(0.75, 0.88, "Avg velocity in last 8 intervals", ha="center", fontsize=14, color="#555555")

    # Bars
    bars = ax.bar(x, completed, color=COLORS["purple"], alpha=0.85, label="Completed", width=0.6)
    for bar, val in zip(bars, completed):
        if val:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.1,
                    str(val), ha="center", va="bottom", fontsize=16, fontweight="bold", color=COLORS["purple"])

    # Average velocity line
    ax.plot(x, avg_line, color=COLORS["orange"], linewidth=3, marker="o", markersize=8, label="Average Velocity")

    ax.set_xticks(x)
    ax.set_xticklabels(x_labels, rotation=30, ha="right", fontsize=14)
    ax.set_xlabel("Time intervals", fontsize=16, labelpad=10)
    ax.set_ylabel("Work Item Count", fontsize=18)
    ax.yaxis.set_major_locator(plt.MaxNLocator(integer=False))
    ax.tick_params(axis="y", labelsize=16)
    ax.grid(axis="y", alpha=0.4)

    if not hide_title:
        ax.set_title(title, fontsize=22, fontweight="bold", pad=60)

    fig.subplots_adjust(bottom=0.32, top=0.85)
    fig.legend(
        ax.get_legend_handles_labels()[0], ax.get_legend_handles_labels()[1],
        loc="lower center", bbox_to_anchor=(0.5, 0.02),
        ncol=2, fontsize=18, frameon=False,
        handlelength=2.5, handletextpad=1.0, columnspacing=3.5,
    )

    return _save(fig, name)


def render_pie(name: str, title: str, data: dict[str, Any], **kwargs) -> Path:
    """Pie chart with leader-line labels showing 'Status = count'."""
    _apply_style()
    hide_title = kwargs.get("hide_title", False)
    fig, ax = plt.subplots(figsize=(14, 9))

    if not data or all(v == 0 for v in data.values()):
        ax.text(0.5, 0.5, "No Data", ha="center", va="center", transform=ax.transAxes, fontsize=14)
        if not hide_title:
            ax.set_title(title, fontsize=22, fontweight="bold")
        return _save(fig, name)

    filtered = {k: v for k, v in data.items() if v and v > 0}
    labels = list(filtered.keys())
    values = list(filtered.values())

    pie_colors = plt.cm.Set3(np.linspace(0, 1, max(len(labels), 1)))

    wedges, texts = ax.pie(
        values,
        labels=None,
        startangle=90,
        colors=pie_colors,
    )

    label_texts = [f"{lbl} = {val}" for lbl, val in zip(labels, values)]
    ax.legend(
        wedges, label_texts,
        loc="center left", bbox_to_anchor=(1.0, 0.5),
        fontsize=18, frameon=False,
        labelspacing=1.2,
    )

    if not hide_title:
        ax.set_title(title, fontsize=22, fontweight="bold", pad=20)

    footer = kwargs.get("footer")
    if footer:
        fig.subplots_adjust(bottom=0.12)
        fig.text(0.5, 0.02, footer, ha="center", fontsize=16, color="#666666")

    return _save(fig, name)


RENDERERS = {
    "bar": render_bar,
    "stacked_bar": render_stacked_bar,
    "stacked_bar_with_trend": render_stacked_bar_with_trend,
    "dual_area": render_dual_area,
    "bar_with_trend": render_bar_with_trend,
    "bar_with_velocity": render_bar_with_velocity,
    "big_number": render_big_number,
    "horizontal_bar": render_horizontal_bar,
    "area": render_area,
    "heatmap": render_heatmap,
    "pie": render_pie,
}
