---
name: tableau-migration
description: >-
  Migrate Tableau dashboards/workbooks into Hex. Use when someone wants to
  convert, port, rebuild, or migrate Tableau content (.twb / .twbx, Tableau
  Cloud/Server views) into Hex projects — fetching workbooks, parsing the XML,
  mapping the data connection, porting worksheets to Hex SQL + native chart
  cells, and batch-migrating a whole folder. Triggers: "migrate Tableau to
  Hex", "port my Tableau dashboards", "convert a .twb", "Tableau → Hex".
---

# Tableau → Hex Migration

A CLI-driven migration where **the Agent does the porting** (not Hex's in-product Notebook Agent). You fetch a Tableau workbook, read its XML as the source of truth, rebuild each worksheet as Hex SQL + native chart cells against a real data connection, and QA with screenshots.

**Priority order (say this to the customer up front):** (1) **accuracy** of SQL + visuals first, (2) **similar look & feel** second. Some Tableau features have no clean 1:1 in Hex (maps, LOD/detail tooltips, cosmetic styling) — name those early so "it isn't pixel-identical" is never a surprise. Philosophy: **cover the basis, don't gold-plate.**

## Reference docs (read on demand)
- [`reference/connection-mapping.md`](reference/connection-mapping.md) — resolve the Tableau → Hex data connection.
- [`reference/tableau-semantics.md`](reference/tableau-semantics.md) — **Phase 1 (code conversion):** Tableau construct → warehouse SQL/Python (calcs, LOD, window calcs, params, sets, RLS), the per-dialect docs step, and SQL consolidation into shared cells.
- [`reference/building-cells.md`](reference/building-cells.md) — **Phase 2 (viz build-out):** native-cell template library + styling map.
- [`reference/datasource-guide.md`](reference/datasource-guide.md) — author a Hex guide mirroring the Tableau data source (semantic layer for Threads/agent), published via `hex guide`.
- [`reference/gotchas.md`](reference/gotchas.md) — parsing correctness rules, Hex CLI quirks, app layout.

## What you need before starting
- **Tableau access** — a Personal Access Token (for `scripts/tableau_fetch.py`) *or* exported `.twb`/`.twbx` files.
- **Hex CLI** installed and authed, and the **target Hex data connection** the migrated cells will query.
- **Hex-YAML editor validation (install this).** You'll hand-edit the exported project YAML (native cells, app layout). Install the **[RedHat YAML VS Code extension](https://marketplace.visualstudio.com/items?itemName=redhat.vscode-yaml)** — it auto-fetches the official **Hex file-format JSON Schema from [SchemaStore](https://www.schemastore.org/)** and gives you live validation, key/value autocomplete, and hover docs for the whole Hex YAML surface. **Schema detection is filename-based: name the file `*.hex.yaml`** and the schema applies automatically (opening one also prompts the extension install). This is the fastest way to understand and get the YAML right before importing. (For CLI/CI, validate against the hosted schema `https://static.hex.site/hex-file-schema.json` — see `building-cells.md`.)
- `credentials/tableau.env` filled in from `credentials/tableau.env.example` (pod URL + site + PAT). Gitignored.

## Workflow at a glance
0. **Prioritize & organize** the customer's dashboards → one folder.
1. **Pilot 1–2 dashboards** end-to-end, QA, tune.
2. **Port each workbook:** resolve connection → parse XML → plan+build SQL → validate → build native cells → run.
3. **Batch the rest** with the folder loop + manifest.

---

# Step 0 — Prioritize & organize (do this FIRST, before any workbook)

Migration is the best moment a team ever gets to prune. Most Tableau sites are 60–80% dead weight — abandoned drafts, one-offs, near-duplicates. **Do not migrate what nobody uses.** Guide the customer through a short triage before a single `.twb` is fetched.

1. **Take inventory.** On Tableau Cloud/Server the fastest source is the site's *Views* admin export / "Content" list (carries **view counts** + **last-accessed**); otherwise ask. Per dashboard capture: name, owner, last-viewed, 90-day view count, and a one-line "what decision does this drive?"

2. **Prioritize on three axes**, then bucket:

   | Axis | Migrate-first | Drop / defer |
   |------|---------------|--------------|
   | **Usage** | viewed regularly, real audience | ~0 views in 90 days |
   | **Business value** | drives a recurring decision | ad-hoc / one-time / "nice to have" |
   | **Freshness / ownership** | actively maintained, clear owner | stale, orphaned |

   **Get the customer to confirm the buckets** — it's a business call, not yours: **Migrate** (high usage+value+maintained), **Archive/rebuild-later** (matters but stale/redundant — snapshot, don't port as-is), **Drop** (dead — say so explicitly). Collapse **near-duplicates** into one canonical version.

