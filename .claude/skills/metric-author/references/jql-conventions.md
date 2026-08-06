# JQL Conventions

## Count-first (non-negotiable)
Default every metric to `measure.kind: count` — it maps to a zero-fetch JQL `count()` call. Only reach for per-issue field access (`ratio` with `numerator_type: linked_idd`, or `duration`) when a genuinely per-issue relationship is needed, and restrict the fields queried to the minimum.

## Sub-task exclusion (non-negotiable)
Every emulation-scoped filter MUST include `AND issuetype != Sub-task`. Stories are the emulations we track; Sub-tasks are steps *within* a Story and would double-count if left in.

## Done vs Closed
- **Done** = emulation completed successfully.
- **Closed** = could not complete (see `closure_labels` in `config/settings.yaml`: no infra, no environment, no PoC available, not reproduced, network appliance).
- Velocity-type metrics count **Done only**. Coverage-type metrics show Done vs Remaining. Closure-analysis metrics break down **Closed** by reason label (`by_label_prefix`).

## Template variables, never literals
Always `{{current_quarter}}` / `{{prev_quarter}}` / `{{prev_prev_quarter}}` in `filter` — never a literal `ATDT_FYxxQx` string. `registry.py` resolves these at load time from the fiscal calendar; hardcoding a label silently breaks the metric at the next quarter rollover.

## No fabrication
If a JQL query returns 0 or errors, the engine renders "No Data" (`ratio`) or a `0`/empty series (other kinds) — never invent or carry forward a stale number from a prior run.
