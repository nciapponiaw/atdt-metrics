# MAINTENANCE — How to Safely Update This Workspace

> **Read this before changing anything in `.claude/`, `config/`, or `src/metrics_master/`.**
> This project works because several files silently agree on the same facts (metric names,
> measure kinds, chart types, the child-page title). Those agreements are **contracts**.
> Break one half of a contract and the pipeline fails late — often only when you actually
> `/run-metrics`, after the metric has already looked "valid". This guide tells you, for
> each kind of change you might want to make, **every file you must touch** and **how to
> verify** you didn't break a contract.

> **Which document do I read?** `README.md` — what the workspace is + how to run it (**start
> here**). **`MAINTENANCE.md` (this file)** — how to change it without breaking the
> cross-file contracts. `CLAUDE.md` — the always-loaded, agent-facing rules (roster,
> non-negotiables, architecture). `WORKFLOW_Short-Explanation.md` — a one-page pipeline
> walkthrough. The same map lives at the top of `README.md`.

All workspace changes go in `.claude/`, `config/`, `src/metrics_master/`, `CLAUDE.md`.

---

## The 5 Golden Rules

1. **A change is not done until every layer agrees.** A metric or feature can live in up to
   four layers (command → agent → skill → config/code). Changing one and not the others is
   the #1 cause of breakage.
2. **The config layer encodes the report's shape.** `registry.py`'s `valid_kinds` /
   `valid_charts` sets, `engine.py`'s `_dispatch` table, and `render/charts.py`'s
   `RENDERERS` dict all hardcode the same two vocabularies (measure kinds, chart types). If
   you add one without the other, `validate` either wrongly passes a broken config or wrongly
   rejects a good one.
