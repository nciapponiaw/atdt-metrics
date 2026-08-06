# Metric YAML Schema

Every file in `config/metrics/*.yaml` has this shape:

```yaml
name: metric_slug              # must match the filename (without .yaml)
title: "Human title"
description: "One sentence — what this measures and why."
filter: >
  project = SHLD
  AND issuetype != Sub-task    # required on every emulation-scoped metric
  AND labels = {{current_quarter}}
  AND <additional JQL>
measure:
  kind: count | coverage | created_vs_resolved | ratio | duration
  # kind-specific fields — see below
group_by: []                   # optional — see Dimension Types
chart: bar                     # see Chart Types
target: null                   # optional numeric target/threshold
```

## Template variables (resolved by `registry.py` — never hardcode a quarter)
- `{{current_quarter}}` — auto-detected from the fiscal calendar (or `settings.current_quarter` override, or CLI `--quarter`)
- `{{prev_quarter}}`, `{{prev_prev_quarter}}` — the two preceding quarters

## Measure kinds

### `count` — zero-fetch JQL count
```yaml
measure:
  kind: count
```
With no `group_by`: single scalar. With one `group_by` dimension: `{segment: count}`. With two: nested `{dim1: {dim2: count}}` (heatmap/stacked charts only).

### `coverage` — cumulative Done vs Remaining per week
```yaml
measure:
  kind: coverage
  weeks: 13        # optional, default 13
```
Computes total scope once, then Done-by-week (cumulative) vs Remaining, per Monday-start week. Summary text: `"{done}/{total} completed ({pct}%)"`.

### `created_vs_resolved` — intake vs output per week
```yaml
measure:
  kind: created_vs_resolved
  weeks: 13        # optional, default 13
```
Per week: count of issues created in-window vs resolved in-window (independent counts, not cumulative).

### `ratio` — percentage, two forms
```yaml
# Form A — JQL-based
measure:
  kind: ratio
  numerator_jql: "..."     # standalone JQL, not appended to filter
  denominator_jql: "..."   # standalone JQL, not appended to filter

# Form B — IDD link-based (traverses issue links)
measure:
  kind: ratio
  numerator_type: linked_idd
```
Form B counts emulations (matched by `filter`) that have at least one linked issue carrying the `idd_identifier` label (from `config/settings.yaml`, default `ATDT_IDD`). This is the one case where per-issue link traversal (`links.py`) is justified — keep new `ratio` metrics to this pattern rather than inventing new traversal code.

### `duration` — aggregate days between two dates
```yaml
measure:
  kind: duration
  span: <see measures.py for supported spans, e.g. created_to_resolved>
  aggregate: median     # median (default) | distribution
```
Without `group_by`: one aggregate value, summary `"Median: {val} days"`. With `group_by`: one aggregate per segment, summary is the min–max range across segments.

## Dimension types (`group_by` entries)
- `by_week: {window: last_91d, date_field: created}` — buckets into Monday-start weeks; `window` is `last_<N>d`, `date_field` defaults to `resolved`
- `by_quarter: [ATDT_FY27Q1, ATDT_FY26Q4, ...]` — one bucket per quarter label, resolved to its display name via `settings.quarters`
- `by_value: {Label: "extra JQL clause", ...}` — arbitrary named JQL segments (most flexible; each becomes `{filter} AND {clause}`)
- `by_label_prefix: "ATDT_No"` — one bucket per `closure_labels` entry (from `config/settings.yaml`) matching the prefix, case-insensitive
- `by_status: [Done, Closed, "In Progress"]` — one bucket per literal status value

## Chart types
`bar`, `stacked_bar`, `stacked_bar_with_trend`, `dual_area`, `bar_with_trend`, `area`, `heatmap`, `big_number`, `horizontal_bar` — pick the one matching your `measure`/`group_by` output shape. A bare scalar (`count` with no `group_by`, or `ratio`) wants `big_number`; a nested two-dimension `count` wants `heatmap` or a stacked variant; a single-dimension breakdown wants `bar` / `horizontal_bar`.
