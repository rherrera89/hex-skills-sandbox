---
name: looker-migration
description: >-
  Migrate Looker dashboards/Looks into Hex. Use when someone wants to convert,
  port, rebuild, or migrate Looker content (LookML models/explores, user-defined
  or LookML dashboards, Looks) into Hex projects — discovering content over the
  Looker REST API 4.0, resolving the LookML connection to a Hex data connection,
  porting Looker's generated SQL + calc logic to warehouse SQL, rebuilding each
  tile as Hex SQL + native chart cells, and batch-migrating a whole folder.
  Triggers: "migrate Looker to Hex", "port my Looker dashboards", "convert a
  LookML dashboard", "rebuild my Looks in Hex", "Looker → Hex".
---

# Looker → Hex Migration

A fully CLI-driven, **headless** migration. You discover Looker content over the REST API, treat LookML + the dashboard/Look JSON as the source of truth, translate + QA the SQL yourself, and rebuild the dashboard in Hex against a real data connection. The **viz build-out (Phase 2) is a choice** you offer the customer: *this coding agent* hand-builds the native cells (spends their frontier-model subscription tokens, no Hex credits), **or** you hand the build to **Hex's in-product notebook agent** via `hex thread` (better dashboards/SQL in Hex house style, spends Hex credits). The accuracy layer (connection + SQL translation + the fidelity gate) is always the coding agent's job regardless.

**Priority order (say this to the customer up front):** (1) **accuracy** of SQL + visuals first, (2) **similar look & feel** second. A few Looker features need approximation or deliberate setup in Hex (maps, custom/marketplace viz, some exotic table calcs; user-attribute row-level security needs a deliberate Jinja/RBAC setup) — name those early so "it isn't pixel-identical" is never a surprise. Philosophy: **cover the basis, don't gold-plate.**

## Looker hands you the SQL and the numbers — use it

Looker will **hand you both the SQL and the answers over the API**, so you don't reconstruct SQL from scratch and you aren't blind to the rendered numbers:

- **Generated SQL.** `looker_fetch.py sql <query-spec>` → `POST /queries/run/sql` returns **Looker's own generated warehouse SQL** for a tile's query. Phase 1 becomes *port and repoint Looker's SQL*, not *reverse-engineer it from measures*. It's already in the resolved dialect.
- **Reference values.** `looker_fetch.py query <query-spec>` → `POST /queries/run/json` returns the tile's **actual result rows**. This gives Phase 1.5 a real **numeric parity oracle** — you can diff Hex's output against Looker's true numbers, not just the blind COMPLETED/ERRORED check. Lean on it hard; it's the biggest fidelity win in this migration.

Treat these as ground truth for *what the number is*; still translate the LookML deliberately for *why* (grain, joins, filters) so the ported SQL is maintainable and not an opaque paste.

## Two layers — convert them separately

Looker has two independent layers (same split the semantic-layer migration literature uses):

| Layer | Source (production = API-first) | Becomes in Hex |
|---|---|---|
| **Semantic model** | LookML views + model + explores (Looker API, or `.lkml` files offline) | shared SQL cells + a **Hex guide** (default, fully headless) — and *optionally* a governed **semantic model** (`type: model`/`view`), see step 8 |
| **Dashboards** | `GET /dashboards/{id}` — covers **user-defined (UDD) AND LookML** dashboards, same JSON | a Hex project: SQL cells + native chart/KPI cells + app layout |
| **Looks** | `GET /looks/{id}` — one saved query | one chart/KPI cell (a thin one-tile case of the dashboard path) |

⚠️ **UDD is the primary path.** Most real Looker dashboards are **user-defined** (built in the UI, in no `.lkml` file) and are reachable **only** via the API. The API returns UDD and LookML dashboards as the *same* `Dashboard` JSON, so discovery keys off the API, not files. `.dashboard.lookml` parsing is a secondary, offline-only path.