3. **Organize into ONE folder** (the batch loop points at a single directory of `.twb`s):
   - **Tableau Cloud/Server:** `scripts/tableau_fetch.py` (`--project` / `--name`) — downloads + auto-extracts `.twb` from `.twbx` into `tableau_exports/`.
   - **Local files:** customer exports `.twb`/`.twbx` (Tableau Desktop → *File → Export Packaged Workbook*) into one folder.
   - Name the folder per wave (e.g. `tableau_exports/wave1/`) so waves stay separate.

4. **Complexity triage — set expectations.** Flag known-gap features up front (detail in [`reference/gotchas.md`](reference/gotchas.md) + [`building-cells.md`](reference/building-cells.md)): **maps** → Python cell; **detail/LOD text tooltips** → no clean equivalent; **external file/spreadsheet source** (region map, quarterly goals) → rows aren't in the `.twb`; **ask the customer for the file**, don't guess; **extract-backed datasource** (`.hyper`) → **ask which connection it's built on** (don't read the extract) and expect snapshot drift vs. live — see [`connection-mapping.md`](reference/connection-mapping.md) → *Extracts*; **cosmetic styling** → Hex defaults; **heavy calc/parameter logic** → more per-workbook tuning; **dashboard objects** → images & text rebuild as markdown cells (image via upload), but **web-page/iframe embeds have no native equivalent** (flag, like maps). Mark them in the plan so the non-pixel-perfect result isn't a surprise.

# First pass — cap at 1–2 dashboards (pilot, then scale)

**Do not run the full folder first.** Migrate **one or two** dashboards end-to-end, then stop and tune.
- **Pick the pilot(s):** one *simple/representative* (proves the happy path); if two, add one *representative-complex* (surfaces gaps early). Don't make the single hardest edge case your only pilot.
- **Go all the way:** create → SQL → validate → native cells → run → **customer visually QAs** vs. the Tableau original.
- **Tune, then scale:** fold fixes (connection mapping, calc translations, format mappings, filter scopes) back into this playbook/templates *before* batching the rest.

Why: the agent is **blind to rendered output**, so a human check on a tiny first batch catches systematic errors before they multiply across dozens of workbooks.

# Guiding the customer
- **State the priority order up front** (accuracy first, look & feel second).
- **Name the two human gates:** (1) **data connection** — you'll ask when the target is ambiguous; (2) **visual QA** — you can't see rendered charts, so they confirm fidelity on the pilot and each batch.
- **Tell them what to provide:** Tableau access (PAT) *or* exported files; and which **Hex data connection** to target.
- **Work in waves, not one big bang:** pilot → tune → batch a wave → QA → next wave.

---

# Porting a workbook (the core per-workbook loop)

1. **Resolve the data connection, then load its SQL dialect docs.** Match on metadata (type + database), not names/hosts. Fetch the published `.tdsx` if the workbook uses `sqlproxy`. Full procedure → [`reference/connection-mapping.md`](reference/connection-mapping.md). ⚠️ **Never assume Snowflake** — customers run on all mainstream warehouses. Once you know the warehouse, open its function reference and confirm the syntax for what this workbook uses (`QUALIFY` support, week-start, date-parse tokens, regex/percentile names). Links + the "what actually varies" checklist → [`reference/tableau-semantics.md`](reference/tableau-semantics.md).

2. **Create the Hex project and inject the raw `.twb`.** The XML fits in **one markdown cell** (verified ~121 KB, no chunking) — keeps the source of truth in the project while you port:
   ```bash
   hex project create ...
   hex cell create -s "$(cat workbook.twb)"   # markdown cell holding the source XML
   ```
   **Keep this `.twb` cell in the notebook, but never add it to the app layout** — it's a working reference for whoever maintains the migration, not stakeholder-facing. (Same for the raw SQL cells; see step 6.)

