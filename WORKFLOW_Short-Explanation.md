# Workflow at a Glance

> A one-page tour of the pipeline: the `.claude/` commands and agents, sitting on top of a
> plain-Python compute/render/publish pipeline.

**What it does:** turns Jira data into ATDT delivery metrics — coverage, velocity, IDDs,
closure analysis — and publishes them as chart images on one dedicated Confluence child page.
Metrics are defined as config (YAML), not code: adding one is a config change, not a Python
change.

You start it with one of four commands: `/run-metrics`, `/dry-run-metrics`,
`/validate-metrics`, `/add-metric`.

---

## The flow (config → Confluence)

```
config/settings.yaml ──┐         Fiscal calendar, sections, weekly_metrics, closure labels
config/metrics/*.yaml ─┴──►  registry.py
                              │  resolves {{current_quarter}} etc., validates schema
                              ▼
                        engine.py (MetricEngine)
                              │  dispatches by measure.kind → count / coverage /
                              │  created_vs_resolved / ratio / duration
                              │  (jira_client.py: cached, count-first JQL calls)
                              ▼
                        render/charts.py
                              │  one PNG per metric → output/<name>.png
                              ▼
                        render/page_builder.py
                              │  assembles the Confluence storage-format HTML
                              ▼
              ┌─── dry-run? ──┴── publish? ───┐
              ▼                               ▼
   output/page_preview.html         confluence_client.py
   (local only, nothing sent)       creates/updates ONE child page
                                     ("Computed Metrics MA"), uploads
                                     chart PNGs as attachments,
                                     tracks the page id in .state.json
                                     for idempotent re-runs
```

Everything above the dashed line is orchestrated by `publish.py::run()` — one function, no
hidden state beyond `.state.json`.

---

## Who does what (command → agent → CLI)

| You type | Agent | Skill (the *how*) | Runs | Can write to Confluence? |
|---|---|---|---|---|
| `/dry-run-metrics [--metric] [--weekly] [--quarter]` | `metrics-runner` | `metrics-runner` | `cli run --dry-run ...` | No |
| `/validate-metrics [name]` | `metrics-runner` | `metrics-runner` | `cli validate ...` | No |
| `/add-metric <name>` | `metric-author` | `metric-author` | `cli add-metric` → edit YAML → `cli validate` → `cli run --dry-run` | No |
| `/run-metrics [--metric] [--weekly] [--quarter]` | `metrics-publisher` | `metrics-publisher` | `cli run ...` (no `--dry-run`) | **Yes — the only one** |

Every agent reads **only CLI stdout** (a small JSON summary) — never raw Jira issues, never
metric YAML data, never chart files. That's the token-efficiency rule from `CLAUDE.md`,
enforced at the agent level.

---

## Key semantics

- **Done** = emulation completed successfully. **Closed** = could not complete (no infra, no
  PoC, not reproduced, network appliance — see `closure_labels` in `config/settings.yaml`).
- **Velocity** counts Done only. **Coverage**-shaped metrics show Done vs Remaining.
  **Closure analysis** breaks down Closed by reason.
- **Quarter** auto-detects from the fiscal calendar (FY starts May, Q1 = May–Jul) via
  `calendar.py`, or is overridden with `--quarter ATDT_FYxxQx`. Every metric's `filter` uses
  `{{current_quarter}}` (never a hardcoded label) so it keeps working across quarter rollovers.
- **Weekly-cadence subset** (`--weekly`) is a hand-maintained list (`weekly_metrics:` in
  `config/settings.yaml`) — not auto-detected from `measure.kind`.
- **Idempotent publish**: re-running `/run-metrics` updates the same Confluence child page
  (tracked via `.state.json`) — it never creates a duplicate, and it never touches the parent
  page or any sibling.
- **No fabrication**: a failed or empty query renders "No Data" — never a stale or invented
  number.

For the full cross-file contracts behind these guarantees, see `MAINTENANCE.md`.