## Reference docs (read on demand)
- [`reference/connection-mapping.md`](reference/connection-mapping.md) — resolve the LookML model's `connection:` → warehouse → **Hex data connection**.
- [`reference/lookml-semantics.md`](reference/lookml-semantics.md) — **Phase 1 (code conversion):** LookML construct → warehouse SQL/Python (dimensions, measures, `dimension_group`, derived tables/PDTs, joins, `sql_always_where`/`access_filter`, `filters`/`parameters` + Liquid, dashboard table calcs), the per-dialect docs step, and SQL consolidation into shared cells. **Use Looker's generated SQL as the reference.**
- [`reference/sql-review.md`](reference/sql-review.md) — **Phase 1.5 (SQL-fidelity review gate):** ledger → independent re-derivation & diff → mistake-class checklist → **numeric parity against Looker's own values** + differential oracle probes. Catches semantically-wrong SQL that *passes* the run oracle.
- [`reference/building-cells.md`](reference/building-cells.md) — **Phase 2, option A (coding agent hand-builds):** the Looker-tile → Hex-cell map + native-cell template library + styling map. (Option B — the notebook-agent handoff — is in step 6 below.)
- [`reference/datasource-guide.md`](reference/datasource-guide.md) — author a Hex **guide** mirroring the LookML model (the default, fully-headless semantic layer for Threads/agent), published via `hex guide`. LookML *is* a semantic model — this is a near-direct lift.
- [`reference/semantic-model.md`](reference/semantic-model.md) — **optional, higher-fidelity:** construct a governed Hex **semantic model** (`type: model`/`view`) from LookML and publish it via `hex context`. Requires one manual UI step (create the empty semantic project). Example: [`templates/semantic-model.example.yaml`](templates/semantic-model.example.yaml).
- [`reference/gotchas.md`](reference/gotchas.md) — LookML/Looker-API parsing correctness rules, Hex CLI quirks, app layout.

## What you need before starting
- **Looker access** — an API3 key (client_id/client_secret) for `scripts/looker_fetch.py` *or* a checkout of the LookML project's Git repo (offline path). For UDD dashboards the **API is required** (files can't see them).
- **Hex CLI** installed and authed, and the **target Hex data connection** the migrated cells will query.
- **Hex-YAML editor validation (install this).** You'll hand-edit exported project YAML (native cells, app layout). Install the **[RedHat YAML VS Code extension](https://marketplace.visualstudio.com/items?itemName=redhat.vscode-yaml)** — it auto-fetches the official **Hex file-format JSON Schema from [SchemaStore](https://www.schemastore.org/)** and gives live validation, autocomplete, and hover docs for the whole Hex YAML surface. **Schema detection is filename-based: name the file `*.hex.yaml`** and the schema applies automatically. (For CLI/CI, validate against `https://static.hex.site/hex-file-schema.json` — see `building-cells.md`.)
- `credentials/looker.env` filled in from `credentials/looker.env.example` (base URL + API3 key), or a `~/.looker/looker.ini`. Gitignored.

## Workflow at a glance
0. **Prioritize & organize** the customer's dashboards → one shortlist.
1. **Pilot 1–2 dashboards** end-to-end, QA, tune.
2. **Port each dashboard:** resolve connection → fetch contract + generated SQL → plan+build SQL → validate → **SQL-fidelity review (with numeric parity)** → build the dashboard (coding agent **or** notebook agent) → run → ship the semantic layer (guide, +optional semantic model).
3. **Batch the rest** with the folder loop + manifest.

---

# Step 0 — Prioritize & organize (do this FIRST, before any dashboard)

Migration is the best moment a team ever gets to prune. Most Looker instances are 60–80% dead weight — abandoned drafts, one-offs, near-duplicates. **Do not migrate what nobody uses.** Guide the customer through a short triage before porting a single dashboard.

1. **Take inventory.** `looker_fetch.py list-dashboards` (UDD + LookML), `list-looks`, `list-models`. For **usage** (the value axis), Looker exposes it well via its own **System Activity** model — run an inline query against `model: system__activity` (the `history` explore grouped by `dashboard.id` / `look.id` for run counts over the last 90 days; needs a role with `see_system_activity`). Per dashboard capture: title, owner, last-run, 90-day run count, and a one-line "what decision does this drive?"

2. **Prioritize on three axes**, then bucket:

   | Axis | Migrate-first | Drop / defer |
   |------|---------------|--------------|
   | **Usage** | run regularly, real audience | ~0 runs in 90 days |
   | **Business value** | drives a recurring decision | ad-hoc / one-time / "nice to have" |
   | **Freshness / ownership** | actively maintained, clear owner | stale, orphaned |

   **Get the customer to confirm the buckets** — it's a business call, not yours: **Migrate**, **Archive/rebuild-later** (matters but stale/redundant — snapshot, don't port as-is), **Drop** (dead — say so explicitly). Collapse **near-duplicates** into one canonical version.

