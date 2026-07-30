"""Metric registry — loads YAML configs, resolves templates, validates."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from .calendar import current_quarter_label, all_quarter_labels


METRICS_DIR = Path("config/metrics")
_TEMPLATE_RE = re.compile(r"\{\{(\w+)\}\}")


def load_metric(name: str, quarter_override: str | None = None) -> dict[str, Any]:
    """Load a single metric config by name, resolving template variables."""
    path = METRICS_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Metric config not found: {path}")
    config = yaml.safe_load(path.read_text())
    return _resolve_templates(config, _build_context(quarter_override))


def load_all_metrics(quarter_override: str | None = None) -> list[dict[str, Any]]:
    """Load all metric configs, resolving template variables."""
    context = _build_context(quarter_override)
    metrics = []
    if not METRICS_DIR.exists():
        return metrics
    for path in sorted(METRICS_DIR.glob("*.yaml")):
        config = yaml.safe_load(path.read_text())
        if config:
            metrics.append(_resolve_templates(config, context))
    return metrics


def load_settings() -> dict[str, Any]:
    """Load the global settings file."""
    path = Path("config/settings.yaml")
    if not path.exists():
        raise FileNotFoundError("config/settings.yaml not found")
    return yaml.safe_load(path.read_text())


def validate_metric(config: dict) -> list[str]:
    """Validate a metric config. Returns list of error messages (empty = valid)."""
    errors = []
    required = ["name", "title", "filter", "measure", "chart"]
    for field in required:
        if field not in config:
            errors.append(f"Missing required field: {field}")

    measure = config.get("measure", {})
    if "kind" not in measure:
        errors.append("measure.kind is required")

    valid_kinds = {"count", "duration", "ratio", "coverage", "created_vs_resolved"}
    if measure.get("kind") not in valid_kinds:
        errors.append(f"measure.kind must be one of {valid_kinds}")

    valid_charts = {
        "bar", "stacked_bar", "stacked_bar_with_trend", "dual_area",
        "bar_with_trend", "area", "heatmap", "big_number", "horizontal_bar",
    }
    if config.get("chart") not in valid_charts:
        errors.append(f"chart must be one of {valid_charts}")

    return errors


def _build_context(quarter_override: str | None = None) -> dict[str, str]:
    """Build template variable context."""
    settings = load_settings()
    fy_start = settings.get("fiscal_year_start_month", 5)
    pattern = settings.get("quarter_label_pattern", "ATDT_FY{fy}Q{q}")

    if quarter_override:
        current = quarter_override
    elif settings.get("current_quarter"):
        current = settings["current_quarter"]
    else:
        current = current_quarter_label(fy_start_month=fy_start, pattern=pattern)

    quarters = all_quarter_labels(3, fy_start_month=fy_start, pattern=pattern)

    return {
        "current_quarter": current,
        "prev_quarter": quarters[1] if len(quarters) > 1 else "",
        "prev_prev_quarter": quarters[2] if len(quarters) > 2 else "",
    }


def _resolve_templates(obj: Any, context: dict[str, str]) -> Any:
    """Recursively substitute {{var}} in strings within a config dict/list."""
    if isinstance(obj, str):
        return _TEMPLATE_RE.sub(lambda m: context.get(m.group(1), m.group(0)), obj)
    elif isinstance(obj, dict):
        return {k: _resolve_templates(v, context) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_resolve_templates(item, context) for item in obj]
    return obj
