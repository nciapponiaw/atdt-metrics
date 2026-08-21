"""MetricEngine — separates compute/render/publish for scalability and agent readiness."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Any

from . import jira_client
from .dimensions import resolve_dimension, resolve_dimension_jql
from .measures import compute_count, compute_duration
from .links import count_with_linked_idds
from .windows import week_boundaries, week_label


@dataclass
class MetricResult:
    name: str
    title: str
    description: str
    data: Any
    summary: str | None
    target: Any = None
    rag: str | None = None
    error: str | None = None


class MetricEngine:
    """Computes metrics from config + Jira data. Stateless per call."""

    def __init__(self, settings: dict):
        self.settings = settings

    def compute(self, config: dict) -> MetricResult:
        """Compute a single metric. Returns structured result (no side effects)."""
        try:
            data, summary = self._dispatch(config)
            return MetricResult(
                name=config["name"],
                title=config["title"],
                description=config.get("description", ""),
                data=data,
                summary=summary,
                target=config.get("target"),
            )
        except Exception as e:
            return MetricResult(
                name=config["name"],
                title=config["title"],
                description=config.get("description", ""),
                data=None,
                summary=None,
                error=str(e),
            )

    def compute_all(self, configs: list[dict]) -> list[MetricResult]:
        """Compute all metrics in sequence."""
        return [self.compute(c) for c in configs]

    def _dispatch(self, config: dict) -> tuple[Any, str | None]:
        """Route to the appropriate computation based on measure.kind."""
        kind = config["measure"]["kind"]
        dispatch = {
            "count": self._compute_count,
            "coverage": self._compute_coverage,
            "created_vs_resolved": self._compute_created_vs_resolved,
            "ratio": self._compute_ratio,
            "duration": self._compute_duration,
            "velocity": self._compute_velocity,
        }
        handler = dispatch.get(kind)
        if not handler:
            return None, f"Unknown measure kind: {kind}"
        return handler(config)

    def _compute_count(self, config: dict) -> tuple[Any, str]:
        base_jql = config["filter"].strip()
        group_by = config.get("group_by", [])

        if not group_by:
            value = compute_count(base_jql)
            return value, f"Count: {value}"

        if len(group_by) == 1:
            data = resolve_dimension(group_by[0], base_jql, self.settings)
            total = sum(v for v in data.values() if isinstance(v, (int, float)))
            return data, f"Total: {total}"

        # Two dimensions → nested dict (heatmap/stacked)
        dim1_jql = resolve_dimension_jql(group_by[0], base_jql, self.settings)
        result_data = {}
        for label1, sub_jql in dim1_jql.items():
            result_data[label1] = resolve_dimension(group_by[1], sub_jql, self.settings)
        total = sum(
            v for inner in result_data.values()
            for v in inner.values() if isinstance(v, (int, float))
        )
        return result_data, f"Total: {total}"

    def _compute_coverage(self, config: dict) -> tuple[Any, str]:
        """Cumulative coverage: Done vs Remaining over the quarter."""
        base_jql = config["filter"].strip()
        num_weeks = config["measure"].get("weeks", 13)
        weeks = week_boundaries(num_weeks)

        total_scope = jira_client.count(base_jql)
        data: dict[str, dict[str, int]] = {}

        for monday, sunday in weeks:
            sun1 = sunday + timedelta(days=1)
            done_by_week = jira_client.count(
                f'{base_jql} AND status = Done AND resolved <= "{sun1}"'
            )
            remaining = max(0, total_scope - done_by_week)
            data[week_label(monday)] = {"Done": done_by_week, "Remaining": remaining}

        latest = list(data.values())[-1] if data else {}
        done = latest.get("Done", 0)
        return data, f"{done}/{total_scope} completed ({round(done / total_scope * 100)}%)" if total_scope else "No Data"

    def _compute_created_vs_resolved(self, config: dict) -> tuple[Any, str]:
        base_jql = config["filter"].strip()
        measure = config["measure"]
        num_weeks = measure.get("weeks", 13)
        resolved_extra = measure.get("resolved_filter", "")
        label_format = measure.get("label_format", "default")
        weeks = week_boundaries(num_weeks)

        resolved_jql = f"{base_jql} AND {resolved_extra}" if resolved_extra else base_jql

        data: dict[str, dict[str, int]] = {}
        for monday, sunday in weeks:
            sun1 = sunday + timedelta(days=1)
            created = jira_client.count(f'{base_jql} AND created >= "{monday}" AND created <= "{sun1}"')
            resolved = jira_client.count(f'{resolved_jql} AND resolved >= "{monday}" AND resolved <= "{sun1}"')
            lbl = week_label(monday, day_first=(label_format == "day_first"))
            data[lbl] = {"Created": created, "Resolved": resolved}

        total_created = sum(d["Created"] for d in data.values())
        total_resolved = sum(d["Resolved"] for d in data.values())
        return data, f"Created: {total_created} | Resolved: {total_resolved}"

    def _compute_ratio(self, config: dict) -> tuple[Any, str]:
        measure = config["measure"]
        base_jql = config["filter"].strip()

        if measure.get("numerator_type") == "linked_idd":
            idd_label = self.settings.get("idd_identifier", "ATDT_IDD")
            link_data = count_with_linked_idds(base_jql, idd_label)
            if link_data["total"] > 0:
                ratio = round(link_data["with_idd"] / link_data["total"] * 100, 1)
                summary = f"{ratio}% ({link_data['with_idd']}/{link_data['total']} emulations → {link_data['total_idds']} IDDs)"
                return ratio, summary
            return None, "No Data"

        num_jql = measure.get("numerator_jql", "").strip()
        denom_jql = measure.get("denominator_jql", "").strip()
        if num_jql and denom_jql:
            num = jira_client.count(num_jql)
            denom = jira_client.count(denom_jql)
            if denom > 0:
                ratio = round(num / denom * 100, 1)
                return ratio, f"{ratio}% ({num}/{denom})"
            return None, "No Data"

        return None, "No Data"

    def _compute_velocity(self, config: dict) -> tuple[Any, str]:
        """Compute weekly velocity: completions per week with rolling average."""
        base_jql = config["filter"].strip()
        measure = config["measure"]
        num_weeks = measure.get("weeks", 8)
        display_weeks = measure.get("display_weeks", 5)
        date_field = measure.get("date_field", "resolved")
        weeks = week_boundaries(num_weeks)

        all_counts = []
        for monday, sunday in weeks:
            sun1 = sunday + timedelta(days=1)
            count = jira_client.count(
                f'{base_jql} AND {date_field} >= "{monday}" AND {date_field} <= "{sun1}"'
            )
            all_counts.append((monday, sunday, count))

        avg_velocity = sum(c for _, _, c in all_counts) / len(all_counts) if all_counts else 0

        display_data = {}
        for monday, sunday, count in all_counts[-display_weeks:]:
            label = f"{monday.strftime('%m/%d/%y')} - {sunday.strftime('%m/%d/%y')}"
            trailing = [c for _, _, c in all_counts[:all_counts.index((monday, sunday, count)) + 1]]
            trailing_avg = sum(trailing) / len(trailing) if trailing else 0
            display_data[label] = {"completed": count, "avg_velocity": round(trailing_avg, 2)}

        last_completed = all_counts[-1][2] if all_counts else 0
        summary = f"Last interval: {last_completed} completed | Avg velocity (8w): {avg_velocity:.2f}"

        return {
            "weeks": display_data,
            "last_completed": last_completed,
            "avg_velocity": round(avg_velocity, 2),
        }, summary

    def _compute_duration(self, config: dict) -> tuple[Any, str]:
        base_jql = config["filter"].strip()
        measure = config["measure"]
        span = measure["span"]
        aggregate = measure.get("aggregate", "median")
        group_by = config.get("group_by", [])

        if not group_by:
            result = compute_duration(base_jql, span, aggregate)
            val = result["value"]
            summary = f"Median: {val} days" if val is not None else "No Data"
            return result, summary

        data = {}
        for dim_spec in group_by:
            segments = resolve_dimension_jql(dim_spec, base_jql, self.settings)
            for seg_label, seg_jql in segments.items():
                dur = compute_duration(seg_jql, span, aggregate)
                data[seg_label] = dur.get("values", []) if aggregate == "distribution" else dur.get("value")

        summary_vals = [v for v in data.values() if isinstance(v, (int, float)) and v is not None]
        summary = f"Range: {min(summary_vals):.1f}–{max(summary_vals):.1f} days" if summary_vals else "No Data"
        return data, summary
