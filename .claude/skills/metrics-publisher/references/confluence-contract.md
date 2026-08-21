# Confluence Publishing Contract

The pipeline owns two independent Confluence write paths. Keep them separate in your head — different parent page, different title pattern, different state-file key, different trigger.

## Contract A — "Computed Metrics MA" (the regular metrics page)

### What gets written
Exactly one page: **title = "Computed Metrics MA"** (see `PAGE_TITLE` in `src/metrics_master/publish.py`), created as a child of `confluence.parent_page_id` (env var `CONFLUENCE_PARENT_PAGE_ID`, referenced from `config/settings.yaml`).

> Note: `CLAUDE.md` describes this page as "Computed Metrics (Automated)" — that's stale prose; the title the code actually publishes is `"Computed Metrics MA"`. If you rename the page, update `PAGE_TITLE` in `publish.py` AND every doc that names it, together (see `MAINTENANCE.md` → Contract Registry).

### Idempotency mechanism
`.state.json` (repo root, gitignored) stores `{"child_page_id": "<id>", ...}` after the first successful create. Every subsequent `publish_page()` call:
1. Reads `child_page_id` from `.state.json`.
2. Fetches that page by ID (`GET /api/v2/pages/{id}`).
3. If it still exists, `PUT`s an update (version bump) — same page, new content.
4. Only if the stored ID is missing or the page was deleted does it fall back to creating a new child page and re-saving `.state.json`.

### Attachments
Chart PNGs are uploaded via the Confluence v1 REST API (`/rest/api/content/{page_id}/child/attachment`) as attachments on the child page itself — never inline-embedded elsewhere and never uploaded to the parent.

### Trigger
Plain `run`, `run --weekly`, `run --metric <name>` — anything that does NOT pass `--quarter`.

## Contract B — Quarterly Metrics Summary (per-quarter report)

### What gets written
One page per quarter label: **title = "`<label> - Quarterly Metrics Summary`"** (e.g. `ATDT_FY27Q1 - Quarterly Metrics Summary`), created as a child of `confluence.quarterly_report_parent_page_id` (`config/settings.yaml`, a plain literal page ID — not an env var, since it's a fixed report destination rather than a per-environment secret). Content is a computed table (Jira + Confluence lookups), not charts — see `src/metrics_master/quarterly_report.py` and `src/metrics_master/render/quarterly_report_builder.py`.

### Idempotency mechanism
`.state.json`'s `pages` dict, keyed `quarterly_summary:<label>` → page ID. `confluence_client.publish_named_page()`:
1. Reads `pages["quarterly_summary:<label>"]` from `.state.json`.
2. Fetches that page by ID; if it still exists, `PUT`s an update (version bump).
3. Otherwise creates a new child page under `quarterly_report_parent_page_id` and records its ID under that same key.

A different `<label>` is a different key → a new sibling page, never an overwrite of another quarter's report.

### Trigger
`run --quarter <label>` only. Rejected (CLI exits 1) if combined with `--weekly` or `--metric`.

## Shared mechanics
- **Never delete or hand-edit `.state.json`** — doing so orphans the corresponding Confluence page (a duplicate gets created on the next publish) and breaks idempotency until manually reconciled. This applies to both `child_page_id` and every key under `pages`.
- **Full-width**: both contracts call `_set_full_width()` (a Confluence content-property write) on every create *and* every update — pages under both contracts are always full-width, unconditionally.

## Blast radius
The pipeline only ever calls `_get_page`, `_create_page`, `_update_page`, `_set_full_width`, `upload_attachment`, `find_page_for_issue` (CQL search, read-only) — all scoped to page IDs read from `.state.json` or freshly created under one of the two configured parents above. There is no code path that reads or writes either parent page, or any sibling page the pipeline didn't create itself. Keep it that way: any future Confluence feature must declare which of these two contracts it extends, or define a third one explicitly (new parent config key + new `.state.json` namespace) — never silently reuse another contract's page.
