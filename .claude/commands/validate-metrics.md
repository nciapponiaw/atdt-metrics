---
description: "Validate all metric YAML configs (or one, by name) against the schema. Reports the exact file and field to fix."
argument-hint: "[metric-name]"
agent: metrics-runner
model: sonnet
effort: low
disable-model-invocation: true
---
Validate metric configs.

## Input
$ARGUMENTS — optional metric name to validate a single config; otherwise validates every file in `config/metrics/*.yaml`.

## Pipeline
1. Run `python -m metrics_master.cli validate` (add `--metric <name>` if a name was given in `$ARGUMENTS`).
2. Read stdout/stderr only.
3. If it prints `All metrics valid.` — report success.
4. If errors are printed, list each one with the offending metric name and field, mapped to its file path (`config/metrics/<name>.yaml`).

## Output
Pass/fail, plus on failure, one line per error naming the file to fix.
