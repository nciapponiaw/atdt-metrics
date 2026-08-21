"""CLI entry point: python -m metrics_master.cli run|compute|validate|add-metric."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from .registry import load_all_metrics, load_metric, load_settings, validate_metric
from .publish import run, run_quarterly_report
from .engine import MetricEngine


def main() -> None:
    parser = argparse.ArgumentParser(prog="metrics-master", description="ATDT Metrics Pipeline")
    subparsers = parser.add_subparsers(dest="command")

    # run
    run_parser = subparsers.add_parser("run", help="Execute pipeline and publish")
    run_parser.add_argument("--metric", help="Run a single metric by name")
    run_parser.add_argument("--dry-run", action="store_true", help="Render locally, don't publish")
    run_parser.add_argument("--quarter", help="Override quarter (e.g., ATDT_FY27Q1)")
    run_parser.add_argument(
        "--weekly", action="store_true",
        help="Run only the weekly-cadence metrics listed under weekly_metrics in config/settings.yaml",
    )

    # compute
    compute_parser = subparsers.add_parser("compute", help="Compute metrics (no render/publish)")
    compute_parser.add_argument("--metric", help="Compute a single metric by name")
    compute_parser.add_argument("--quarter", help="Override quarter label")
    compute_parser.add_argument("--format", choices=["json", "text"], default="text")

    # validate
    val_parser = subparsers.add_parser("validate", help="Validate metric configs")
    val_parser.add_argument("--metric", help="Validate a single metric by name")

    # add-metric
    add_parser = subparsers.add_parser("add-metric", help="Create a new metric config from template")
    add_parser.add_argument("name", help="Metric slug (e.g., my_new_metric)")

    args = parser.parse_args()

    if args.command == "run":
        if args.quarter:
            if args.metric or args.weekly:
                print(
                    "ERROR: --quarter cannot be combined with --metric or --weekly "
                    "(it targets the Quarterly Metrics Summary report, not the regular metrics page)",
                    file=sys.stderr,
                )
                sys.exit(1)
            summary = run_quarterly_report(quarter_label=args.quarter, dry_run=args.dry_run)
        else:
            summary = run(
                metric_filter=args.metric,
                dry_run=args.dry_run,
                weekly=args.weekly,
            )
        print(json.dumps(summary, indent=2))
        if summary.get("errors") or summary.get("error"):
            sys.exit(1)

    elif args.command == "compute":
        settings = load_settings()
        engine = MetricEngine(settings)

        if args.metric:
            config = load_metric(args.metric, quarter_override=args.quarter)
            results = [engine.compute(config)]
        else:
            configs = load_all_metrics(quarter_override=args.quarter)
            results = engine.compute_all(configs)

        if args.format == "json":
            output = [
                {"name": r.name, "summary": r.summary, "data": r.data, "error": r.error}
                for r in results
            ]
            print(json.dumps(output, indent=2, default=str))
        else:
            for r in results:
                status = r.summary if not r.error else f"ERROR: {r.error}"
                print(f"  {r.name}: {status}")

    elif args.command == "validate":
        if args.metric:
            config = load_metric(args.metric)
            errors = validate_metric(config)
        else:
            all_metrics = load_all_metrics()
            errors = []
            for m in all_metrics:
                errs = validate_metric(m)
                errors.extend([f"{m.get('name', '?')}: {e}" for e in errs])

        if errors:
            for e in errors:
                print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)
        else:
            print("All metrics valid.")

    elif args.command == "add-metric":
        _create_template(args.name)

    else:
        parser.print_help()


def _create_template(name: str) -> None:
    """Create a new metric YAML from template."""
    path = Path(f"config/metrics/{name}.yaml")
    if path.exists():
        print(f"ERROR: {path} already exists", file=sys.stderr)
        sys.exit(1)

    template = {
        "name": name,
        "title": "FILL_ME",
        "description": "FILL_ME",
        "filter": "project = SHLD AND issuetype != Sub-task AND labels = {{current_quarter}} AND FILL_ME",
        "measure": {"kind": "count"},
        "group_by": [],
        "chart": "bar",
        "target": None,
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(template, default_flow_style=False, sort_keys=False))
    print(f"Created: {path}")


if __name__ == "__main__":
    main()
