---
description: "Run the full ATDT metrics pipeline and publish charts to the Confluence child page, or publish the Quarterly Metrics Summary report for a given quarter."
argument-hint: "[--weekly] [--metric <name>] | --quarter <ATDT_FYxxQx>"
agent: metrics-publisher
model: sonnet
effort: low
disable-model-invocation: true
---
Publish ATDT delivery metrics — two distinct targets depending on the flags given.

## Input
$ARGUMENTS

Recognized flags (pass through to `python -m metrics_master.cli run`):
- (no flags) — publish every metric for the current quarter to the "Computed Metrics MA" Confluence child page
- `--weekly` — same target, scoped to the weekly-cadence metrics listed under `weekly_metrics` in `config/settings.yaml`
- `--metric <name>` — same target, a single metric by name
- `--quarter <label>` — **different target.** Publishes/updates the "`<label> - Quarterly Metrics Summary`" report page for that quarter (e.g. `ATDT_FY27Q1`), under `confluence.quarterly_report_parent_page_id`. Does NOT touch "Computed Metrics MA". Cannot be combined with `--weekly` or `--metric` — the CLI rejects that combination.

## Scope
**Publish only.** Do not edit metric YAMLs, `config/settings.yaml`, or any pipeline source file. If a metric errors, report "No Data" exactly as the pipeline returns it — never fabricate or carry forward a number.

## Pipeline
1. Build the command: `python -m metrics_master.cli run` plus any recognized flags parsed from `$ARGUMENTS`.
2. Run it and read only stdout (the JSON summary) — never open raw Jira data or inspect issue-level detail.
3. Report the result back to the user in plain language:
   - No `--quarter`: `status`, `metrics_computed`, `errors`.
   - With `--quarter`: `status`, `title`, `total_light_cycles`, `total_idds`, `total_cves`, `total_cve_idds`, `total_research_projects`, `page_id`, `errors` (present when `status` is `"published"`; a top-level `error` string instead if the parent page id isn't configured).
4. If `status` is not `"published"`, or `errors`/`error` is non-empty, surface the exact error text — do not paper over it.

## Output
One short status line per run (what was computed, any errors, confirmation of publish). Never print JQL, issue keys, or raw Jira payloads.
