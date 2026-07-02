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

A CLI-driven migration where **Claude is the porting agent** (not Hex's in-product Notebook Agent). You fetch a Tableau workbook, read its XML as the source of truth, rebuild each worksheet as Hex SQL + native chart cells against a real data connection, and QA with screenshots.

**Priority order (say this to the customer up front):**
1. **Accuracy** of SQL + visuals — first.
2. **Similar look & feel** — second.

Some Tableau features have no clean 1:1 in Hex (maps, LOD/detail tooltips, cosmetic styling). Name those early so "it isn't pixel-identical" is never a surprise. Philosophy throughout: **cover the basis, don't gold-plate.**

## What you need before starting
- **Tableau access** — either a Personal Access Token (for `scripts/tableau_fetch.py` against Tableau Cloud/Server) *or* exported `.twb`/`.twbx` files.
- **Hex CLI** installed and authed, and the **target Hex data connection** the migrated cells will query.
- `credentials/tableau.env` filled in from `credentials/tableau.env.example` (pod URL + site + PAT). Gitignored.

## The workflow at a glance
0. **Prioritize & organize** the customer's dashboards → one folder. *(Step 0 below.)*
1. **Pilot 1–2 dashboards** end-to-end, QA, tune. *(First-pass cap below.)*
2. **Per workbook:** resolve connection → parse XML → build SQL → validate → build native cells → run. *(Porting a workbook below.)*
3. **Batch the rest** with the folder loop + manifest. *(Batch migration below.)*

---

# Step 0 — Prioritize & organize (do this FIRST, before any workbook)

Migration is the best moment a team ever gets to prune. Most Tableau sites are 60–80% dead weight — abandoned drafts, one-off requests, near-duplicates. **Do not migrate what nobody uses.** Guide the customer through a short triage before a single `.twb` is fetched.

**1. Take inventory.** Get the list of candidate dashboards. On Tableau Cloud/Server this is fastest from the site's *Views* admin export or the "Content" list (which carries **view counts** and **last-accessed** dates); otherwise ask the customer to list them. Capture per dashboard: name, owner, last-viewed date, view count (last 90 days), and a one-line "what decision does this drive?"

**2. Prioritize — score each dashboard on three axes:**

| Axis | Migrate-first signal | Drop / defer signal |
|------|---------------------|---------------------|
| **Usage** | Viewed regularly, real audience | ~0 views in 90 days |
| **Business value** | Drives a recurring decision / exec or team relies on it | Ad-hoc, one-time, "nice to have" |
| **Freshness / ownership** | Actively maintained, clear owner | Stale, orphaned, owner gone |

Sort into three buckets and **get the customer to confirm the buckets** — this is a business call, not yours:
- **Migrate** — high usage + high value + maintained.
- **Archive / rebuild-later** — matters but stale or redundant; snapshot it, don't port as-is.
- **Drop** — dead. Say so explicitly; don't silently carry it forward.

Also collapse **near-duplicates** (the same dashboard forked five ways) into one canonical version to migrate.

**3. Organize into ONE folder.** The batch loop points at a single directory of `.twb` files. Get the "Migrate" bucket into that folder:
- **Tableau Cloud/Server:** use `scripts/tableau_fetch.py` (`--project` or `--name`) — it downloads and auto-extracts `.twb` from `.twbx` into `tableau_exports/`. Confirm the pod/site in `credentials/tableau.env` first.
- **Local files:** have the customer drop the `.twb`/`.twbx` exports into one folder (Tableau Desktop → *File → Export Packaged Workbook*).
- Name the folder for the batch (e.g. `tableau_exports/wave1/`) so waves stay separate.

**4. Complexity triage — set expectations before building.** Skim each prioritized workbook for features with known fidelity gaps, and flag them to the customer up front (details in *Migration rules* and *Styling*):
- **Maps** → rebuilt as a Python cell, not a native map (Hex has none).
- **Detail/LOD text tooltips** → no clean EXPLORE equivalent (tooltips are aggregate-only); may fall back to a Python cell or be dropped.
- **Cosmetic-only styling** (donut hole, exact fonts/label placement) → Hex defaults, not 1:1.
- **Heavy calc/parameter logic** → ported to SQL; the more custom calcs, the more per-workbook tuning.
Mark these in the plan so nobody is surprised when the port isn't pixel-perfect.

# First pass: cap at 1–2 dashboards (pilot, then scale)

**Do not run the full folder on the first pass.** Migrate **one or two** dashboards end-to-end first, then stop and tune.

- **Pick the pilot(s):** ideally one *simple/representative* dashboard (proves the happy path) and, if you do two, one *representative-complex* one (surfaces the gaps early). Avoid the single hardest edge-case workbook as your only pilot — it teaches you little about the common case.
- **Go all the way:** create project → SQL cells → validate → native cells → run → **customer visually QAs the result** against the Tableau original.
- **Tune from what you learn:** connection mapping, calc translations, chart/format mappings, filter-scope handling. Fold fixes back into this playbook/templates *before* scaling.
- **Then batch the rest** via the folder loop, now that the rules are calibrated on real output.

Why: the agent is **blind to rendered output** (see *Batch migration*), so a human fidelity check on a tiny first batch is what catches systematic errors before they're multiplied across dozens of workbooks.

# Guiding the customer — posture & expectations
- **State the priority order up front** (accuracy first, look & feel second).
- **Name the two human gates** — the places you'll pause for them:
  1. **Data connection** — when the target Hex connection is ambiguous, you'll ask.
  2. **Visual QA** — you can't see rendered charts, so they confirm fidelity on the pilot and each batch.
- **Tell them what to provide:** Tableau access (PAT) *or* exported files; and which **Hex data connection** to target.
- **Work in waves, not one big bang:** pilot → tune → batch a wave → QA → next wave. Keep waves in separate folders.

---

# Porting a workbook (the core per-workbook loop)

For each workbook, in order:

**1. Resolve the data connection** — see *Data connection mapping* below. Fetch the published `.tdsx` if the workbook uses `sqlproxy`.

**2. Create the Hex project and inject the raw `.twb`.** A workbook's XML fits in **one markdown cell** (verified at ~121 KB) — no chunking:
```bash
hex project create ...
hex cell create -s "$(cat workbook.twb)"   # markdown cell holding the source XML
```
This keeps the source of truth inside the project while you port.

**3. Parse the XML, then PLAN shared queries — don't default to one SQL per chart.** The `.twb` XML is the **source of truth**; screenshots are QA only. Per worksheet, read marks/shelves/encodings/calcs/filters. Before writing any SQL, **cluster the worksheets into shared queries** — see *Consolidate SQL* below. Then author **one SQL cell per cluster** (not per chart) and point each chart at it.
- **Resolve scrambled field names.** Tableau "copy" duplications scramble internal field names — resolve via *encodings → internal-name → caption + formula*, never by caption alone (a "Total ARR KPI" pill can actually be Closed-Won ARR).
- **Sweep ALL filter scopes.** Tableau filters live at four scopes: **worksheet**, **dashboard**, **data-source**, and **shared/context/workbook** (`workbook/shared-views/shared-view//filter`, often `context=true`). Context/workbook + data-source filters apply to **every** sheet on that datasource — push them into the shared query's `WHERE`. **Worksheet-level** filters stay per-chart (as EXPLORE cell filters), so they don't fork the query. Missing a shared-scope filter silently changes totals.
  - *Relative-date gotcha:* Tableau counts the current period as one. `first-period=-1, last-period=0, period-type=year` = **last 2 years**, not 1 — window starts at the beginning of 2 years ago. Don't map `-1` to "1 year back."

**4. Validate with the run-status oracle.** The Hex CLI **cannot read cell output** (`cell get` returns source; `run status` returns only COMPLETED/ERRORED/timing). Use **COMPLETED-vs-ERRORED as a boolean oracle** to test SQL validity, probe schema, and check type-casts (a bogus table → ERRORED confirms the oracle works). Fix until COMPLETED.

**5. Build native chart/KPI cells** by clone-and-override — see *Native-cell templates*.

**6. Run and QA.** `hex project run` (async — poll `run status`), then hand the project link to the customer for visual QA. Set the app layout via export/import if desired (see *App layout*).

## Consolidate SQL — one query feeds many charts

**Mental model:** In Tableau, a dashboard's worksheets almost all sit on **one data source**; each worksheet is just a different viz + shelves + worksheet filter over the same rows. Hex mirrors this: **one SQL cell = the "data source"**, and many EXPLORE/METRIC cells read that same dataframe. Because **EXPLORE aggregates and filters over its input dataframe**, you do *not* need a pre-aggregated SQL per chart. One-SQL-per-chart is the anti-pattern — it duplicates logic, bloats the project, and drifts out of sync when a calc changes.

**Cluster worksheets into shared queries (do this in Phase-1 planning).** Group worksheets that share ALL of:
- the same **base table(s) + join shape**,
- the same **data-source + context/workbook filters** (they apply to every sheet on the datasource anyway),
- a **compatible grain** — build the SQL at the **finest grain any chart in the group needs** (plus its date/id keys); each EXPLORE rolls up from there.

Then emit **one SQL cell per cluster**, selecting the **union of every column + measure** the cluster's charts reference. Point each chart's EXPLORE at that dataframe and let it pick fields / aggregation / worksheet-filter.

**Add calculated columns once, in the shared SQL.** If two charts need the same derived field (a ratio, a bucket, a `CASE`), compute it in the shared query — never fork the query just to add a column.

**Keep queries separate when:**
- **different base table or join shape** — no shared grain to stand on;
- one chart needs **row-level detail** while another needs a heavy pre-aggregation — sharing would force a huge detail dataframe; split if the detail set is large;
- a chart carries a **data-source-level** filter the others don't (worksheet-level filters do *not* force a split — they live on the cell);
- a **KPI/METRIC** that's a single scalar off an unrelated aggregation — a tiny dedicated query is cheaper and clearer than rolling it out of a wide df.

**Make it reviewable:** in the plan/manifest, record the `sql_cell → [charts]` mapping so the consolidation is explicit. Target: the **fewest SQL cells that don't force an incompatible grain** — usually 1–3 per dashboard, not one per worksheet.

### Hex CLI gotchas (confirmed)
- `hex cell create` makes **only** code/sql/markdown cells. Native cells (METRIC/EXPLORE/…) are authored via **YAML export → edit → import** (below).
- `project run` / `cell run` are **async** — no `--no-wait`; poll `run status`. `cell update` has no `-t` flag.
- Freshly imported versions have **no outputs** until you `hex project run` — charts render blank until then.
- **No CLI to start the Notebook Agent** (`hex thread` is list/get only).

---

# Data connection mapping (do this for each workbook)

The Tableau workbook connects to *some* warehouse; the migrated Hex cells need a **Hex data connection**. There's no automatic link — resolve it by matching metadata, not by trusting names or hosts.

**1. Get the Tableau connection's physical details — location depends on connection type:**

| Tableau connection | Qualified table names in `.twb`? | How to read it |
|---|---|---|
| **Live / federated** | ✅ Yes — `[DB].[SCHEMA].[TABLE]` + server/db/schema/warehouse in `<named-connection>` | read from the `.twb` |
| **Published datasource** (`sqlproxy`) | ❌ No — hidden behind the proxy | download the published `.tdsx` (`server.datasources.download`) and read its `.tds` `<named-connection>` + `<relation>` |

Pull: `class` (snowflake/bigquery/…), `server`/host, `dbname`, `schema`, `warehouse`.

**2. Match to a Hex connection** via `hex connection list --json` then `hex connection get <id> --json` → `connectionDetails.snowflake.{accountName, database, warehouse, role}`. **Match on `type` + `database` (+ `schema`).**

**3. Do NOT match on host** — the account URL usually differs even for the same data:
```
Tableau:  qib82113.snowflakecomputing.com  /  B2B_DEMO_DATA . PROD
Hex:      co24109.us-east-2.aws            /  b2b_demo_data
          ^ different host,  same database.  (and possibly a different SNAPSHOT — data parity is NOT guaranteed)
```

**4. Decide:**
- **Exactly one** Hex connection matches type+database → use it; state the assumption in output.
- **Zero or multiple** → **ask the customer** which Hex connection to target. This is the one genuine human gate on connections — data may live in a different account/snapshot.

**5. Translate names 1:1:** Tableau `[DB].[SCHEMA].[TABLE]` → Hex SQL `DB.SCHEMA.TABLE`. Validate reachability with the run-status oracle (wrong role/schema → `ERRORED`, not silent).

Naming Hex connections to match Tableau datasources makes step 2 trivial, but it's a **bonus**, not a requirement.

---

# Native-cell templates (clone-and-override library)

Real, valid exported cell configs live in `templates/`. **Clone one, override a few fields, import.** This beats building native cells from the JSON schema (which fails on hidden required fields like `displayTableConfig`, `showAllBaseTableDetailFields`).

| File | Cell type | Covers (Tableau equivalent) |
|------|-----------|------------------------------|
| `metric.json` | METRIC | KPI / single-value text tile |
| `explore_bar.json` | EXPLORE (bar) | Bar; **grouped** via `chartConfig.series[].barGrouped=true`, **horizontal** via `orientation`, **stacked** = default |
| `explore_line.json` | EXPLORE (line) | Line/time-series; **area** = flip `series[].type` to `area` |
| `explore_faceted.json` | EXPLORE (bar + facet) | Small-multiples / trellis |
| `explore_pivot.json` | EXPLORE (`pivot-table`) | Crosstab / summary table (also carries a filter example) |
| `explore_pie.json` | EXPLORE (pie/donut) | Pie; **donut** via `series[].radius`, data labels via `series[].text.dataLabels` |
| `explore_area.json` | EXPLORE (area) | Area (stacked line) |
| `explore_scatter.json` | EXPLORE (scatter) | Scatter (two measures) |

## How to clone-and-override
1. Load the template JSON, assign a **new `cellId`** — import **won't change an existing cell's type**, so native replacements need new ids (then repoint the `appLayout`).
2. Set `config.dataframe` to the upstream SQL cell's output dataframe.
3. Rewrite `config.spec.fields[]`: set each field's `value` to the (UPPERCASE Snowflake) column, its `title`, `dataType`, and shared `seriesId`; set `displayFormat`.
4. For METRIC: set `valueVariableName` (dataframe) + `valueColumn` + `displayFormat`.
5. Put the cell in `cells[]`, add a matching `appLayout` element, import, then `hex project run`.
6. Validate against `reference/hex-file-schema.json` (or `https://static.hex.site/hex-file-schema.json`) before importing.

## Feature references (how to mirror Tableau)
- **Faceting → small-multiples/trellis:** a `config.spec.fields[]` field with `channel: "h-facet"` or `"v-facet"`, `fieldType: "COLUMN"` — use for Tableau worksheets that put a dimension on Rows/Columns to create panels.
- **Per-cell filters → Tableau worksheet filters:** shape `{"column": ..., "fieldType": "COLUMN", "predicate": {"op": "IS_ONE_OF", "arg": [...]}, "queryPath": [], "columnType": "STRING"}`. Chart cells: `config.spec.filters`. Pivot/table cells: `config.displayTableConfig.filters`. (Workbook/context filters go into the SQL `WHERE` instead.)
- **Pivot / crosstab → Tableau text table:** `config.spec.visualizationType: "pivot-table"` with `row`/`column`/`value` channel fields.
- **Valid EXPLORE channels:** `base-axis, cross-axis, color, opacity, tooltip, h-facet, v-facet, row, column, value, source, destination`. There is **no `detail` channel**.

## Styling — what maps from Tableau
Styling lives in `config.spec.chartConfig` (data labels `series[].text.dataLabels`, donut `series[].radius`, legend `settings.legend.position`, colors via `colorMappings`). Split it — don't try 1:1:

| Styling | In the `.twb`? | Map it? |
|---------|----------------|---------|
| Chart type, stacking, dual-axis | Yes | **Yes** |
| **Colors / palette** (per member) | Yes (color encodings) | **Yes, high value** → `colorMappings` |
| **Number/date formats** ($, %, decimals) | Yes (field/axis `<format>`) | **Yes, high value** → `displayFormat` |
| **Data labels** (show/hide + field) | Yes (mark Label shelf) | **Yes** → `series[].text.dataLabels` |
| Axis titles, legend on/off | Partial | Best-effort |
| Donut hole, label position, fonts | **No Tableau source** | **No** — Hex default / manual polish |

Bottom line: map **chart type, colors, number formats, and data-labels-on/off** from the XML — those drive most of the visual fidelity. Leave cosmetic-only knobs as sensible Hex defaults.

---

# Migration rules (learned)
- **Dates stay dates.** Never `TO_CHAR` a Tableau date to a string in SQL — it breaks the EXPLORE date axis. Keep the column a real DATE, set base-axis `dataType: DATE` + `truncUnit` to match the Tableau date pill (`tqr`→`quarter`, `tmn`→`month`, `YEAR()`→`year`). Preserves Hex's date formatting + granularity controls.
- **Watch pre-bucketed numeric "date" columns.** A column like `CLOSED_MONTH` may be a NUMBER, not a date — `DATE_TRUNC` errors on it. Use the real date column (`CLOSED_DATE`).
- **Maps: no native cell.** Build maps as a Python CODE cell (`px.scatter_geo(df, lat=, lon=, color=, size=, projection="natural earth")`), not an EXPLORE scatter of lat/lon.
- **Tooltips are aggregate-only** (measures, not text/dimension values) → Tableau's **detail/LOD text dimension has no clean EXPLORE equivalent**. Note the gap, don't hack around it. Per-row point charts needing text granularity → Python cell.

---

# Batch migration (folder loop)

Point at a folder of `.twb` files and migrate them as a set. Three phases:

**Phase 1 — parallel, read-only (safe to fan out):** scan the folder → parse each workbook (worksheets, marks, calcs, filters at all scopes, datasource) → resolve each connection (fetch `.tdsx` if `sqlproxy`) → **cluster worksheets into shared queries** (see *Consolidate SQL*) → produce a per-workbook **plan** (connection, `sql_cell → [charts]` clusters, chart specs). **Batch every ambiguous-connection question into ONE ask** — don't stop per workbook.

**Phase 2 — sequential, mutating (one workbook at a time):** for each, run the *Porting a workbook* loop (create → inject → SQL → validate → native cells → run). **Write status to the manifest after each** so the batch is resumable and fail-soft — a bad workbook is marked `failed` and skipped, not fatal.

**Phase 3 — verify (one batch):** collect all project links and present them for human visual QA in a single pass (the agent is blind to rendered output).

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
    "sql_clusters": 2,               // shared SQL cells (see Consolidate SQL) — expect << worksheets
    "notes": ""                      // e.g. "map → python cell", "ambiguous connection: asked"
  }
]
```
On rerun, skip any workbook whose `status` is `verified` (or `run`, if re-verifying). Record `failed` + the error in `notes` and continue.

> **Scope note:** this is the single-stream loop (Phase 2 sequential). If a folder has category **subfolders** (marketing/, sales/) and volume warrants it, the same phases can fan out one agent per subfolder — but keep the human gates (connection ask, visual QA) in the main thread and cap concurrency (~2–3) for Hex kernel limits.

---

# App layout (optional polish)
App layout **is** settable via CLI: `hex project export <id> -o f.yaml` → edit the `appLayout` block → `hex project import f.yaml`. Import matches by `projectId`/`sourceVersionId` (both DO NOT CHANGE) and updates in place as a new version. Schema: `appLayout.tabs[].rows[].columns[]`; a column has `start`/`end` (0–120 grid) + `elements[]`; each element = `{type: CELL, cellId, showLabel, showSource, hideOutput, height}`. Use the **export's** cellIds (they differ from `hex cell` API ids). Map cells by **position/order** (stable), not by content-sniffing. Exclude the `.twb` source cell + raw SQL cells from the app view.

> **UI gotcha:** after importing an appLayout, the Hex app view still shows the empty "build an app" onboarding screen — click **"edit app manually"** once to reveal it. The import worked; this is just a UI acknowledgment.

---

# Files in this skill
- `SKILL.md` — this playbook.
- `templates/` — clone-and-override native-cell configs (METRIC + EXPLORE bar/line/area/pie/scatter/faceted/pivot, `_filter_snippet.json`).
- `scripts/tableau_fetch.py` — fetch `.twb`/`.twbx` from Tableau Cloud/Server (`--list` / `--name` / `--project`).
- `reference/hex-file-schema.json` — Hex file JSON Schema (validate exports before import).
- `credentials/tableau.env.example` — template for Tableau PAT + pod + site. Copy to `tableau.env` (gitignored).
- `REFERENCE_PROJECT_CHECKLIST.md` — checklist for the reference "zoo" projects.
- `tableau_exports/`, `working/` — local downloads + scratch YAML (gitignored).
