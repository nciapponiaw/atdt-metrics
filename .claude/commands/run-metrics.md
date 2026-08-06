---
description: "Run the full ATDT metrics pipeline and publish charts to the Confluence child page. Optionally scope to weekly-cadence metrics, a single metric, or a specific quarter."
argument-hint: "[--weekly] [--metric <name>] [--quarter <ATDT_FYxxQx>]"
agent: metrics-publisher
model: sonnet
effort: low
disable-model-invocation: true
---
Publish ATDT delivery metrics to the "Computed Metrics MA" Confluence child page.

## Input
$ARGUMENTS

Recognized flags (pass through to `python -m metrics_master.cli run`):
- `--weekly` — run only the weekly-cadence metrics listed under `weekly_metrics` in `config/settings.yaml`
- `--metric <name>` — run a single metric by name
- `--quarter <label>` — override the auto-detected fiscal quarter (e.g. `ATDT_FY27Q1`)

With no arguments, runs and publishes every metric for the current quarter.

## Scope
**Publish only.** Do not edit metric YAMLs, `config/settings.yaml`, or any pipeline source file. If a metric errors, report "No Data" exactly as the pipeline returns it — never fabricate or carry forward a number.

## Pipeline
1. Build the command: `python -m metrics_master.cli run` plus any recognized flags parsed from `$ARGUMENTS`.
2. Run it and read only stdout (the JSON summary) — never open raw Jira data or inspect issue-level detail.
3. Report the JSON summary's `status`, `metrics_computed`, and `errors` back to the user in plain language.
4. If `status` is not `"published"`, or `errors` is non-empty, surface the exact error text — do not paper over it.

## Output
One short status line per run (metrics computed, any errors, confirmation of publish). Never print JQL, issue keys, or raw Jira payloads.