3. **Parse the XML, then PLAN shared queries — don't default to one SQL per chart.** The `.twb` XML is the **source of truth**; screenshots are QA only. A dashboard's worksheets usually sit on one data source, so **cluster worksheets** that share base table + join + data-source/context filters + a compatible grain into **one SQL cell** (finest grain, union of columns); each chart's EXPLORE aggregates/filters over that dataframe. Strategy + when-to-split → [`reference/tableau-semantics.md`](reference/tableau-semantics.md).
   - ⚠️ **Sweep ALL filter scopes.** Data-source/context/workbook filters apply to every sheet → put in the shared `WHERE`; **worksheet** filters stay per-cell. Missing a shared-scope filter silently changes totals.
   - ⚠️ **Resolve scrambled field names** via encodings → internal-name → caption+formula, never by caption alone.
   - **Translate calcs/LOD/window/params** into the resolved dialect's SQL (LOD → `OVER (PARTITION BY)`; table calcs resolve in SQL, not the chart; params → Hex input cells + Jinja). Full mapping → [`reference/tableau-semantics.md`](reference/tableau-semantics.md).
   - (The above, plus the relative-date off-by-one, are detailed in [`reference/gotchas.md`](reference/gotchas.md).)

4. **Validate with the run-status oracle.** The Hex CLI can't read cell output — use **COMPLETED-vs-ERRORED** as a boolean oracle to test SQL validity, probe schema, and check type-casts. Fix until COMPLETED.

5. **Build native chart/KPI cells** by clone-and-override from `templates/` — see [`reference/building-cells.md`](reference/building-cells.md).

6. **Run and QA.** `hex project run` (async — poll `run status`), then hand the project link to the customer for visual QA. Set the app layout via export/import if desired → [`reference/gotchas.md`](reference/gotchas.md).

7. **Author a Hex guide for the data source (once per data source).** Ship a semantic layer, not just charts: mirror the Tableau data source as a retrieved Hex guide (canonical metrics + join patterns + migration risk areas) so the customer's team can self-serve in Threads / the Notebook Agent. Built from the Phase-1 parse, reused across every dashboard on that data source, published headless via `hex guide preview`/`publish`. Template + what-to-keep-out → [`reference/datasource-guide.md`](reference/datasource-guide.md).

---

# Batch migration (folder loop)

Point at a folder of `.twb` files and migrate them as a set. Three phases:

**Phase 1 — parallel, read-only (safe to fan out):** scan → parse each workbook (worksheets, marks, calcs, filters at all scopes, datasource) → resolve each connection (fetch `.tdsx` if `sqlproxy`) → **cluster worksheets into shared queries** → produce a per-workbook **plan** (connection, `sql_cell → [charts]` clusters, chart specs). **Batch every ambiguous-connection question into ONE ask** — don't stop per workbook.

**Phase 2 — sequential, mutating (one workbook at a time):** run the *Porting a workbook* loop for each. **Write status to the manifest after each** so the batch is resumable and fail-soft — a bad workbook is marked `failed` and skipped, not fatal. **Author each data source's guide once** (step 7) — workbooks sharing a data source share one guide; refresh it, don't duplicate.

**Phase 3 — verify (one batch):** collect all project links and present them for human visual QA in a single pass.

### Manifest (`migrations.json`) — the resumable backbone
```json
[
  {
    "twb_file": "marketing_funnel.twb",
    "title": "Marketing Funnel",
    "hex_project_id": null,
    "connection_id": "019a59ac-8c0f-...",
    "status": "pending",            // pending → parsed → built → run → verified | failed
    "worksheets": 4,
    "sql_clusters": 2,               // shared SQL cells — expect << worksheets
    "notes": ""                      // e.g. "map → python cell", "ambiguous connection: asked"
  }
]
```
On rerun, skip any workbook whose `status` is `verified` (or `run`, if re-verifying). Record `failed` + the error in `notes` and continue.

> **Scope note:** this is the single-stream loop (Phase 2 sequential). If a folder has category **subfolders** and volume warrants, the same phases can fan out one agent per subfolder — but keep the human gates in the main thread and cap concurrency (~2–3) for Hex kernel limits.

---

# Files in this skill
- `SKILL.md` — this playbook (workflow spine).
- `reference/` — on-demand detail: `connection-mapping.md`, `tableau-semantics.md` (Phase 1), `building-cells.md` (Phase 2), `datasource-guide.md` (semantic-layer guide), `gotchas.md`.
- `templates/` — clone-and-override native-cell configs (METRIC + EXPLORE bar/line/area/pie/scatter/faceted/pivot, `_filter_snippet.json`).
- `tableau-zoo/` — regression fixtures (`.twb` inputs + parity ground truth + Hex goldens).
- `scripts/tableau_fetch.py` — fetch `.twb`/`.twbx` from Tableau Cloud/Server (`--list` / `--name` / `--project`).
- `credentials/tableau.env.example` — template for Tableau PAT + pod + site. Copy to `tableau.env` (gitignored).
- `tableau_exports/`, `working/` — local downloads + scratch YAML (gitignored).
