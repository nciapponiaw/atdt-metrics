# Confluence Publishing Contract

## What gets written
Exactly one page: **title = "Computed Metrics MA"** (see `PAGE_TITLE` in `src/metrics_master/publish.py`), created as a child of `confluence.parent_page_id` (env var `CONFLUENCE_PARENT_PAGE_ID`, referenced from `config/settings.yaml`).

> Note: `CLAUDE.md` describes this page as "Computed Metrics (Automated)" — that's stale prose; the title the code actually publishes is `"Computed Metrics MA"`. If you rename the page, update `PAGE_TITLE` in `publish.py` AND every doc that names it, together (see `MAINTENANCE.md` → Contract Registry).

## Idempotency mechanism
`.state.json` (repo root, gitignored) stores `{"child_page_id": "<id>"}` after the first successful create. Every subsequent `publish_page()` call:
1. Reads `child_page_id` from `.state.json`.
2. Fetches that page by ID (`GET /api/v2/pages/{id}`).
3. If it still exists, `PUT`s an update (version bump) — same page, new content.
4. Only if the stored ID is missing or the page was deleted does it fall back to creating a new child page and re-saving `.state.json`.

**Never delete or hand-edit `.state.json`** — doing so orphans the old Confluence page (a duplicate gets created on the next publish) and breaks idempotency until manually reconciled.

## Attachments
Chart PNGs are uploaded via the Confluence v1 REST API (`/rest/api/content/{page_id}/child/attachment`) as attachments on the child page itself — never inline-embedded elsewhere and never uploaded to the parent.

## Blast radius
The pipeline only ever calls `_get_page`, `_create_page`, `_update_page`, `upload_attachment` — all scoped to the child page ID read from `.state.json` or freshly created. There is no code path that reads or writes the parent page or any sibling. Keep it that way: any future Confluence feature must stay scoped to this same child page.
