"""Dimension resolvers — slice issue populations by week, quarter, label, value, status."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from . import jira_client
from .windows import week_boundaries, week_label


def _parse_week_spec(spec) -> tuple[int, str]:
    """Parse by_week spec — supports string or dict with window + date_field."""
    if isinstance(spec, str):
        window = spec
        date_field = "resolved"
    elif isinstance(spec, dict):
        window = spec.get("window", "last_56d")
        date_field = spec.get("date_field", "resolved")
    else:
        window = "last_56d"
        date_field = "resolved"

    if isinstance(window, str) and window.startswith("last_"):
        days = int(window.replace("last_", "").replace("d", ""))
    else:
        days = 56

    return days // 7, date_field


def resolve_dimension(dim_spec: dict, base_jql: str, settings: dict) -> dict[str, Any]:
    """Dispatch to the appropriate dimension resolver. Returns {segment_label: count}."""
    if "by_week" in dim_spec:
        num_weeks, date_field = _parse_week_spec(dim_spec["by_week"])
        return _by_week(base_jql, num_weeks, date_field)
    elif "by_quarter" in dim_spec:
        return _by_quarter(base_jql, dim_spec["by_quarter"], settings)
    elif "by_value" in dim_spec:
        return _by_value(base_jql, dim_spec["by_value"])
    elif "by_label_prefix" in dim_spec:
        return _by_label_prefix(base_jql, dim_spec["by_label_prefix"], settings)
    elif "by_status" in dim_spec:
        return _by_status(base_jql, dim_spec["by_status"])
    else:
        raise ValueError(f"Unknown dimension spec: {dim_spec}")


def resolve_dimension_jql(dim_spec: dict, base_jql: str, settings: dict) -> dict[str, str]:
    """Return {display_label: full_jql} for each segment."""
    if "by_week" in dim_spec:
        num_weeks, date_field = _parse_week_spec(dim_spec["by_week"])
        weeks = week_boundaries(num_weeks)
        result = {}
        for monday, sunday in weeks:
            sun1 = sunday + timedelta(days=1)
            jql = f'{base_jql} AND {date_field} >= "{monday}" AND {date_field} <= "{sun1}"'
            result[week_label(monday)] = jql
        return result
    elif "by_quarter" in dim_spec:
        quarter_labels = dim_spec["by_quarter"]
        quarter_config = settings.get("quarters", [])
        label_to_name = {q["label"]: q["name"] for q in quarter_config}
        result = {}
        for label in quarter_labels:
            name = label_to_name.get(label, label)
            result[name] = f'{base_jql} AND labels = "{label}"'
        return result
    elif "by_value" in dim_spec:
        segments = dim_spec["by_value"]
        result = {}
        for name, extra_jql in segments.items():
            result[name] = f"{base_jql} AND {extra_jql}"
        return result
    elif "by_label_prefix" in dim_spec:
        prefix = dim_spec["by_label_prefix"]
        labels = settings.get("closure_labels", [])
        result = {}
        for label in labels:
            if label.lower().startswith(prefix.lower()):
                result[label] = f'{base_jql} AND labels = "{label}"'
        return result
    elif "by_status" in dim_spec:
        statuses = dim_spec["by_status"]
        result = {}
        for status in statuses:
            result[status] = f'{base_jql} AND status = "{status}"'
        return result
    else:
        raise ValueError(f"Unknown dimension spec: {dim_spec}")


def _by_week(base_jql: str, num_weeks: int, date_field: str) -> dict[str, int]:
    """Count issues per Monday-start week using the specified date field."""
    weeks = week_boundaries(num_weeks)
    results = {}

    for monday, sunday in weeks:
        sun1 = sunday + timedelta(days=1)
        jql = f'{base_jql} AND {date_field} >= "{monday}" AND {date_field} <= "{sun1}"'
        results[week_label(monday)] = jira_client.count(jql)

    return results


def _by_quarter(base_jql: str, quarter_labels: list[str], settings: dict) -> dict[str, int]:
    """Count issues per quarter label."""
    quarter_config = settings.get("quarters", [])
    label_to_name = {q["label"]: q["name"] for q in quarter_config}

    results = {}
    for label in quarter_labels:
        name = label_to_name.get(label, label)
        jql = f'{base_jql} AND labels = "{label}"'
        results[name] = jira_client.count(jql)

    return results


def _by_value(base_jql: str, segments: dict[str, str]) -> dict[str, int]:
    """Count issues per named segment (each segment adds JQL)."""
    results = {}
    for name, extra_jql in segments.items():
        jql = f"{base_jql} AND {extra_jql}"
        results[name] = jira_client.count(jql)
    return results


def _by_label_prefix(base_jql: str, prefix: str, settings: dict) -> dict[str, int]:
    """Count issues per closure-reason label matching a prefix."""
    labels = settings.get("closure_labels", [])
    results = {}
    for label in labels:
        if label.lower().startswith(prefix.lower()):
            jql = f'{base_jql} AND labels = "{label}"'
            results[label] = jira_client.count(jql)
    return results


def _by_status(base_jql: str, statuses: list[str]) -> dict[str, int]:
    """Count issues per status value."""
    results = {}
    for status in statuses:
        jql = f'{base_jql} AND status = "{status}"'
        results[status] = jira_client.count(jql)
    return results
