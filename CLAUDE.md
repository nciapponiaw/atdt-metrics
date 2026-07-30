# CLAUDE.md — metrics-master operating rules

## What this project does
Automated Jira metrics pipeline for the ATDT team. Computes delivery metrics (coverage,
velocity, IDDs, closure analysis) from Jira data and publishes chart images to a dedicated
Confluence child page.

## Running
```bash
cd /Users/natalia.ciapponi/repos/atdt-metrics
python -m metrics_master.cli run                    # full publish
python -m metrics_master.cli run --dry-run          # render locally only
python -m metrics_master.cli run --metric team_velocity  # single metric
python -m metrics_master.cli compute                # compute only (no render/publish)
python -m metrics_master.cli compute --format json  # JSON output for agents
python -m metrics_master.cli validate               # check all configs
```

## Non-negotiable rules
- **Token efficiency**: Never load raw Jira issues into context. All querying/aggregation in Python. Only tiny numeric summaries and file paths reach the agent.
- **Count-first**: Default every metric to `count()`. Only use `search()` when per-issue fields are genuinely needed (link traversal), and restrict fields to the minimum.
- **Sub-task exclusion**: All emulation metrics MUST include `AND issuetype != Sub-task`. Stories are emulations; Sub-tasks are steps within them.
- **No fabrication**: If a query fails or returns nothing, render "No Data". Never invent or carry forward stale numbers.
- **Idempotent publishing**: Re-running updates the existing child page in place. Never creates duplicates.
- **Child page only**: The pipeline creates and owns "Computed Metrics (Automated)" under the parent. It must NEVER read or write the parent page or sibling pages.
- **No MCP runtime dependency**: Plain Python + API tokens, runnable headless via cron/CI.
- **Template variables**: Use `{{current_quarter}}` in metric configs — never hardcode quarter labels.

## Architecture
- `MetricEngine` (engine.py) — stateless compute layer, callable independently from publish
- `publish.py` — thin orchestrator that delegates to engine, renders charts, publishes
- `calendar.py` — fiscal year auto-resolution (FY starts May, Q1 = May-Jul)
- `registry.py` — loads YAML configs with `{{template}}` substitution

## Adding a metric
1. `python -m metrics_master.cli add-metric my_metric`
2. Edit `config/metrics/my_metric.yaml` — fill filter, measure, group_by, chart
3. Add metric name to a section in `config/settings.yaml`
4. Validate: `python -m metrics_master.cli validate`
5. Test: `python -m metrics_master.cli run --dry-run --metric my_metric`
6. Publish: `python -m metrics_master.cli run --metric my_metric`

## Key workflow semantics
- **Done** = emulation completed successfully
- **Closed** = could not complete (no infra, no PoC, not reproduced, etc.)
- Velocity counts Done only
- Coverage shows Done vs Remaining (cumulative over quarter)
- Quarter is auto-detected from fiscal calendar (override with `--quarter` flag)

## Supported measure kinds
- `count` — JQL count (zero-fetch)
- `coverage` — cumulative Done vs Remaining per week
- `created_vs_resolved` — intake vs output per week
- `ratio` — percentage (JQL-based or IDD link-based)
- `duration` — days between dates (created→resolved, time-in-status)

## Project structure
- `config/settings.yaml` — fiscal calendar, labels, section layout
- `config/metrics/*.yaml` — one file per metric (template variables supported)
- `src/metrics_master/engine.py` — MetricEngine (compute layer)
- `src/metrics_master/publish.py` — orchestrator (render + publish)
- `src/metrics_master/calendar.py` — fiscal year quarter resolution
- `src/metrics_master/jira_client.py` — Jira REST client (cached, count-first)
- `src/metrics_master/confluence_client.py` — Confluence REST client
- `src/metrics_master/dimensions.py` — dimension resolvers (by_week, by_quarter, by_value)
- `src/metrics_master/links.py` — optimized IDD link traversal
- `src/metrics_master/render/` — chart renderers + page builder
- `tests/` — unit tests
