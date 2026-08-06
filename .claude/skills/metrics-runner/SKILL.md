---
name: metrics-runner
description: "Run the ATDT metrics CLI in read-only modes — dry-run render, compute, and validate. Use when parsing command arguments into CLI flags and interpreting stdout summaries."
user-invocable: false
---
# Metrics Runner Skill

## When to Use
- `/dry-run-metrics` and `/validate-metrics`
- Any read-only CLI invocation of the atdt-metrics pipeline

## Command Grammar
From `$ARGUMENTS`, recognize (any order, all optional):
- `--metric <name>` → passed straight through
- `--weekly` → passed straight through (filters to `weekly_metrics` in `config/settings.yaml`)
- `--quarter <label>` → passed straight through (e.g. `ATDT_FY27Q1`)

Unrecognized tokens: pass through as-is; if the CLI rejects them, surface argparse's error verbatim.

## Invocations
```bash
# Dry-run render (always add --dry-run — never omit it in this skill)
python -m metrics_master.cli run --dry-run [--metric <name>] [--weekly] [--quarter <label>]

# Validate all configs, or one
python -m metrics_master.cli validate [--metric <name>]

# Compute only, JSON output (agent-friendly, no chart render)
python -m metrics_master.cli compute --format json [--metric <name>] [--quarter <label>]
```

## Reading Output
- `run --dry-run` prints one JSON object: `status`, `metrics_computed`, `errors[]`, `preview` (path to `output/page_preview.html`).
- `validate` prints `All metrics valid.` on success, or one `ERROR: <metric>: <message>` line per problem on stderr with a non-zero exit code.
- Never open the referenced files (`page_preview.html`, chart PNGs, metric YAMLs) to "double check" — the CLI's stdout is authoritative and cheaper.

See `references/cli-reference.md` for the full command/flag table.
