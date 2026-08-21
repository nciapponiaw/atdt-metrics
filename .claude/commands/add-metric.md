---
description: "Scaffold, fill in, register, and validate a new ATDT metric end-to-end — creates the YAML, adds it to a config/settings.yaml section, and dry-runs it."
argument-hint: "<metric_name> — e.g. escalation_rate"
agent: metric-author
model: sonnet
effort: medium
disable-model-invocation: true
---
Create a new metric end-to-end.

## Input
$ARGUMENTS — the new metric's slug (snake_case; becomes `config/metrics/<name>.yaml`).

## Pipeline
1. Scaffold: `python -m metrics_master.cli add-metric <name>` creates `config/metrics/<name>.yaml` from the template. If the file already exists, stop and ask the user before overwriting anything.
2. Fill in the template based on the user's requirements: `title`, `description`, `filter` (JQL — count-first, `AND issuetype != Sub-task` on every emulation-scoped filter, `{{current_quarter}}` never a hardcoded label), `measure` (pick the right `kind`: `count` / `coverage` / `created_vs_resolved` / `ratio` / `duration`), `group_by` if the metric needs a breakdown, `chart`, `target`.
3. Register the metric name under the right section list in `config/settings.yaml` (`sections:`). If it's weekly-cadence, also add it to `weekly_metrics:`.
4. Validate: `python -m metrics_master.cli validate --metric <name>`. Fix and re-run until it passes.
5. Dry-run: `python -m metrics_master.cli run --dry-run --metric <name>`. Confirm it renders (no error, a sensible summary) before handing back to the user.

## Constraints
- Never publish — dry-run only. The user runs `/run-metrics` themselves when ready.
- Never hardcode a quarter label — always `{{current_quarter}}` / `{{prev_quarter}}` / `{{prev_prev_quarter}}`.
- Every emulation-scoped filter (labels include `ATDT_CVE` or `LightCycles`) MUST exclude Sub-tasks.
- Default to `count()`; only reach for a `ratio` with link traversal (`links.py`) when a genuine per-issue relationship is needed.

## Output
The final YAML content, the section it was registered under, and the dry-run summary line.