3. **Run the verification suite after every change** (see [Pre-Commit
   Verification](#pre-commit-verification)). It is copy-paste and takes seconds.
4. **Work on a branch, commit per logical change.** Keep the previous working state reachable
   for rollback.
5. **Test with a real dry-run before trusting a change** (`/dry-run-metrics` or `cli run
   --dry-run`). Static checks (`validate`, `pytest`) catch contract breaks; only a real
   compute catches a JQL or Jira-field mistake.

---

## The Layered Architecture — Where Things Live

A single "feature" usually has presence in several layers. When you change behavior, walk
**down** this list and ask "does this layer need to change too?"

| Layer | Files | Owns |
|---|---|---|
| **1. Command** | `.claude/commands/*.md` | Entry point, recognized flags, which agent runs it, model. |
| **2. Agent** | `.claude/agents/<name>.md` | One agent's role, tools, constraints, **output contract** (what it must report). |
| **3. Skill** | `.claude/skills/<name>/SKILL.md` (+ `references/`) | The *how* — procedure, schema, conventions. Preloaded via the agent's `skills:` frontmatter. |
| **4. Metric config** | `config/metrics/<name>.yaml` | One metric's `filter` (JQL), `measure`, `group_by`, `chart`, `target`. |
| **5. Global config** | `config/settings.yaml` | Fiscal calendar, quarter labels, closure labels, `sections:` (what renders where), `weekly_metrics:`. |
| **6. Registry / Calendar** | `registry.py`, `calendar.py` | Loads YAML, resolves `{{template}}` variables, validates schema (`valid_kinds`, `valid_charts`). |
| **7. Engine** | `engine.py`, `dimensions.py`, `measures.py`, `links.py`, `jira_client.py`, `quarterly_report.py` | Computes a `MetricResult` from a config (`_dispatch` maps `measure.kind` to a handler) — or, for the Quarterly Metrics Summary report, computes its section data directly from Jira/Confluence (no metric config involved). |
| **8. Render** | `render/charts.py` (`RENDERERS` dict), `render/page_builder.py`, `render/quarterly_report_builder.py` | Turns `MetricResult` into a PNG (`output/<name>.png`) and the page HTML, or turns the quarterly report's section data into its own page HTML. |
| **9. Publish** | `publish.py`, `confluence_client.py` | Orchestrates 6→7→8, then creates/updates the target page (one of the two contracts in the Contract Registry below) and uploads attachments where applicable. |
| **10. CLI** | `cli.py` | The single process entry point every command/agent shells out to (`run` / `compute` / `validate` / `add-metric`). |

> Layer 2 vs 3: **agent file = enforcement** (what it must/must not do, what it's allowed to
> touch). **SKILL.md = knowledge** (the procedure, the schema, the conventions). If you're
> changing *what an agent is allowed to do*, touch the agent. If you're changing *how a task
> is done*, touch the skill. Adding a metric field usually touches both the skill (document
> it) and nothing else — the agent's job doesn't change.

---

## The Contract Registry

These are the implicit agreements. Each row is a fact that **multiple files assume**. If you
change the fact, change it in **every file listed**.

### Contract 1 — A metric's name is repeated in up to 4 places
`config/metrics/<name>.yaml` (filename, and the `name:` field inside it — **must match**, nothing enforces this at load time, a mismatch just means the loaded config's `name` differs from its filename and confuses every downstream reference to "the metric"), a `sections:` entry in `config/settings.yaml` (controls whether/where it renders on the page — **a typo here silently drops the metric from the page with no error**, `publish.py::_organize_sections` just skips names it can't find), optionally `weekly_metrics:` in `config/settings.yaml` (**same silent-drop behavior** — `publish.py::run` filters by name and a typo just means fewer metrics run, no error), and `output/<name>.png` (the rendered chart filename, derived from the config's `name` field by `render/charts.py::_save`).

**Depended on by:** `registry.py::load_metric` (loads by filename) · `publish.py::_organize_sections` (matches by `name` against `sections:`) · `publish.py::run` (matches by `name` against `weekly_metrics:` and against `--metric`) · `render/charts.py::_save` (writes `output/{name}.png`). *(Pre-Commit check 3 greps for orphaned/mismatched names.)*

### Contract 2 — `measure.kind` vocabulary (3 files must agree)
The set of valid measure kinds is hardcoded independently in three places:
- `registry.py::validate_metric` — `valid_kinds = {"count", "duration", "ratio", "coverage", "created_vs_resolved"}`
- `engine.py::MetricEngine._dispatch` — the `dispatch` dict keys (`_compute_count`, `_compute_coverage`, `_compute_created_vs_resolved`, `_compute_ratio`, `_compute_duration`)
- `.claude/skills/metric-author/references/metric-schema.md` — the documented schema per kind (agent-facing; not enforced but must stay accurate)

If you add a kind to `registry.py` but not `engine.py`, `validate` passes but `run` fails at compute time with `"Unknown measure kind"`. If you add it to `engine.py` but not `registry.py`, `validate` rejects an otherwise-working config. **Change recipe: "Add a measure kind" below.**

### Contract 3 — `chart` vocabulary (2 files must agree)
- `registry.py::validate_metric` — `valid_charts` set (9 entries)
- `render/charts.py::RENDERERS` — dict keys (must be the exact same 9 entries; `publish.py::_render` falls back to `RENDERERS["bar"]` if a chart type isn't found, which silently mis-renders instead of erroring)

**Depended on by:** `.claude/skills/metric-author/references/metric-schema.md` (documents the same 9 values — keep the list in sync if you add one).

### Contract 4 — The Confluence child page title
`publish.py::PAGE_TITLE = "Computed Metrics MA"` is the single source of truth for the regular metrics page. It is echoed in prose in `README.md`, `CLAUDE.md`, and `.claude/skills/metrics-publisher/references/confluence-contract.md`. **These docs were already found to be stale once** (an older doc pass called it "Computed Metrics (Automated)" — that name was never in the code). If you rename the page, grep for `Computed Metrics` across `*.md` and update every hit in the same commit. The separate Quarterly Metrics Summary report's title is built dynamically (`publish.py::QUARTERLY_REPORT_TITLE_SUFFIX`, `f"{quarter_label}{QUARTERLY_REPORT_TITLE_SUFFIX}"`) — see Contract 8.

### Contract 5 — `.state.json` is the idempotency key, and it is not committed
`confluence_client.py::publish_page` stores `{"child_page_id": "<id>"}` in `.state.json` (repo root, gitignored) after the first publish of "Computed Metrics MA". `publish_named_page` (used by the Quarterly Metrics Summary report, Contract 8) stores each quarter's page ID under a sibling `"pages": {"quarterly_summary:<label>": "<id>", ...}` dict in the same file — same mechanism, separate namespace. Every later publish reads the relevant ID, and updates the same page if it still exists. **Never hand-edit or delete `.state.json`** — doing so orphans the real Confluence page(s) and the next publish creates a duplicate. If the file is genuinely lost (new machine, fresh clone), the next publish will create *new* pages for whatever keys are missing — that's expected recovery behavior, not a bug, but it means the old page(s) are now orphaned and should be manually archived.

### Contract 6 — Template variables are resolved once, at load time
`registry.py::_build_context` resolves `{{current_quarter}}` / `{{prev_quarter}}` / `{{prev_prev_quarter}}` against `config/settings.yaml` (`fiscal_year_start_month`, `quarter_label_pattern`, optional `current_quarter` override) or the CLI `--quarter` flag passed to `compute`, **before** the config reaches the engine. Any metric YAML with a literal quarter label instead of `{{current_quarter}}` silently stops updating at the next fiscal rollover — `validate` does not catch this (it's a content choice, not a schema error). **This is unrelated to `run --quarter`** — on the `run` subcommand specifically, `--quarter` no longer flows through this template-resolution path at all; it routes straight to `publish.py::run_quarterly_report` instead (Contract 8). Only `compute --quarter` still uses this contract.

### Contract 7 — Weekly-cadence metrics are a list, not a computed property
`weekly_metrics:` in `config/settings.yaml` is a hand-maintained list — nothing infers "weekly-cadence" from a metric's `measure.kind` (a `coverage` or `created_vs_resolved` metric is *usually* weekly but isn't required to be; a `count` metric with a `by_week` `group_by` is also weekly-shaped). When you add a new weekly-shaped metric, you must add it to this list yourself — `/add-metric`'s skill prompts for this, but nothing enforces it after the fact.

### Contract 8 — `run --quarter <label>` is a completely separate publish target
`cli.py::main` branches on `args.quarter` on the `run` subcommand: if set, it calls `publish.py::run_quarterly_report` instead of `publish.py::run`, and rejects the combination with `--metric`/`--weekly` (exit 1). This target:
- "Work Breakdown by Category" has three subsections. **Light Cycles & IDDs** (label `LightCycles`) and **CVEs & IDDs** (label `ATDT_CVE`) are both computed by the shared `quarterly_report.py::_compute_label_section(quarter_label, settings, label)` (JQL: `project = SHLD AND issuetype = Story AND labels = <label> AND labels = "<label>" AND status = Done` — Story only, so Epics/Tasks/Sub-tasks are excluded, and Done-only — plus per-issue `issuelinks` filtered to link type `"Problem/Incident"` (outward phrase "causes") for the Linked IDDs column). `compute_light_cycles_section`/`compute_cve_section` are thin wrappers that call it and rename the `"total"` key to `total_light_cycles`/`total_cves` respectively — `total_idds` is scoped per subsection (CVEs' linked IDDs are not added to Light Cycles' count or vice versa). **Research Projects** (label `ATD_Project`, `quarterly_report.py::compute_research_projects_section`) is intentionally *not* built on `_compute_label_section` — its JQL has no `status = Done` filter (a research project ticket can be in any status; the Status column shows whatever it actually is), it has no Linked IDDs/POC Impact columns, and it has a **Summary** column instead: a raw excerpt (verbatim source text, not a generated summary — confirmed with the user, who chose this over adding an LLM call to the pipeline) via `quarterly_report.py::_first_paragraph_text`, preferring the first `<p>` of the linked Confluence page's body (`confluence_client.py::get_page_body_html`) and falling back to the Jira ticket's own rendered description (`jira_client.py::get_rendered_description`) when no page is found. The excerpt is HTML-escaped at render time (`render/quarterly_report_builder.py`, `html.escape`) since it's free-text prose far more likely than a ticket title to contain `&`/`<` that would otherwise break the page's storage-format XML. `publish.py::run_quarterly_report` calls all three compute functions and passes `{"light_cycles": ..., "cves": ..., "research_projects": ...}` to the render module; the CLI JSON summary carries `total_light_cycles`/`total_idds`, `total_cves`/`total_cve_idds`, and `total_research_projects`.
- **Confluence Page column** (`quarterly_report.py::_find_emulation_page`): prefers Jira's own "Confluence content" backlinks — `jira_client.py::get_confluence_remote_links` calls `GET /rest/api/3/issue/{key}/remotelink` and keeps only `application.type == "com.atlassian.confluence"` entries. This is the same curated data Jira's issue view "Confluence content" panel shows, and is far more precise than a text search — a CQL text match on an issue key routinely surfaces rollup pages that just happen to mention many tickets, not the page that documents this one. Only falls back to `confluence_client.py::find_page_for_issue` (CQL `text ~ "<key>"`) when Jira has no such link for the issue. Either path filters out: pages outside the pipeline's own space (`confluence_client.py::resolve_space_key`/`page_space_key`, comparing canonical keys since `CONFLUENCE_SPACE` may be an alias like `atd` for the real key `VR`), this pipeline's own generated pages (`exclude_page_ids=confluence_client.known_report_page_ids()`), and any page whose title contains "quarterly summary" or "metrics" (`quarterly_report.EXCLUDE_PAGE_TITLE_SUBSTRINGS`) — rollup/summary pages that were never meant to be "the" page for a specific emulation. No match after filtering renders "—", never a wrong guess.
- Renders via `render/quarterly_report_builder.py::build_quarterly_report_page` (plain HTML table, no charts). SHLD Story / Linked IDDs cells render as `<a>{key}</a> — {summary}`; Status renders as a Confluence `status` macro (colour `Green` for `Done`/`In Progress`, `Grey` otherwise); Confluence Page renders the found page's title as link text (not a generic "View"). **Full-width gotcha:** Confluence's renderer still caps plain `<h2>`/`<h3>`/`<p>` elements to a narrow "readable" column even on a full-width page — only tables span the full container. Every heading/text block is therefore wrapped in its own `<table style="width:100%;border:none;"><tr><td style="padding:0;border:none;">...</td></tr></table>` cell, mirroring the same trick `page_builder.py` already uses (see its header band / `_build_full_width_section`). Any new subsection added here must follow the same wrapping or it will render narrow despite the page-level full-width property being set correctly.
- Publishes via `confluence_client.py::publish_named_page` under `confluence.quarterly_report_parent_page_id` (`config/settings.yaml`) — see Contracts 4 and 5 for the title/state-file details.
To add another "Work Breakdown by Category" subsection that matches the Light Cycles/CVEs shape (Done-only, POC Impact + Linked IDDs columns): add a thin `compute_*_section` wrapper around `_compute_label_section` in `quarterly_report.py` (new label constant + renamed `"total"` key), call it from `publish.py::run_quarterly_report`, add it to the `section_data` dict and to `summary_fields`, and add a `_build_category_subsection(...)` call to `render/quarterly_report_builder.py::build_quarterly_report_page` — no new render code needed since `_build_category_subsection` is already generic across subsections. A subsection with a genuinely different shape (different filter, different columns) — like Research Projects — needs its own `compute_*_section` and its own `_build_*_subsection` instead; don't force it through `_compute_label_section`/`_build_category_subsection` just for reuse's sake.

---

## Change Recipes

### Recipe A — Add a metric
1. `/add-metric <name>` (or manually: `cli add-metric <name>`, edit the YAML, register in `config/settings.yaml`).
2. Fill `filter` / `measure` / `group_by` / `chart` per `.claude/skills/metric-author/references/metric-schema.md`.
3. Add the name to a `sections:` list. If weekly-cadence, also add to `weekly_metrics:`.
4. `cli validate --metric <name>` → `cli run --dry-run --metric <name>`.
5. Only then `/run-metrics --metric <name>`.

### Recipe B — Add a measure kind
Touches **Contract 2** — all three files, together:
1. `engine.py` — add a `_compute_<kind>` method and a new entry in `_dispatch`'s `dispatch` dict.
2. `registry.py::validate_metric` — add the new kind to `valid_kinds`.
3. `.claude/skills/metric-author/references/metric-schema.md` — document the new kind's fields.
4. Write/extend a unit test in `tests/` covering the new kind (see Pre-Commit Verification).
5. `cli validate` + a real `cli run --dry-run --metric <name>` against a metric using it.

### Recipe C — Add a chart type
Touches **Contract 3**:
1. `render/charts.py` — add `render_<type>` and a new `RENDERERS` entry.
2. `registry.py::validate_metric` — add it to `valid_charts`.
3. `.claude/skills/metric-author/references/metric-schema.md` — document it.
4. Dry-run a metric using the new chart type and open `output/page_preview.html` to eyeball it.

### Recipe D — Add a `group_by` dimension type
1. `dimensions.py` — add a `_by_<type>` resolver, wire it into both `resolve_dimension` and `resolve_dimension_jql` (they must support the same set — `duration` with `group_by` uses `resolve_dimension_jql`, everything else uses `resolve_dimension`).
2. `.claude/skills/metric-author/references/metric-schema.md` — document it.
3. Dry-run a metric using it.

### Recipe E — Change the fiscal calendar
1. `config/settings.yaml` — `fiscal_year_start_month` and/or `quarter_label_pattern`.
2. Re-derive `quarters:` (the last 3 labels + display names) — this list is hand-maintained, not auto-generated; `calendar.py::all_quarter_labels` computes the *labels* on the fly but `settings.yaml::quarters` supplies the *display names* used by `by_quarter` grouping — keep them in sync.
3. `cli compute --format json` for a metric using `{{prev_quarter}}` / `by_quarter` and eyeball the labels.

### Recipe F — Change the Confluence page title or layout
1. `publish.py::PAGE_TITLE` — the title (Contract 4 — grep and update every doc that names it in the same commit).
2. `render/page_builder.py` — the HTML assembly / section layout.
3. `config/settings.yaml::sections:` — which metrics group under which heading.
4. Dry-run and inspect `output/page_preview.html` before publishing for real.

### Recipe G — Rename a metric
1. Rename the file `config/metrics/<old>.yaml` → `<new>.yaml` **and** update its internal `name:` field (Contract 1 — they must match).
2. Update every `sections:` / `weekly_metrics:` reference in `config/settings.yaml`.
3. `cli validate` (won't catch a stale `sections:` reference — that's a silent no-op per Contract 1, so also grep: see Pre-Commit check 3).
4. The old `output/<old>.png` and any Confluence attachment under that filename become orphaned — harmless (gitignored, and the next publish just uploads under the new filename) but you may want to delete the stale attachment from Confluence manually.

---

## Pre-Commit Verification

Copy-paste, run from the repo root:

```bash
# 1. All metric configs are schema-valid
python -m metrics_master.cli validate

# 2. Unit tests pass
python -m pytest tests/ -q

# 3. Contract 1 — every metric registered in settings.yaml actually exists as a config file,
#    and every config file is registered in at least one section (a metric nobody can see)
python3 - <<'EOF'
import yaml, pathlib
settings = yaml.safe_load(pathlib.Path("config/settings.yaml").read_text())
registered = {m for s in settings.get("sections", []) for m in s.get("metrics", [])}
weekly = set(settings.get("weekly_metrics", []))
files = {p.stem for p in pathlib.Path("config/metrics").glob("*.yaml")}

missing_files = (registered | weekly) - files
orphaned = files - registered

if missing_files:
    print(f"ERROR: referenced in settings.yaml but no config file exists: {missing_files}")
if orphaned:
    print(f"WARNING: metric config exists but isn't in any section (won't render): {orphaned}")
if not missing_files and not orphaned:
    print("Contract 1 OK: every registered name has a file, every file is registered.")
EOF

# 4. Every command references an agent that exists; every agent's skills: resolve
python3 - <<'EOF'
import re, pathlib
agents = {p.stem for p in pathlib.Path(".claude/agents").glob("*.md")}
skills = {p.name for p in pathlib.Path(".claude/skills").iterdir() if p.is_dir()}

for cmd in pathlib.Path(".claude/commands").glob("*.md"):
    text = cmd.read_text()
    m = re.search(r"^agent:\s*(\S+)", text, re.M)
    if m and m.group(1) not in agents:
        print(f"ERROR: {cmd} references missing agent '{m.group(1)}'")

for agent in pathlib.Path(".claude/agents").glob("*.md"):
    text = agent.read_text()
    for skill in re.findall(r"^\s*-\s*(\S+)\s*$", text.split("skills:")[1].split("---")[0]) if "skills:" in text else []:
        if skill not in skills:
            print(f"ERROR: {agent} references missing skill '{skill}'")

print("Command/agent/skill wiring check complete.")
EOF

# 5. Frontmatter parses as valid YAML on every command/agent/skill file
python3 - <<'EOF'
import yaml, pathlib
for pattern in [".claude/commands/*.md", ".claude/agents/*.md", ".claude/skills/*/SKILL.md"]:
    for f in pathlib.Path(".").glob(pattern):
        text = f.read_text()
        if not text.startswith("---"):
            print(f"ERROR: {f} has no frontmatter")
            continue
        fm = text.split("---", 2)[1]
        try:
            yaml.safe_load(fm)
        except yaml.YAMLError as e:
            print(f"ERROR: {f} frontmatter is invalid YAML: {e}")
print("Frontmatter check complete.")
EOF

# 6. .claude/settings.json is valid JSON
python3 -c "import json; json.load(open('.claude/settings.json')); print('settings.json OK')"

# 7. A real dry-run still renders (catches JQL/engine breaks static checks miss)
python -m metrics_master.cli run --dry-run --metric team_velocity
python -m metrics_master.cli run --dry-run --weekly
```

If all seven pass, the change is safe to commit.