3. **Organize into ONE shortlist** (the batch loop points at a set of dashboard ids / a folder):
   - **Live:** a list of dashboard ids (`looker_fetch.py dashboard <id>` per id → `looker_exports/`). Group a wave into one working directory.
   - **Offline:** the LookML Git checkout + any `.dashboard.lookml` files in one folder.

4. **Complexity triage — set expectations.** Flag the features that need approximation or deliberate setup up front (detail in [`reference/gotchas.md`](reference/gotchas.md) + [`building-cells.md`](reference/building-cells.md)): **custom/marketplace viz** (vis type outside the known set) → approximate or Python/flag; **maps** (`looker_map`) → Python cell; **merged results** (`merge_result_id`) → a join or companion query; **pivots / table calcs** → resolved in SQL, not the chart; **user-attribute RLS** (`access_filter`) → Hex **RBAC via Jinja** (current-user context wired into the SQL `WHERE`); doable but non-trivial to get right — set it up and **test it deliberately**, don't assume it's ported; **derived tables / PDTs** → CTE/subquery, expect the same cost. Mark them in the plan so a non-pixel-perfect result isn't a surprise. (Two things that are **not** gaps and need no special handling: **cross-filtering** — Hex supports it natively in the UI, click a data point → **"Keep"** → apply to all cells using that data; and **per-tile refresh** — Hex runs/refreshes cells individually.)

# First pass — cap at 1–2 dashboards (pilot, then scale)

**Do not run the full shortlist first.** Migrate **one or two** dashboards end-to-end, then stop and tune.
- **Pick the pilot(s):** one *simple/representative* (proves the happy path); if two, add one *representative-complex* (surfaces gaps early — a pivot, a table calc, a derived table). Don't make the single hardest edge case your only pilot.
- **Go all the way:** discover → SQL → validate → **numeric parity** → native cells → run → **customer visually QAs** vs. the Looker original.
- **Tune, then scale:** fold fixes (connection mapping, LookML translations, format mappings, filter scopes) back into this playbook/templates *before* batching the rest.

Why: even with Looker's value oracle, the agent is **blind to rendered layout**, so a human check on a tiny first batch catches systematic errors before they multiply.

