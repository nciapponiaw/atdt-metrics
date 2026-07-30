"""Pipeline orchestrator — delegates to MetricEngine, renders charts, publishes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import jira_client, confluence_client
from .engine import MetricEngine, MetricResult
from .registry import load_all_metrics, load_settings
from .render.charts import RENDERERS
from .render.page_builder import build_page

PAGE_TITLE = "Computed Metrics (Automated)"


def run(metric_filter: str | None = None, dry_run: bool = False) -> dict[str, Any]:
    """Execute the full pipeline. Returns summary dict."""
    settings = load_settings()
    configs = load_all_metrics()

    if metric_filter:
        configs = [m for m in configs if m["name"] == metric_filter]
        if not configs:
            return {"error": f"Metric '{metric_filter}' not found"}

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


def _render(config: dict, result: MetricResult) -> Path:
    """Render the chart for a computed metric."""
    chart_type = config["chart"]
    renderer = RENDERERS.get(chart_type, RENDERERS["bar"])
    data = result.data
    name = result.name
    title = result.title

    if chart_type == "big_number":
        value = data if isinstance(data, (int, float)) else None
        return renderer(name, title, value, target=config.get("target"))

    if data is None:
        data = {"No Data": 0}

    return renderer(name, title, data)


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
