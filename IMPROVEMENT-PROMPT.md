# Prompt — Restructure atdt-metrics as an agentic workspace

> Paste everything below the line into a fresh Claude Code session opened in
> `atdt-metrics` (branch `Improve-Metrics-Agentic`). Delete this file when done.

---

Restructure this project (`atdt-metrics`) into a Claude Code agentic workspace following the **same structure and conventions** as my reference project:

`/Users/maristela.ames/Library/CloudStorage/OneDrive-ArcticWolfNetworksInc/Documents/GitHub/ATDT-Agentic-Hunting_Claude`

**Before writing anything, study the reference project** — read its `README.md`, `CLAUDE.md`, `MAINTENANCE.md`, `WORKFLOW_Short-Explanation.md`, and the contents of `.claude/commands/`, `.claude/agents/`, `.claude/skills/` (frontmatter conventions especially), and `.claude/settings.json`. Mirror its patterns; do not invent a new layout.

## Goal

Today the pipeline runs only via raw CLI calls and has a single `.claude/agents/metrics-master.md`. I want the same operating model as the reference project: **slash commands as entry points → agents for enforcement → skills for knowledge → docs that make the workspace maintainable by a new owner.**

## 1. `.claude/` layer (mirror the reference conventions)

**Commands** (`.claude/commands/*.md`) — the user-facing entry points, with the same frontmatter style (`description`, `argument-hint`, `model`, `effort`, `allowed-tools`, `disable-model-invocation` where appropriate). Create at minimum:
- `/run-metrics` — full pipeline publish. Must support these optional arguments, passed through to the CLI: `--weekly`, `--metric <name>`, `--quarter <label>` (document them in the command's `argument-hint`). Note: `--metric` and `--quarter` already exist in the CLI; `--weekly` does NOT — implement it as a new CLI flag on `run` that executes only a configured list of weekly-cadence metrics (define that list in `config/settings.yaml`, e.g. the weekly coverage/IDD metrics — do not hardcode metric names in Python)
- `/dry-run-metrics` — local render only, opens/points to `output/page_preview.html`
- `/add-metric` — guided creation of a new metric YAML (scaffold via `cli add-metric`, fill filter/measure/group_by/chart, register in `settings.yaml`, validate, dry-run)
- `/validate-metrics` — run `cli validate` and summarize failures with the exact file/field to fix

**Agents** (`.claude/agents/*.md`) — enforcement files with frontmatter (`name`, `description`, `skills:`, `model`, `maxTurns`, `tools`, `permissionMode`) like the reference. Keep the roster small and purpose-built (this pipeline is simpler than the hunting one — do NOT over-decompose):
- `metrics-runner` — executes the CLI, reads stdout only (evolve the existing `metrics-master.md` into this)
- `metric-author` — creates/edits metric YAMLs and `config/settings.yaml` sections
- `metrics-publisher` — publish step + Confluence verification (child page only)

Each agent file = **what it must/must not do + its output contract**. Use **relative paths only** — the current `metrics-master.md` hardcodes an absolute home-directory path; remove that.

**Skills** (`.claude/skills/<agent-name>/SKILL.md`, `user-invocable: false`) — the *how*, preloaded via each agent's `skills:` frontmatter, with `references/` subfolders for stable knowledge:
- metric YAML schema (all supported `measure` kinds: count, coverage, created_vs_resolved, ratio, duration; chart options; `{{template}}` variables)
- JQL conventions (count-first, mandatory `AND issuetype != Sub-task` for emulation metrics, Done-vs-Closed semantics)
- fiscal calendar rules (FY starts May, Q1 = May–Jul, auto-resolution, `--quarter` override)
- Confluence publishing contract (idempotent update of "Computed Metrics (Automated)" child page; parent/siblings are NEVER touched)

**Settings** (`.claude/settings.json`) — extend the existing permissions allowlist so the commands run with minimal prompting (the venv python invocations, read-only git, the Atlassian MCP tools already listed). Follow the reference project's allow/deny style.

## 2. Documentation set (same four-doc pattern as the reference)

- **`README.md`** — rewrite with the reference's structure: what the workspace is, a **Documentation Map table** (which doc / when to read it / audience), a **Workspace Configuration table** (concept → where it lives), first-time setup, and how to run via slash commands (CLI kept as the fallback).
- **`CLAUDE.md`** — keep as the always-loaded agent-facing contract. Preserve ALL existing non-negotiable rules verbatim in spirit (token efficiency, count-first, sub-task exclusion, no fabrication, idempotent publishing, child-page-only, no MCP runtime dependency, template variables). Add the agent roster + command inventory. **Fix the stale path**: it currently says `/Users/natalia.ciapponi/repos/atdt-metrics` — use repo-relative instructions instead of any absolute path.
- **`MAINTENANCE.md`** — new, modeled on the reference: the layered architecture table (command → agent → skill → config → Python), a **Contract Registry** (facts multiple files silently agree on — e.g., metric names appearing in `config/metrics/<name>.yaml` AND `config/settings.yaml` sections AND chart output filenames; the `{{current_quarter}}` template variable; the child-page title; the Done/Closed semantics), **change recipes** ("Add a metric", "Add a measure kind", "Change the fiscal calendar", "Change the Confluence page layout", "Rename a metric"), and a copy-paste **Pre-Commit Verification** block (at minimum: `cli validate`, `pytest`, a grep that every metric in `config/metrics/` is registered in `settings.yaml` and vice versa).
- **`WORKFLOW_Short-Explanation.md`** — new one-pager with the same flavor as the reference: an ASCII flow of the pipeline (config → registry/calendar → engine → render → publish), who does what (command → agent → CLI subcommand), and the key semantics (Done vs Closed, coverage, quarter auto-detection).

## 3. Hard constraints

- **Do not change the Python pipeline's behavior**, with ONE exception: adding the `--weekly` flag to the `run` CLI subcommand as described above (a thin filter over the already-registered metrics — no changes to engine/measure logic). This task is otherwise workspace/docs/config layering only. If you find a genuine bug, list it in the final summary — don't fix it unprompted.
- All existing CLAUDE.md non-negotiables remain in force and must be restated in the new agent/skill files where relevant (especially: never load raw Jira issues into context; agents read CLI stdout summaries only).
- No secrets in any committed file; `.env` stays untracked.
- Work on the current branch (`Improve-Metrics-Agentic`), commit in logical steps (e.g., commands / agents+skills / docs / settings), and do not push.

## 4. Verification before you finish

1. `python -m metrics_master.cli validate` passes.
2. `python -m metrics_master.cli run --dry-run --metric team_velocity` still works.
2b. `python -m metrics_master.cli run --dry-run --weekly` runs exactly the weekly-cadence metrics listed in `config/settings.yaml` and nothing else.
3. Every command file references only agents that exist; every agent's `skills:` entries resolve to an existing `SKILL.md`; frontmatter parses (no tabs, valid YAML).
4. `pytest tests/` passes.
5. Finish with a summary: files created/changed, the new command → agent → skill wiring, and anything you deliberately left out.
