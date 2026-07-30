# atdt-metrics

Automated Jira metrics pipeline for the Advanced Threat Defense Team (ATDT). Computes delivery metrics from Jira data and publishes chart images to a Confluence child page.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Fill in .env with your Jira/Confluence credentials
```

## Usage

```bash
# Full pipeline — compute all metrics and publish to Confluence
python -m metrics_master.cli run

# Dry run — render charts locally without publishing
python -m metrics_master.cli run --dry-run

# Single metric
python -m metrics_master.cli run --metric team_velocity

# Compute only (no render/publish) — agent-friendly JSON output
python -m metrics_master.cli compute --format json

# Override quarter (default: auto-detected from fiscal calendar)
python -m metrics_master.cli run --quarter ATDT_FY26Q4

# Validate all metric configs
python -m metrics_master.cli validate

# Create a new metric from template
python -m metrics_master.cli add-metric my_new_metric
```

## Architecture

```
config/settings.yaml            → Fiscal calendar, labels, section layout
config/metrics/*.yaml           → One YAML per metric (supports {{template}} vars)
         ↓
registry.py                     → Loads configs, resolves {{current_quarter}} etc.
calendar.py                     → Auto-detects quarter from fiscal year start
         ↓
engine.py (MetricEngine)        → Stateless compute layer (agent-callable)
         ↓
    ┌────┴──────────────────────────┐
    │                               │
dimensions.py / measures.py     links.py (optimized)
jira_client.py (cached)         (2-search IDD traversal)
    │                               │
    └────┬──────────────────────────┘
         ↓
publish.py                      → Thin orchestrator (delegates to engine)
         ↓
render/charts.py                → PNG chart images
render/page_builder.py          → Confluence storage-format HTML
         ↓
confluence_client.py            → Creates/updates child page + uploads attachments
```

### Design principles

- **Count-first** — prefers Jira's approximate-count endpoint (zero issue data fetched) over search. Only uses `search` when per-issue fields are needed (link traversal).
- **Config-driven** — each metric is a standalone YAML with filter, measure kind, dimensions, and chart type. No code changes needed to add a metric.
- **Sub-task exclusion** — all emulation metrics filter with `issuetype != Sub-task` to count Stories (actual emulations), not their child tasks.
- **Idempotent publishing** — re-running updates the existing "Computed Metrics (Automated)" page in place. Never creates duplicates.
- **Child page isolation** — only touches its own page. Never reads or writes the parent or sibling pages.
- **No MCP dependency** — plain Python + REST API tokens, runnable headless via cron/CI.

## Metrics (13 total)

### Emulation Coverage

| Metric | Kind | Chart | Description |
|--------|------|-------|-------------|
| `cve_weekly_coverage` | coverage | stacked bar | Cumulative CVE emulations: Done vs Remaining over the quarter |
| `lc_weekly_coverage` | coverage | stacked bar | Same for LightCycles |

### Intake vs Output

| Metric | Kind | Chart | Description |
|--------|------|-------|-------------|
| `cve_created_vs_resolved` | created_vs_resolved | dual area | Weekly: new CVE tickets created (red) vs resolved (green) — gap = backlog |
| `lc_created_vs_resolved` | created_vs_resolved | dual area | Same for LightCycles |

### Team Output

| Metric | Kind | Chart | Description |
|--------|------|-------|-------------|
| `weekly_idds` | count (by_week, created) | bar | ATDT-created Detection Requests per week (label: `ATDT_IDD`) |
| `team_velocity` | count (2D: week × type) | stacked bar + trend | CVE vs LightCycles per week with rolling average |
| `idd_conversion_rate` | ratio (linked_idd) | big number | % of Done emulations that produced at least one IDD |

### Quarterly Summary

| Metric | Kind | Chart | Description |
|--------|------|-------|-------------|
| `q1_completion_status` | count (by_value) | bar | Done / Closed / In Progress breakdown for current quarter |
| `quarter_over_quarter` | count (by_quarter) | bar | Done stories per quarter — delivery trend |
| `closure_rate` | ratio (JQL) | big number | % of quarter emulations Closed without completion |

### Closure Analysis

| Metric | Kind | Chart | Description |
|--------|------|-------|-------------|
| `closure_reasons` | count (by_value) | horizontal bar | Breakdown by reason: No Infra, No Env, No PoC, Not Reproduced, Network Appliance |

### Work Health

| Metric | Kind | Chart | Description |
|--------|------|-------|-------------|
| `work_aging` | count | big number | Open emulations with no update in 14+ days (target: 0) |

### Request Management

| Metric | Kind | Chart | Description |
|--------|------|-------|-------------|
| `external_requests` | count (by_value) | bar | ATDTRequest tickets: Done / Closed / Open |

## How Computation Works

The pipeline has three decoupled phases:

1. **Compute** (`MetricEngine` in `engine.py`) — loads configs, resolves `{{current_quarter}}` templates, dispatches by `measure.kind`, returns `MetricResult` dataclass objects. No side effects. Agent-callable via `python -m metrics_master.cli compute --format json`.

2. **Render** (`render/charts.py`) — takes computed data and generates PNG chart images.

3. **Publish** (`publish.py`) — thin orchestrator that calls engine.compute_all(), renders each result, builds Confluence HTML, and uploads.

### Measure kinds

| Kind | Description | API calls |
|------|-------------|-----------|
| `count` | Issue count via JQL | 1 per segment (zero-fetch) |
| `coverage` | Cumulative Done vs Remaining per week | 1 + N weeks |
| `created_vs_resolved` | Created vs resolved per week | 2N (N weeks) |
| `ratio` | % (JQL or IDD link-based) | 2-3 calls |
| `duration` | Days between dates | 1 search + changelogs |

### Fiscal Calendar Auto-Resolution (`calendar.py`)

Quarter is auto-detected from the fiscal year start month (default: May). FY27 = May 2026 – Apr 2027, Q1 = May–Jul. Template variables in metric configs:
- `{{current_quarter}}` → `ATDT_FY27Q1`
- `{{prev_quarter}}` → `ATDT_FY26Q4`
- `{{prev_prev_quarter}}` → `ATDT_FY26Q3`

Override with `--quarter ATDT_FY26Q4` for historical runs.

### Jira Client (`jira_client.py`)

- `count(jql)` — uses `/rest/api/3/search/approximate-count` (cloud) for zero-fetch counting.
- `search(jql, fields, max_results)` — paginated search with minimal fields. Only used for link traversal.
- In-memory cache prevents duplicate API calls within a single pipeline run.

### Link Traversal (`links.py`) — Optimized

Two-search approach (3 API calls total):
1. Fetch IDR keys with `ATDT_IDD` label (key field only — tiny payload)
2. Fetch emulation issuelinks (bounded by quarter scope, ~50-150 issues)
3. Intersect to find emulations with IDD links

## Project Structure

```
config/
  settings.yaml                 # Fiscal calendar, labels, section layout
  metrics/                      # One YAML per metric (supports {{templates}})
    cve_weekly_coverage.yaml
    team_velocity.yaml
    work_aging.yaml
    ...
src/metrics_master/
  engine.py                     # MetricEngine — stateless compute layer
  cli.py                        # CLI (run/compute/validate/add-metric)
  publish.py                    # Thin orchestrator (engine → render → publish)
  calendar.py                   # Fiscal year quarter auto-resolution
  registry.py                   # YAML loader + template substitution
  jira_client.py                # Jira REST client (cached, count-first)
  confluence_client.py          # Confluence REST client
  dimensions.py                 # Dimension resolvers (by_week, by_quarter, by_value)
  measures.py                   # Duration computations
  links.py                      # Optimized IDD link traversal
  windows.py                    # Date utilities
  render/
    charts.py                   # Chart renderers
    page_builder.py             # Confluence HTML assembly
tests/
output/                         # Generated charts + page preview (git-ignored)
```

## Adding a Metric

1. Create config: `python -m metrics_master.cli add-metric my_metric`
2. Edit `config/metrics/my_metric.yaml` — set filter (JQL), measure kind, group_by, chart type
3. Add the metric name to a section in `config/settings.yaml`
4. Validate: `python -m metrics_master.cli validate`
5. Test: `python -m metrics_master.cli run --dry-run --metric my_metric`
6. Publish: `python -m metrics_master.cli run --metric my_metric`

### Supported measure kinds

| Kind | Description | Required fields |
|------|-------------|-----------------|
| `count` | Issue count via JQL | `filter`, optionally `group_by` |
| `coverage` | Cumulative Done vs Remaining per week | `filter`, `weeks` |
| `created_vs_resolved` | Created vs resolved per week | `filter`, `weeks` |
| `ratio` | Percentage (JQL or IDD link-based) | `numerator_jql` + `denominator_jql`, or `numerator_type: linked_idd` |
| `duration` | Days between dates | `filter`, `span`, `aggregate` |

### Supported chart types

`bar`, `stacked_bar`, `stacked_bar_with_trend`, `dual_area`, `bar_with_trend`, `big_number`, `horizontal_bar`, `area`, `heatmap`

## Agent Integration

The `MetricEngine` is designed to be called independently from publish:

```python
from metrics_master.engine import MetricEngine
from metrics_master.registry import load_settings, load_metric

settings = load_settings()
engine = MetricEngine(settings)

# Compute a single metric — returns MetricResult dataclass
result = engine.compute(load_metric("team_velocity"))
print(result.summary)  # "Total: 17"
print(result.data)     # {"May 4": {"CVE": 1, "LightCycles": 1}, ...}
```

Or via CLI for agent subprocess calls:
```bash
python -m metrics_master.cli compute --metric team_velocity --format json
```
