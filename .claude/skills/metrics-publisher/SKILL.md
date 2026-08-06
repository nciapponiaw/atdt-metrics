---
name: metrics-publisher
description: "Publish the ATDT metrics pipeline output to its Confluence child page and verify the result. Use for /run-metrics — the only workspace skill that performs a Confluence write."
user-invocable: false
---
# Metrics Publisher Skill

## When to Use
- `/run-metrics` (the full, non-dry-run publish)

## Procedure
```bash
python -m metrics_master.cli run [--weekly] [--metric <name>] [--quarter <label>]
```
No `--dry-run` here — this is the one skill in the workspace allowed to omit it.

Read only stdout — a single JSON object: `status` (should be `"published"`), `page_id`, `metrics_computed`, `errors[]`.

## Confluence contract
The pipeline owns exactly one page: the child page titled **"Computed Metrics MA"** under `confluence.parent_page_id`. Idempotency is tracked in `.state.json` (`child_page_id`) — re-running updates that same page via version bump; it never creates a duplicate and never touches the parent or any sibling page. Chart PNGs are uploaded as attachments on that same child page. Full detail: `references/confluence-contract.md`.

## Verification before declaring success
1. `status == "published"`
2. `errors` is empty (or, if non-empty, each one is surfaced verbatim to the user — never suppressed)
3. `page_id` is present

If credentials are missing (`CONFLUENCE_URL` / `CONFLUENCE_EMAIL` / `CONFLUENCE_TOKEN` / `CONFLUENCE_PARENT_PAGE_ID` env vars), the CLI raises — report the actual error, don't guess at the cause.

## Constraints
- Never publish except when explicitly invoked via `/run-metrics`.
- Never read or attempt to write the parent page or any sibling page — not even to "check" something. The child page is the entire blast radius.
- Never fabricate a `page_id` or URL if the run failed.
- Never load raw Jira issues into context — only the CLI's own numeric summary and file paths reach you.
