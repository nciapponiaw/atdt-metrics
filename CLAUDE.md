# CLAUDE.md — metrics-master operating rules

## What this project does
Automated Jira metrics pipeline for the ATDT team. Computes delivery metrics (coverage,
velocity, IDDs, closure analysis) from Jira data and publishes chart images to a dedicated
Confluence child page. It also publishes a separate per-quarter Quarterly Metrics Summary
report page (Jira + Confluence lookups, tabular) under a different parent page.

## Running
All commands run from the repo root (wherever it's checked out — never hardcode an absolute path).

Via slash commands (preferred — see [Agent Workspace](#agent-workspace) below):
```
/run-metrics [--weekly] [--metric <name>]       # full publish to "Computed Metrics MA"
/run-metrics --quarter <label>                  # publish/update the Quarterly Metrics Summary report for that quarter
/dry-run-metrics [--metric <name>] [--weekly] [--quarter <label>]  # render locally only
/validate-metrics [metric-name]                                 # check configs
/add-metric <name>                                               # scaffold + register + validate a new metric
```

Via raw CLI (what the commands/agents call under the hood):
```bash
python -m metrics_master.cli run                    # full publish
python -m metrics_master.cli run --dry-run          # render locally only
python -m metrics_master.cli run --metric team_velocity  # single metric
python -m metrics_master.cli run --weekly            # weekly-cadence metrics only (see weekly_metrics in config/settings.yaml)
python -m metrics_master.cli run --quarter ATDT_FY27Q1        # Quarterly Metrics Summary report — NOT the regular metrics page (see below)
python -m metrics_master.cli compute                # compute only (no render/publish)
python -m metrics_master.cli compute --format json  # JSON output for agents
python -m metrics_master.cli validate               # check all configs
```

`run --quarter <label>` and plain `run` are two different publish targets — see [Non-negotiable rules](#non-negotiable-rules) → Child page only. `--quarter` cannot be combined with `--metric` or `--weekly`.

## Non-negotiable rules
- **Token efficiency**: Never load raw Jira issues into context. All querying/aggregation in Python. Only tiny numeric summaries and file paths reach the agent.
- **Count-first**: Default every metric to `count()`. Only use `search()` when per-issue fields are genuinely needed (link traversal), and restrict fields to the minimum.
- **Sub-task exclusion**: All emulation metrics MUST include `AND issuetype != Sub-task`. Stories are emulations; Sub-tasks are steps within them.
- **No fabrication**: If a query fails or returns nothing, render "No Data". Never invent or carry forward stale numbers.
- **Idempotent publishing**: Re-running updates the existing page in place (per-page, see below). Never creates duplicates.
- **Child page only — two owned targets**: The pipeline owns exactly two kinds of Confluence pages and must NEVER read or write anything outside them (no parent pages, no siblings other than pages it created itself):
  1. **"Computed Metrics MA"** (`PAGE_TITLE` in `publish.py`) — one page, under `CONFLUENCE_PARENT_PAGE_ID`. Published by plain `run` / `run --weekly` / `run --metric <name>`.
  2. **"`<label> - Quarterly Metrics Summary`"** — one page *per quarter label*, under `confluence.quarterly_report_parent_page_id` (`config/settings.yaml`). Published by `run --quarter <label>`. Idempotency tracked per-quarter in `.state.json`'s `pages` dict (key `quarterly_summary:<label>`) — re-running the same quarter updates that page; a different quarter creates its own sibling page, it never overwrites another quarter's report.
- **No MCP runtime dependency**: Plain Python + API tokens, runnable headless via cron/CI.
- **Template variables**: Use `{{current_quarter}}` in metric configs — never hardcode quarter labels.

## Architecture
- `MetricEngine` (engine.py) — stateless compute layer, callable independently from publish
- `publish.py` — thin orchestrator that delegates to engine, renders charts, publishes
- `calendar.py` — fiscal year auto-resolution (FY starts May, Q1 = May-Jul)
- `registry.py` — loads YAML configs with `{{template}}` substitution

## Agent workspace
Slash commands are the entry points; each delegates to one purpose-built agent, which preloads one skill (+ `references/`) for the *how*. Full contracts live in [MAINTENANCE.md](MAINTENANCE.md); this is the roster.

| Command | Agent | Skill | Can publish? |
|---|---|---|---|
| `/dry-run-metrics` | `metrics-runner` | `metrics-runner` | No — `--dry-run` only |
| `/validate-metrics` | `metrics-runner` | `metrics-runner` | No |
| `/add-metric` | `metric-author` | `metric-author` | No — validates + dry-runs, never publishes |
| `/run-metrics` | `metrics-publisher` | `metrics-publisher` | **Yes** — the only agent permitted to write to Confluence |

All three agents read only CLI stdout — never raw Jira issues, never metric YAML data, never chart files — per the token-efficiency rule above.

## Adding a metric
Preferred: `/add-metric my_metric` (the `metric-author` agent does steps 1-5 below, then hands back for review before you publish).

Manual equivalent:
1. `python -m metrics_master.cli add-metric my_metric`
2. Edit `config/metrics/my_metric.yaml` — fill filter, measure, group_by, chart
3. Add metric name to a section in `config/settings.yaml` (and to `weekly_metrics:` if weekly-cadence)
4. Validate: `python -m metrics_master.cli validate`
5. Test: `python -m metrics_master.cli run --dry-run --metric my_metric`
6. Publish: `/run-metrics --metric my_metric` (or `python -m metrics_master.cli run --metric my_metric`)

## Key workflow semantics
- **Done** = emulation completed successfully
- **Closed** = could not complete (no infra, no PoC, not reproduced, etc.)
- Velocity counts Done only
- Coverage shows Done vs Remaining (cumulative over quarter)
- Quarter for the regular metrics page is auto-detected from the fiscal calendar (override for `compute`/dry-run purposes with `--quarter`, but note `run --quarter <label>` targets the *separate* Quarterly Metrics Summary report, not "Computed Metrics MA" — see Non-negotiable rules)

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
- `src/metrics_master/quarterly_report.py` — Quarterly Metrics Summary report compute layer
- `src/metrics_master/render/` — chart renderers + page builder + quarterly report builder
- `tests/` — unit tests
- `.claude/commands/` — slash command entry points
- `.claude/agents/` — enforcement (what each agent must/must not do, its output contract)
- `.claude/skills/` — knowledge (`user-invocable: false`, preloaded via each agent's `skills:` frontmatter, with `references/` for stable detail)
