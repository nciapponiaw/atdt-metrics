---
description: "Render ATDT metrics charts locally without publishing to Confluence. Use to preview a change before /run-metrics."
argument-hint: "[--metric <name>] [--weekly] [--quarter <ATDT_FYxxQx>]"
agent: metrics-runner
model: sonnet
effort: low
disable-model-invocation: true
---
Render the metrics page locally to `output/page_preview.html` — no Confluence or Jira writes.

## Input
$ARGUMENTS

Same optional flags as `/run-metrics` (`--metric`, `--weekly`, `--quarter`), always run with `--dry-run` appended.

## Scope
**Read-only / local render only.** Never omit `--dry-run`. Never call any Confluence or Jira write endpoint.

## Pipeline
1. Run `python -m metrics_master.cli run --dry-run` plus any recognized flags parsed from `$ARGUMENTS`.
2. Read only stdout (the JSON summary).
3. Confirm `output/page_preview.html` was written (the `preview` field in the JSON summary) and tell the user the path so they can open it.

## Output
Metrics computed, any errors, and the preview file path. Nothing else.
