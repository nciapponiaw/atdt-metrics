"""Measure resolvers — count, duration, ratio computations."""

from __future__ import annotations

import statistics
from datetime import datetime
from typing import Any

from . import jira_client
from .windows import days_between, parse_date


def compute_count(jql: str) -> int:
    """Simple count of issues matching JQL."""
    return jira_client.count(jql)


def compute_duration(
    jql: str,
    span: str,
    aggregate: str,
    max_results: int = 200,
) -> dict[str, Any]:
    """Compute duration metrics. Returns aggregate value + raw values for distribution."""
    if span == "time_in_status":
        return _compute_time_in_status_aggregated(jql, aggregate, max_results)

    if span == "created_to_resolved":
        fields = ["created", "resolutiondate"]
    elif span == "created_to_in_progress":
        fields = ["created", "key"]
    else:
        raise ValueError(f"Unknown duration span: {span}")

    issues = jira_client.search(jql, fields=fields, max_results=max_results)
    durations: list[float] = []

    for issue in issues:
        f = issue.get("fields", {})
        if span == "created_to_resolved":
            d = days_between(f.get("created"), f.get("resolutiondate"))
            if d is not None and d >= 0:
                durations.append(d)
        elif span == "created_to_in_progress":
            created = parse_date(f.get("created"))
            if not created:
                continue
            key = issue.get("key") or f.get("key")
            if not key:
                continue
            first_ip = _first_transition_to(key, "In Progress")
            if first_ip:
                d = (first_ip - created).total_seconds() / 86400
                if d >= 0:
                    durations.append(d)

    if not durations:
        return {"value": None, "values": [], "count": 0}

    if aggregate == "median":
        value = statistics.median(durations)
    elif aggregate == "mean":
        value = statistics.mean(durations)
    elif aggregate == "p90":
        durations_sorted = sorted(durations)
        idx = int(len(durations_sorted) * 0.9)
        value = durations_sorted[min(idx, len(durations_sorted) - 1)]
    elif aggregate == "distribution":
        value = None
    else:
        value = statistics.median(durations)

    return {
        "value": round(value, 1) if value is not None else None,
        "values": [round(d, 1) for d in durations],
        "count": len(durations),
    }


def compute_ratio(
    numerator_jql: str,
    denominator_jql: str,
) -> dict[str, Any]:
    """Compute a ratio between two counts."""
    num = jira_client.count(numerator_jql)
    denom = jira_client.count(denominator_jql)
    if denom == 0:
        return {"numerator": num, "denominator": denom, "ratio": None}
    return {
        "numerator": num,
        "denominator": denom,
        "ratio": round(num / denom * 100, 1),
    }


def _compute_time_in_status_aggregated(
    jql: str, aggregate: str, max_results: int
) -> dict[str, Any]:
    """Compute median/mean time-in-status across issues. Returns {status: days}."""
    issues = jira_client.search(jql, fields=["key"], max_results=max_results)
    status_durations: dict[str, list[float]] = {}

    for issue in issues:
        key = issue.get("key") or issue.get("fields", {}).get("key")
        if not key:
            continue
        tis = _compute_time_in_status(key)
        for status, days in tis.items():
            status_durations.setdefault(status, []).append(days)

    result: dict[str, float] = {}
    for status, values in status_durations.items():
        if aggregate == "median":
            result[status] = round(statistics.median(values), 1)
        elif aggregate == "mean":
            result[status] = round(statistics.mean(values), 1)
        else:
            result[status] = round(statistics.median(values), 1)

    return {"value": result, "values": result, "count": len(issues)}


def _first_transition_to(issue_key: str, target_status: str) -> datetime | None:
    """Find the first time an issue transitioned to target_status."""
    histories = jira_client.get_issue_changelog(issue_key)
    for history in histories:
        created = history.get("created")
        for item in history.get("items", []):
            if item.get("field") == "status" and item.get("toString") == target_status:
                return parse_date(created)
    return None


def _compute_time_in_status(issue_key: str) -> dict[str, float]:
    """Compute days spent in each status for an issue."""
    histories = jira_client.get_issue_changelog(issue_key)
    time_in_status: dict[str, float] = {}
    current_status = None
    last_transition: datetime | None = None

    for history in sorted(histories, key=lambda h: h.get("created", "")):
        created = parse_date(history.get("created"))
        for item in history.get("items", []):
            if item.get("field") == "status":
                if current_status and last_transition and created:
                    days = (created - last_transition).total_seconds() / 86400
                    time_in_status[current_status] = time_in_status.get(current_status, 0) + days
                current_status = item.get("toString")
                last_transition = created

    return time_in_status
