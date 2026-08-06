# CLI Reference — Read-Only Subcommands

```bash
python -m metrics_master.cli run --dry-run [--metric <name>] [--weekly] [--quarter <label>]
python -m metrics_master.cli compute [--metric <name>] [--quarter <label>] [--format json|text]
python -m metrics_master.cli validate [--metric <name>]
```

| Flag | Subcommands | Meaning |
|---|---|---|
| `--metric <name>` | run, compute, validate | Scope to a single metric by `name` field |
| `--weekly` | run | Scope to the `weekly_metrics` list in `config/settings.yaml` (combines with `--metric` as an intersection, not a union) |
| `--quarter <label>` | run, compute | Override auto-detected quarter (e.g. `ATDT_FY27Q1`) — resolves `{{current_quarter}}` in every metric's `filter` |
| `--dry-run` | run | Render `output/page_preview.html` locally; skip Confluence entirely |
| `--format json\|text` | compute | `json` is the agent-friendly form (`name`, `summary`, `data`, `error` per metric) |

## Exit codes
- `run` / `validate`: non-zero if `errors` is non-empty / any config fails validation.
- `compute`: always 0 (errors surface per-metric in the output, not as a process failure).

## `run --dry-run` output shape
```json
{
  "status": "dry_run",
  "metrics_computed": 5,
  "errors": [],
  "preview": "output/page_preview.html"
}
```
If `metric_filter` matches nothing: `{"error": "Metric '<name>' not found"}`.
If `--weekly` matches nothing (empty `weekly_metrics` list): `{"error": "No weekly metrics configured (see weekly_metrics in config/settings.yaml)"}`.
