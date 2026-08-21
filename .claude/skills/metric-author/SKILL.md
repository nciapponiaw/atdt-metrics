---
name: metric-author
description: "Create and edit ATDT metric YAML configs — the measure-kind schema, JQL conventions, chart types, and config/settings.yaml registration. Use for /add-metric or any metric filter/measure change."
user-invocable: false
---
# Metric Author Skill

## When to Use
- `/add-metric`
- Editing an existing metric's `filter`, `measure`, `group_by`, or `chart`
- Registering a metric in `config/settings.yaml`

## Procedure

### 1. Scaffold
```bash
python -m metrics_master.cli add-metric <name>
```
Writes `config/metrics/<name>.yaml` from a fixed template (`name`, `title`, `description`, `filter`, `measure.kind: count`, `group_by: []`, `chart: bar`, `target: null`). Fails loudly if the file already exists — never overwrite silently.

### 2. Fill the filter (JQL)
See `references/jql-conventions.md`. In short: count-first, `AND issuetype != Sub-task` on every emulation-scoped filter, `{{current_quarter}}` (or `{{prev_quarter}}` / `{{prev_prev_quarter}}`) — never a hardcoded quarter label.

### 3. Pick the measure kind
See `references/metric-schema.md` for the full field reference per kind (`count`, `coverage`, `created_vs_resolved`, `ratio`, `duration`) and the `group_by` dimension types (`by_week`, `by_quarter`, `by_value`, `by_label_prefix`, `by_status`).

### 4. Pick the chart type
One of: `bar`, `stacked_bar`, `stacked_bar_with_trend`, `dual_area`, `bar_with_trend`, `area`, `heatmap`, `big_number`, `horizontal_bar`. `big_number` expects a scalar `data` (typically `count` with no `group_by`, or `ratio`); everything else expects a `{label: value}` mapping or a nested dict (two-dimension `count`).

### 5. Register in config/settings.yaml
Add the metric name to one list under `sections:` (controls what renders and in which group on the page). If the metric is weekly-cadence (a week-by-week chart, or you want it included in `/run-metrics --weekly`), also add it to `weekly_metrics:`.

### 6. Validate, then dry-run
```bash
python -m metrics_master.cli validate --metric <name>
python -m metrics_master.cli run --dry-run --metric <name>
```
Both must succeed before handing the metric back. Never publish from this skill.

## Constraints
- Never hand-edit `dimensions.py`, `engine.py`, or `measures.py` from this skill — a "new metric" is a config change, not a code change. If a genuinely new `measure.kind` or dimension type is needed, that's a separate, explicit task (see `MAINTENANCE.md` → "Add a measure kind").
- Never load raw Jira issues into context. All querying/aggregation happens inside the Python pipeline when it runs — you write config, you don't fetch data yourself.