# Guiding the customer
- **State the priority order up front** (accuracy first, look & feel second).
- **Name the two human gates:** (1) **data connection** — you'll ask when the target Hex connection is ambiguous; (2) **visual QA** — you can't see rendered charts, so they confirm layout/format fidelity on the pilot and each batch. (Numbers you *can* now check yourself against Looker's API — do so.)
- **Tell them what to provide:** Looker API3 key *or* a LookML Git checkout (+ API for UDDs); and which **Hex data connection** to target.
- **Work in waves, not one big bang:** pilot → tune → batch a wave → QA → next wave.

---

# Porting a dashboard (the core per-dashboard loop)

1. **Resolve the data connection, then load its SQL dialect docs.** The LookML model declares a `connection:`; `looker_fetch.py connection <name>` returns its dialect + database + schema. Match on metadata (dialect + database), not names/hosts, to a Hex connection. Full procedure → [`reference/connection-mapping.md`](reference/connection-mapping.md). ⚠️ **Never assume Snowflake** — Looker runs on all mainstream warehouses. Once you know the warehouse, open its function reference and confirm the syntax for what this dashboard uses (`QUALIFY` support, week-start, date-parse tokens, regex/percentile names). Links + the "what actually varies" checklist → [`reference/lookml-semantics.md`](reference/lookml-semantics.md).

2. **Fetch the contract + Looker's generated SQL; create the Hex project and inject the source.**
   ```bash
   python3 scripts/looker_fetch.py dashboard <id>           # -> looker_exports/<id>.contract.json
   # per tile whose SQL you'll port, grab Looker's own SQL as the reference:
   python3 scripts/looker_fetch.py sql <tile-query-spec>.json
   hex project create ...
   hex cell create -s "$(cat looker_exports/<id>.contract.json)"   # markdown cell holding the source contract
   ```
   **Keep this contract cell (and, if useful, the LookML views) in the notebook, but never add it to the app layout** — it's a working reference for whoever maintains the migration, not stakeholder-facing. (Same for the raw SQL cells; see step 7.)

3. **Read the contract + LookML, then PLAN shared queries — don't default to one SQL per tile.** A dashboard's tiles usually sit on **one explore**, so **cluster tiles** that share base table + join graph + explore-scoped filters (`sql_always_where` / `always_filter`) + a compatible grain into **one SQL cell** (finest grain, union of columns); each chart's EXPLORE aggregates/filters over that dataframe. Strategy + when-to-split → [`reference/lookml-semantics.md`](reference/lookml-semantics.md).
   - ⚠️ **Sweep ALL filter scopes.** An explore's `sql_always_where` / `always_filter` and any dashboard filter with a default apply broadly → put in the shared `WHERE`; a tile's own `query.filters` stay per-cell. Missing a shared-scope filter silently changes totals.
   - ⚠️ **Resolve fields via LookML, not the humanized label.** A tile's `fields` are `view.field` ids — resolve each through the view's `dimension`/`measure`/`dimension_group` definition to its real `sql:` + aggregation. Same caption on two joined views resolves only by the qualified id.
   - **Translate LookML → dialect SQL** (measures → aggregates; `dimension_group` → `DATE_TRUNC` columns; derived tables → CTEs; `${TABLE}`/`${view.field}` refs resolved; Liquid `{% parameter %}` → Hex input + Jinja; dashboard `dynamic_fields` table calcs → `OVER()`). Full mapping → [`reference/lookml-semantics.md`](reference/lookml-semantics.md). **Cross-check each cluster's SQL against `looker_fetch.py sql` output.**

4. **Validate with the run-status oracle.** The Hex CLI can't read cell output — use **COMPLETED-vs-ERRORED** as a boolean oracle to test SQL validity, probe schema, and check type-casts. Fix until COMPLETED.

5. **SQL-fidelity review gate (mandatory — don't skip to charts).** The oracle proves the SQL *runs*, not that it's *right*. Before building any cells, run an **independent, structured, targeted** review of each SQL cluster. Write a **translation ledger** (LookML→SQL per tile), **independently re-derive** the intended SQL from the LookML + contract and **diff** it (spawn a subagent where supported — Claude Code — else re-derive with fresh eyes), run the **mistake-class checklist**, and — the Looker upgrade — **diff Hex's actual output against Looker's own values** (`looker_fetch.py query`) for each cluster, plus differential oracle probes for suspect filters/joins. Any divergence → fix, re-run step 4, re-review. Full procedure → [`reference/sql-review.md`](reference/sql-review.md).

6. **Build the dashboard — two options; let the customer pick.** The QA'd SQL cells from step 5 are the input either way.
   - **Option A — this coding agent hand-builds the native cells** (like the Tableau migration): clone-and-override from `templates/`, mapping each Looker tile type to a Hex cell → [`reference/building-cells.md`](reference/building-cells.md). **Cost:** the customer's frontier-model subscription tokens; **no Hex credits.** Fully deterministic and inspectable, but you're blind to the rendered result (visual QA gate matters).
   - **Option B — hand the build to Hex's notebook agent** (`hex thread create "<scoped prompt>" --project <id>`; poll `hex thread get`; iterate `hex thread continue`). **Cost:** Hex credits; **upside:** it designs charts + layout in Hex house style and generally produces a better-looking dashboard + SQL than a blind hand-build. Scope the prompt (audience + business question + the tiles), don't over-specify styling — over-determined prompts get dropped. Prereq: the project already has the QA'd SQL cells; the "headless agent threads" feature must be enabled for the workspace.
   - **How to choose:** default to **B** when the customer has Hex credits to spend and wants the best-looking result fastest; use **A** when they'd rather spend frontier-model tokens (their Claude subscription) than Hex credits, or want every cell deterministic and diff-able. Say the tradeoff out loud and let them decide.

7. **Run and QA.** `hex project run` (async — poll `run status`), then hand the project link to the customer for visual QA. Set the app layout via export/import if desired → [`reference/gotchas.md`](reference/gotchas.md).

8. **Ship the semantic layer (once per model/explore).** Hand the customer a governed layer, not just charts, so their team can self-serve in Threads / the notebook agent.
   - **Default — a Hex guide (fully headless).** Mirror the LookML model as a retrieved guide (canonical measures + join patterns + migration risk areas), published via `hex guide preview`/`publish` (Markdown; no pre-existing anything). Template + what-to-keep-out → [`reference/datasource-guide.md`](reference/datasource-guide.md).
   - **Optional — a governed semantic model (`type: model`/`view`).** For customers who want an enforced metrics layer (many ex-Looker teams will), construct Hex semantic YAML from the LookML and publish via `hex context`. ⚠️ **One manual UI step:** the customer creates an empty semantic project in Hex and gives you its id (the CLI can't create one; `hex context` only *populates* an existing project). Then it's CLI the rest of the way. Full mapping + flow → [`reference/semantic-model.md`](reference/semantic-model.md).

---

# Batch migration (folder / id-list loop)

Point at a shortlist of dashboards and migrate them as a set. Three phases:

**Phase 1 — parallel, read-only (safe to fan out):** for each dashboard → fetch contract (`looker_fetch.py dashboard`), resolve its model's connection, read the explore's LookML (fields, joins, `sql_always_where`), pull Looker's generated SQL per tile → **cluster tiles into shared queries** → produce a per-dashboard **plan** (connection, `sql_cell → [tiles]` clusters, chart specs). **Batch every ambiguous-connection question into ONE ask** — don't stop per dashboard.

**Phase 2 — sequential, mutating (one dashboard at a time):** run the *Porting a dashboard* loop for each — including the **SQL-fidelity review gate** (step 5, with numeric parity) after oracle-validation and before building cells; record the gate result in the manifest `notes`. **Write status to the manifest after each** so the batch is resumable and fail-soft — a bad dashboard is marked `failed` and skipped, not fatal. **Author each explore's guide once** (step 8) — dashboards sharing an explore share one guide; refresh it, don't duplicate.

**Phase 3 — verify (one batch):** collect all project links and present them for human visual QA in a single pass.

### Manifest (`migrations.json`) — the resumable backbone
```json
[
  {
    "dashboard_id": "42",
    "title": "Marketing Funnel",
    "kind": "UDD",
    "hex_project_id": null,
    "connection_id": "019a59ac-8c0f-...",
    "status": "pending",            // pending → fetched → built → run → verified | failed
    "tiles": 6,
    "sql_clusters": 2,               // shared SQL cells — expect << tiles
    "parity": "",                    // e.g. "3/3 clusters tie to Looker"
    "notes": ""                      // e.g. "map tile → python cell", "access_filter RLS flagged"
  }
]
```
On rerun, skip any dashboard whose `status` is `verified` (or `run`, if re-verifying). Record `failed` + the error in `notes` and continue.

> **Scope note:** this is the single-stream loop (Phase 2 sequential). If the shortlist has category **groups** and volume warrants, the same phases can fan out one agent per group — but keep the human gates in the main thread and cap concurrency (~2–3) for Hex kernel limits.

---

# Files in this skill
- `SKILL.md` — this playbook (workflow spine).
- `reference/` — on-demand detail: `connection-mapping.md`, `lookml-semantics.md` (Phase 1), `sql-review.md` (Phase 1.5 review gate), `building-cells.md` (Phase 2 option A — coding agent), `datasource-guide.md` (headless guide), `semantic-model.md` (optional governed semantic model via `hex context`), `gotchas.md`.
- `templates/` — clone-and-override native Hex cell configs (METRIC + EXPLORE bar/line/area/pie/scatter/faceted/pivot, `_filter_snippet.json`) + `semantic-model.example.yaml` (the target format for the optional semantic model).
- `scripts/looker_fetch.py` — Looker REST API 4.0 client: `whoami` / `list-*` / `connection` / `explore` / `dashboard` / `look` / **`sql`** (generated SQL) / **`query`** (reference values) / `raw`.
- `credentials/looker.env.example` — template for the Looker base URL + API3 key. Copy to `looker.env` (gitignored); or use `~/.looker/looker.ini`.
- `looker_exports/`, `working/` — local downloads + scratch YAML (gitignored).

## Hex CLI cheat-sheet (verified against `hex 1.2026.07.21`)
- **Guides (headless):** `hex guide preview <*.md>` → `preview_id`; `hex guide publish <preview_id>`. Markdown only.
- **Semantic model (optional):** `hex context preview [--config-path <p>] [--base draft|latest]` → `preview_id`; `hex context publish <preview_id|->`. Driven by a `hex_context.config.json` with a **`semanticProjects: [{id, path}]`** array (key is `semanticProjects`, *not* `semanticModels` — the alpha docs are stale) and/or **`guides`**. The `id` must be an **existing** semantic project (create the empty shell in the UI first; a nonexistent id → `Forbidden`). `hex context`'s subcommands are hidden from `--help` but real.
- **Notebook agent (Phase 2 option B):** `hex thread create <prompt> [--project <id> | --new-project] [--preview-id <id>]` → poll `hex thread get <id>` → `hex thread continue <id> <prompt>`. Uses Hex credits; needs the headless-agent-threads feature.
