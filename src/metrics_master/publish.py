"""Pipeline orchestrator — delegates to MetricEngine, renders charts, publishes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import jira_client, confluence_client, quarterly_report
from .engine import MetricEngine, MetricResult
from .registry import load_all_metrics, load_settings
from .render.charts import RENDERERS
from .render.page_builder import build_page
from .render.quarterly_report_builder import build_quarterly_report_page

PAGE_TITLE = "Computed Metrics MA"
QUARTERLY_REPORT_TITLE_SUFFIX = " - Quarterly Metrics Summary"


def run(metric_filter: str | None = None, dry_run: bool = False, weekly: bool = False) -> dict[str, Any]:
    """Execute the full pipeline. Returns summary dict."""
    settings = load_settings()
    configs = load_all_metrics()

    if metric_filter:
        configs = [m for m in configs if m["name"] == metric_filter]
        if not configs:
            return {"error": f"Metric '{metric_filter}' not found"}

    if weekly:
        weekly_names = set(settings.get("weekly_metrics", []))
        configs = [m for m in configs if m["name"] in weekly_names]
        if not configs:
            return {"error": "No weekly metrics configured (see weekly_metrics in config/settings.yaml)"}

    engine = MetricEngine(settings)
    results = engine.compute_all(configs)

    chart_files: dict[str, Path] = {}
    errors: list[str] = []

    for config, result in zip(configs, results):
        if result.error:
            errors.append(f"{result.name}: {result.error}")
        try:
            chart_files[result.name] = _render(config, result)
        except Exception as e:
            errors.append(f"{result.name} render: {e}")

    sections = _organize_sections(results, settings)
    page_html = build_page(sections, chart_files)

    if dry_run:
        output_path = Path("output/page_preview.html")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(page_html)
        return {
            "status": "dry_run",
            "metrics_computed": len(results),
            "errors": errors,
            "preview": str(output_path),
        }

    page_id = confluence_client.publish_page(PAGE_TITLE, page_html)
    for chart_path in chart_files.values():
        confluence_client.upload_attachment(page_id, chart_path)

    jira_client.close()
    confluence_client.close()
    return {
        "status": "published",
        "page_id": page_id,
        "metrics_computed": len(results),
        "errors": errors,
    }


def run_quarterly_report(quarter_label: str, dry_run: bool = False) -> dict[str, Any]:
    """Compute and publish the per-quarter Quarterly Metrics Summary report page.

    Distinct from run(): lives under confluence.quarterly_report_parent_page_id,
    one page per quarter (idempotent per quarter_label), never touches
    "Computed Metrics MA" or its parent.
    """
    settings = load_settings()
    light_cycles_data = quarterly_report.compute_light_cycles_section(quarter_label, settings)
    cve_data = quarterly_report.compute_cve_section(quarter_label, settings)
    research_projects_data = quarterly_report.compute_research_projects_section(quarter_label, settings)
    tio_response_rate_data = quarterly_report.compute_tio_response_rate_section(
        quarter_label, settings,
        light_cycles_data["rows"], cve_data["rows"],
    )
    section_data = {
        "light_cycles": light_cycles_data,
        "cves": cve_data,
        "research_projects": research_projects_data,
        "tio_response_rate": tio_response_rate_data,
    }
    title = f"{quarter_label}{QUARTERLY_REPORT_TITLE_SUFFIX}"
    page_html = build_quarterly_report_page(quarter_label, section_data)

    summary_fields = {
        "total_light_cycles": light_cycles_data["total_light_cycles"],
        "total_idds": light_cycles_data["total_idds"],
        "total_cves": cve_data["total_cves"],
        "total_cve_idds": cve_data["total_idds"],
        "total_research_projects": research_projects_data["total_research_projects"],
        "total_thread_events": tio_response_rate_data["total_thread_events"],
        "atdt_emulations": tio_response_rate_data["atdt_emulations"],
        "response_rate": tio_response_rate_data["response_rate"],
    }

    if dry_run:
        output_path = Path("output/quarterly_report_preview.html")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(page_html)
        return {
            "status": "dry_run",
            "quarter": quarter_label,
            **summary_fields,
            "preview": str(output_path),
        }

    parent_id = settings.get("confluence", {}).get("quarterly_report_parent_page_id")
    if not parent_id:
        return {"error": "confluence.quarterly_report_parent_page_id not set in config/settings.yaml"}

    page_id = confluence_client.publish_named_page(
        title=title,
        parent_id=str(parent_id),
        body_html=page_html,
        state_key=f"quarterly_summary:{quarter_label}",
    )

    jira_client.close()
    confluence_client.close()
    return {
        "status": "published",
        "page_id": page_id,
        "title": title,
        **summary_fields,
        "errors": [],
    }


def _render(config: dict, result: MetricResult) -> Path:
    """Render the chart for a computed metric."""
    chart_type = config["chart"]
    renderer = RENDERERS.get(chart_type, RENDERERS["bar"])
    data = result.data
    name = result.name
    title = result.title
    chart_kwargs = config.get("chart_kwargs", {})

    if chart_type == "big_number":
        value = data if isinstance(data, (int, float)) else None
        return renderer(name, title, value, target=config.get("target"))

    if data is None:
        data = {"No Data": 0}

    if chart_kwargs.get("footer_totals") and isinstance(data, dict):
        total = sum(
            v for inner in data.values()
            for v in (inner.values() if isinstance(inner, dict) else [inner])
            if isinstance(v, (int, float))
        )
        period = chart_kwargs.get("period_description", "")
        chart_kwargs["footer"] = f"Total Issues: {total}    |    Period: {period}"

    if chart_kwargs.get("footer_created_resolved") and isinstance(data, dict):
        total_created = sum(d.get("Created", 0) for d in data.values() if isinstance(d, dict))
        total_resolved = sum(d.get("Resolved", 0) for d in data.values() if isinstance(d, dict))
        period = chart_kwargs.get("period_description", "")
        chart_kwargs["footer"] = f"Issues: {total_created} created and {total_resolved} resolved    |    Period: {period}"

    return renderer(name, title, data, **chart_kwargs)



def _organize_sections(results: list[MetricResult], settings: dict) -> list[dict]:
    """Group metric results into sections per settings."""
    result_map = {r.name: r for r in results}
    sections = []

    for section_cfg in settings.get("sections", []):
        section_metrics = []
        for metric_name in section_cfg.get("metrics", []):
            r = result_map.get(metric_name)
            if r:
                section_metrics.append({
                    "name": r.name,
                    "title": r.title,
                    "description": r.description,
                    "summary": r.summary,
                    "target": r.target,
                    "rag": r.rag,
                })
        if section_metrics:
            sections.append({"name": section_cfg["name"], "metrics": section_metrics})

    return sections
