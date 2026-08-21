---
name: metrics-publisher
description: "Publish the ATDT metrics pipeline output to its Confluence child page(s) and verify the result. Use for /run-metrics — the only workspace skill that performs a Confluence write."
user-invocable: false
---
# Metrics Publisher Skill

## When to Use
- `/run-metrics` (the full, non-dry-run publish)

## Procedure
```bash
python -m metrics_master.cli run [--weekly] [--metric <name>]
python -m metrics_master.cli run --quarter <label>   # different target — see Confluence contract
```
No `--dry-run` here — this is the one skill in the workspace allowed to omit it. `--quarter` cannot be combined with `--weekly` or `--metric` (the CLI rejects that and exits 1).

Read only stdout — a single JSON object. Shape depends on which target was hit:
- No `--quarter`: `status` (should be `"published"`), `page_id`, `metrics_computed`, `errors[]`.
- With `--quarter`: `status`, `page_id`, `title`, `total_light_cycles`, `total_idds`, `total_cves`, `total_cve_idds`, `total_research_projects`, `errors[]` — or a top-level `error` string if `confluence.quarterly_report_parent_page_id` isn't configured.

## Confluence contract
The pipeline owns exactly **two** kinds of pages — never anything outside them, not even to "check" something:

1. **"Computed Metrics MA"** — one page, under `confluence.parent_page_id`. Published by `run` / `run --weekly` / `run --metric <name>`. Idempotency: `.state.json`'s top-level `child_page_id`.
2. **"`<label> - Quarterly Metrics Summary`"** — one page *per quarter label*, under `confluence.quarterly_report_parent_page_id`. Published by `run --quarter <label>`. Idempotency: `.state.json`'s `pages` dict, key `quarterly_summary:<label>` — re-running the same quarter updates that page; a different quarter creates its own sibling page, never overwriting another quarter's report.

Both are version-bump updates when the tracked page still exists; never a duplicate create. Chart PNGs are only ever attached to the "Computed Metrics MA" page (the quarterly report has no charts, it's tabular). Full detail: `references/confluence-contract.md`.

## Verification before declaring success
1. `status == "published"`
2. `errors` is empty (or, if non-empty, each one is surfaced verbatim to the user — never suppressed); no top-level `error` string
3. `page_id` is present

If credentials are missing (`CONFLUENCE_URL` / `CONFLUENCE_EMAIL` / `CONFLUENCE_TOKEN` / `CONFLUENCE_PARENT_PAGE_ID` env vars), the CLI raises — report the actual error, don't guess at the cause.

## Constraints
- Never publish except when explicitly invoked via `/run-metrics`.
- Never read or attempt to write the parent page of either owned page, or any sibling page other than the pages this pipeline itself created. That's the entire blast radius, for both contracts above.
- Never fabricate a `page_id` or URL if the run failed.
- Never load raw Jira issues into context — only the CLI's own numeric summary and file paths reach you.
