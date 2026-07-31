---
name: tableau-migration
description: >-
  Migrate Tableau dashboards/workbooks into Hex by delegating the build to Hex's
  in-product notebook agent. Use when someone wants to convert, port, rebuild, or
  migrate Tableau content (.twb / .twbx, Tableau Cloud/Server views) into Hex —
  this coding agent parses the workbook and writes a precise migration brief, then
  Hex's notebook agent (which can see the live warehouse schema + workspace
  context) builds a **generative app** on top of gated SQL cells, and this agent
  verifies with a SQL-fidelity gate + a visual-QA loop. Triggers: "migrate Tableau
  to Hex", "port my Tableau dashboards with the Hex agent", "convert a .twb",
  "Tableau → Hex".
---

# Tableau → Hex Migration (generative-app build)

A CLI-driven migration where **this coding agent understands the Tableau source and
verifies the result, and Hex's in-product notebook agent builds the dashboard as a
generative app.** You fetch a workbook, read its XML as the source of truth,
translate its semantics, and write a **migration brief** into the Hex project; the
notebook agent reads that brief and builds a **generative app** on a natively-gated
SQL data layer; then you run a **SQL-fidelity gate** on the SQL and a **visual-QA
loop** on the render.

> **The deliverable is a generative app, not a classic notebook dashboard.** A
> generative app hits Tableau's bespoke layout, tab navigation, and pixel styling
> in a way native EXPLORE/METRIC chart cells can't — while the numbers stay in
> inspectable, gated SQL cells underneath. Hand-building native cells survives only
> as a **fallback** for when the notebook agent isn't available (see the build-path
> gate).

## Why delegate the build to the notebook agent

This coding agent (reading this skill) is **blind to the things that make the build
correct**: it can't see the live **warehouse schema** or data, it can't see the
customer's **Hex workspace context** (Context Studio descriptions, endorsed tables,
semantic models, guides), and it can't see the **rendered result**. The notebook
agent has all three — it runs inside the workspace. So for *building in Hex* it is
the better-equipped agent, and delegating the generative-app build to it is the
default path (it spends Hex credits).

> **Division of labor:** this coding agent owns **understanding the Tableau
> workbook** (the durable IP: reading the XML, translating calcs/LOD/table-calcs/
> filters/params) and **verifying the result** (the fidelity gate). The notebook
> agent owns **building it in Hex**. Accuracy is guaranteed by the gate — which
> reviews whoever wrote the SQL — not by this agent hand-writing every query.

**Priority order (say this to the customer up front):** (1) **accuracy** of SQL +
visuals first, (2) **similar look & feel** second. The generative-app default is what
lets you deliver #2 — it reproduces Tableau's bespoke layout/styling far closer than
native cells, and the visual-QA loop verifies the render — while SQL stays gated
underneath for #1. Some Tableau features still have no clean 1:1 in Hex (maps,
LOD/detail tooltips) — name those early so "it isn't pixel-identical" is never a
surprise. Philosophy: **cover the basis, don't gold-plate.**

## Reference docs (read on demand)
- [`reference/connection-mapping.md`](reference/connection-mapping.md) — resolve the Tableau → Hex data connection.
- [`reference/tableau-semantics.md`](reference/tableau-semantics.md) — **understand the workbook:** Tableau construct → warehouse SQL/Python meaning (calcs, LOD, window calcs, params, sets, RLS), filter scopes, and how to cluster worksheets into shared derivations. This is what you distill into the brief.
- [`reference/build-generative-app.md`](reference/build-generative-app.md) — **the build (default):** gate the SQL natively, then have the agent build a **Generative app** on top (bespoke layout, tab nav, pixel styling); the styling spec + the `genAppFiles` verification.
- [`reference/build-notebook-agent.md`](reference/build-notebook-agent.md) — **brief + handoff mechanics:** how to write the migration brief (intent, not literal SQL), inject it (⚠️ `{% raw %}`-wrapped), hand it to the notebook agent, surface the live URL, and iterate. Shared by the generative build.
- [`reference/visual-qa-loop.md`](reference/visual-qa-loop.md) — **render gate (default):** headless Playwright screenshot (persistent profile, one-time login) → panel-by-panel diff vs. the source PNG → surgical fix batch → repeat.
- [`reference/sql-review.md`](reference/sql-review.md) — **SQL-fidelity gate:** ledger → independent re-derivation & diff → mistake-class checklist → read-back + differential probes. Runs on the native SQL cells under the app.
- [`reference/building-cells.md`](reference/building-cells.md) — **fallback build only:** this coding agent hand-builds native cells from templates (for when the notebook agent isn't available).
- [`reference/datasource-guide.md`](reference/datasource-guide.md) — author a Hex guide mirroring the Tableau data source (semantic layer for Threads/agent), published via `hex guide`.
- [`reference/gotchas.md`](reference/gotchas.md) — parsing correctness rules, Hex CLI quirks, app layout.

## What you need before starting
- **Tableau access** — a Personal Access Token (for `scripts/tableau_fetch.py`) *or* exported `.twb`/`.twbx` files.
- **Hex CLI** installed and authed; the **target Hex data connection** the migrated cells will query; and the **headless-agent-threads feature enabled** for the workspace (the default build path uses `hex thread`).
- `credentials/tableau.env` filled in from `credentials/tableau.env.example` (pod URL + site + PAT). Gitignored.
- **Visual-QA render gate:** `pip install playwright && playwright install chromium`, plus a **one-time headed Hex login** into the screenshot profile (the customer signs in once; every later capture is headless). See [`visual-qa-loop.md`](reference/visual-qa-loop.md).
- **(Fallback path only)** Hex-YAML editor validation — the RedHat YAML VS Code extension for hand-editing exported project YAML. See [`building-cells.md`](reference/building-cells.md).

## Workflow at a glance
0. **Prioritize & organize** the customer's dashboards → one folder.
1. **Pilot 1–2 dashboards** end-to-end, QA, tune.
2. **Port each workbook:** resolve connection → parse XML + understand → build the **generative app** (gate the SQL layer natively, then build the app on top; fall back to hand-built native cells only if the notebook agent is unavailable) → **SQL-fidelity gate** + **visual-QA loop** → ship the guide.
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

   **Get the customer to confirm the buckets** — it's a business call: **Migrate**, **Archive/rebuild-later** (snapshot, don't port as-is), **Drop** (dead — say so). Collapse **near-duplicates** into one canonical version.

3. **Organize into ONE folder** (the batch loop points at a single directory of `.twb`s):
   - **Tableau Cloud/Server:** `scripts/tableau_fetch.py` (`--project` / `--name`) — downloads + auto-extracts `.twb` from `.twbx` into `tableau_exports/`.
   - **Local files:** customer exports `.twb`/`.twbx` (Tableau Desktop → *File → Export Packaged Workbook*) into one folder.

4. **Complexity triage — set expectations.** Flag known-gap features up front (detail in [`gotchas.md`](reference/gotchas.md)): **maps** → Python cell; **detail/LOD text tooltips** → no clean equivalent; **external file/spreadsheet source** → rows aren't in the `.twb`; **ask the customer for the file**; **extract-backed datasource** (`.hyper`) → **ask which connection it's built on**; **web-page/iframe embeds** → no native equivalent (flag, like maps). Put these in the brief as known gaps so the notebook agent doesn't silently approximate them.

# First pass — cap at 1–2 dashboards (pilot, then scale)

**Do not run the full folder first.** Migrate **one or two** dashboards end-to-end, then stop and tune.
- **Pick the pilot(s):** one *simple/representative*; if two, add one *representative-complex* (surfaces gaps early). Don't make the single hardest edge case your only pilot.
- **Go all the way:** parse → brief → gate the SQL → build the generative app → visual-QA loop → **customer's final visual confirm** vs. the Tableau original.
- **Tune, then scale:** fold fixes (connection mapping, calc translations, brief wording, format mappings, screenshot-selector tweaks) back into this playbook *before* batching the rest.

Why: the visual-QA loop gets the render close automatically, but a human confirm on a tiny first batch catches systematic errors before they multiply.

# Guiding the customer
- **State the priority order up front** (accuracy first, look & feel second) and that the deliverable is a **generative app**.
- **Name the human gates:** (1) **data connection** — you'll ask when the target is ambiguous; (2) **screenshot login** — the one-time headed Hex sign-in that powers the visual-QA loop; (3) **final visual confirm** — the loop drives the render to near-parity automatically, then the customer signs off on the pilot and each batch. (You only surface the *build path* as a question if the notebook agent is unavailable and you must fall back to hand-built native cells.)
- **Tell them what to provide:** Tableau access (PAT) *or* exported files; which **Hex data connection** to target; and that the default build spends **Hex credits** (needs the headless-agent-threads feature).
- **Work in waves:** pilot → tune → batch a wave → QA → next wave.

---

# Porting a workbook (the core per-workbook loop)

1. **Resolve the data connection, then note its SQL dialect.** Match on metadata (type + database), not names/hosts. Fetch the published `.tdsx` if the workbook uses `sqlproxy`. Full procedure → [`connection-mapping.md`](reference/connection-mapping.md). ⚠️ **Never assume Snowflake.** (The notebook agent writes the actual dialect SQL against the schema it sees — but you still resolve *which* connection + tables so the brief is right.)

2. **Create the Hex project and inject the raw `.twb`.** The XML fits in one markdown cell (~121 KB, no chunking) — keeps the source of truth in the project:
   ```bash
   hex project create ...
   hex cell create -s "$(cat workbook.twb)"   # markdown cell holding the source XML
   ```
   Keep this `.twb` cell in the notebook but **never add it to the app layout** — it's a maintainer reference. ⚠️ **Wrap any injected reference text (the `.twb`, the brief, the styling spec) in `{% raw %}` … `{% endraw %}`** — Hex markdown cells Jinja-render `{{ }}`, and briefs are full of `{{ param }}` notation (and often a literal empty `{{ }}`), which ERRORs the whole `hex project run` even though every SQL cell is fine. See [`gotchas.md`](reference/gotchas.md).

3. **Parse the XML and understand the workbook.** The `.twb` is the **source of truth**; screenshots are QA only. Produce an intent-level plan, not finished SQL:
   - **Cluster worksheets** that share base table + join + shared filters + a compatible grain into shared **derivations** (a base df + companions for table calcs / ratios / KPIs). Strategy → [`tableau-semantics.md`](reference/tableau-semantics.md) §9.
   - ⚠️ **Sweep ALL filter scopes.** Data-source/context/workbook filters apply to every sheet; worksheet filters are per-chart. A missed shared-scope filter silently changes totals.
   - ⚠️ **Resolve field names** via encodings → internal-name → caption+formula, never by caption alone.
   - **Understand calcs/LOD/window/params** as *meaning* (LOD → per-partition aggregate; table calcs → window; params → input + scope). You describe these as intent in the brief; the notebook agent implements them. Full mapping → [`tableau-semantics.md`](reference/tableau-semantics.md).
   - **Extract the styling values now into a styling spec** (titles, per-member colors as **hex codes from the XML**, tooltip fields, number/date formats). This drives both the generative-app build and the visual-QA diff → [`build-generative-app.md`](reference/build-generative-app.md).
   - Export the original's PNGs for QA: `scripts/tableau_shots.py "<workbook name>"`.

4. **Build path — generative app is the default; native hand-build is a fallback.** There's no "which mode" question in the normal case: **build a generative app.** You only drop to the fallback when the notebook agent isn't available (feature off / no Hex credits).

   | Path | Presentation layer | SQL data layer | Cost | When |
   |---|---|---|---|---|
   | **Generative app (DEFAULT)** | notebook agent builds a **Generative app** (`genAppFiles`) reading the SQL dataframes | native SQL cells — gated the same way regardless of who wrote them | Hex credits (+ your tokens if you pre-build the SQL) | **every migration**, unless the notebook agent is unavailable |
   | **Native hand-build (FALLBACK)** | this coding agent hand-builds native EXPLORE/METRIC cells | this coding agent hand-builds (YAML) | your model tokens | **only** when the notebook agent is unavailable |

   Generative (default) → [`build-generative-app.md`](reference/build-generative-app.md), using the brief/handoff mechanics in [`build-notebook-agent.md`](reference/build-notebook-agent.md) and the render gate [`visual-qa-loop.md`](reference/visual-qa-loop.md). Fallback → [`building-cells.md`](reference/building-cells.md).

   **SQL-first within the generative default.** The app's data layer is always native, inspectable, gated SQL cells — the app reads those dataframes and never re-queries. Two ways to get there: (a) **pre-build + gate the SQL yourself first** (YAML) when the population is subtle (aggressive shared filters, fan-out risk, a relative-date window) — pin the numbers before the app is built; or (b) let the **notebook agent build the SQL cells too** and run the fidelity gate **post-hoc** on them. Default to (b); escalate to (a) for high-stakes/subtle-population workbooks. Either way the SQL is gated before the migration ships. Be honest about cost: the fallback isn't "free" — it spends the customer's frontier-model tokens and builds blind to the warehouse and the render.

5. **Build the generative app (default).** Write the **migration brief** + **styling spec** (intent, not literal SQL — derivations and *what each represents*, plus params, chart specs, layout, and the hex-code styling), inject them as project cells (⚠️ `{% raw %}`-wrapped), then hand off to the notebook agent with a prompt that **opens** with *"Build this as a GENERATIVE APP (App builder → Generative app), not a classic notebook"* and tells it to read those dataframes rather than re-query. `hex thread create --json` → **give the customer the live URL immediately** so they can watch/intervene. Verify `genAppFiles` is non-empty in the export. Full procedure + prompt template → [`build-generative-app.md`](reference/build-generative-app.md); brief/handoff mechanics → [`build-notebook-agent.md`](reference/build-notebook-agent.md).
   - **Fallback only (notebook agent unavailable):** clone-and-override native cells from `templates/` → [`building-cells.md`](reference/building-cells.md).

6. **SQL-fidelity gate (mandatory — the accuracy guarantee).** The gate reviews the SQL *whoever wrote it*. Read every SQL cell's values (`hex cell run --with-output`) and export its source; write a **translation ledger**, **independently re-derive** the intended SQL from the `.twb` and **diff** it (spawn a subagent where supported), run the **mistake-class checklist** (filter scope, relative-date off-by-one, `COUNT` vs `COUNTD`, fan-out join, caption-not-formula, LOD grain), and **prove** suspect filters/joins with differential probes. It runs on the native SQL cells under the app — **post-hoc** when the agent built the SQL, or *before* the app when you pre-built it (the app reads those gated dataframes and never re-queries). Any divergence → fix (agent-built SQL: `hex thread continue` naming the divergence, or edit the cell; pre-built/fallback: edit the SQL) and re-check. Full procedure → [`sql-review.md`](reference/sql-review.md).

7. **Run and QA.** `hex project run` (async — poll `run status`). Confirm what it built via `hex project export`: **`genAppFiles` non-empty** (it's a generative app, not classic — re-prompt if empty), SQL cells present + unchanged, params wired. Then the visual gate:
   - **Generative app (default):** run the **visual-QA loop** — headless Playwright screenshot (persistent profile) → panel-by-panel diff vs. the source PNG → surgical `hex thread continue` fix batch → repeat until parity, then a final human confirm. This is an automated render gate, not a punt to the human → [`visual-qa-loop.md`](reference/visual-qa-loop.md).
   - **Fallback (native hand-build):** hand the customer the project link + the original PNGs (`scripts/tableau_shots.py`) for **visual QA** side-by-side — this agent can't render native cells, so the human is the gate. App layout via export/import → [`gotchas.md`](reference/gotchas.md).

8. **Author a Hex guide for the data source (once per data source).** Ship a semantic layer, not just charts: mirror the Tableau data source as a retrieved Hex guide (canonical metrics + join patterns + migration risk areas) so the team can self-serve in Threads / the notebook agent. Built from the parse, reused across dashboards on that data source, published via `hex guide preview`/`publish`. Template → [`datasource-guide.md`](reference/datasource-guide.md).

---

# Batch migration (folder loop)

Point at a folder of `.twb` files and migrate them as a set. Three phases:

**Phase 1 — parallel, read-only (safe to fan out):** scan → parse each workbook (worksheets, marks, calcs, filters at all scopes, datasource) → resolve each connection → **cluster into shared derivations** → produce a per-workbook **plan + draft brief**. **Batch every ambiguous-connection question into ONE ask**, and **ask the build-path once for the batch** (step 4) — don't stop per workbook.

**Phase 2 — sequential, mutating (one workbook at a time):** run the *Porting a workbook* loop for each — brief → build → **SQL-fidelity gate** → record the gate result in the manifest `notes`. **Write status to the manifest after each** so the batch is resumable and fail-soft. **Author each data source's guide once.**

**Phase 3 — verify (one batch):** collect all project links + original PNGs and present them for human visual QA in one pass.

### Manifest (`migrations.json`) — the resumable backbone
```json
[
  {
    "twb_file": "marketing_funnel.twb",
    "title": "Marketing Funnel",
    "hex_project_id": null,
    "connection_id": "019a59ac-8c0f-...",
    "build_path": "generative",        // generative (default) | native-fallback
    "sql_source": "agent",             // agent (built + gated post-hoc) | prebuilt (gated first)
    "thread_id": null,                  // notebook-agent thread (generative path)
    "status": "pending",                // pending → parsed → briefed → built → gated → run → verified | failed
    "worksheets": 4,
    "derivations": 2,                   // shared df + companions
    "gate": "",                         // e.g. "12 rows, KPIs tie; no divergence"
    "notes": ""                         // e.g. "map → python cell", "ambiguous connection: asked"
  }
]
```
On rerun, skip any workbook whose `status` is `verified`. Record `failed` + the error in `notes` and continue.

---

# Files in this skill
- `SKILL.md` — this playbook (workflow spine).
- `reference/` — `connection-mapping.md`, `tableau-semantics.md` (understand the workbook), `build-generative-app.md` (**the default build** — Generative app), `build-notebook-agent.md` (brief + handoff mechanics), `visual-qa-loop.md` (render gate), `sql-review.md` (fidelity gate), `building-cells.md` (**fallback only** — hand-build native cells), `datasource-guide.md`, `gotchas.md`.
- `templates/` — clone-and-override native-cell configs for the **fallback** hand-build (METRIC + EXPLORE variants, `_filter_snippet.json`).
- `tableau-zoo/` — regression fixtures (`.twb` inputs + parity ground truth + Hex goldens).
- `scripts/tableau_fetch.py` — fetch `.twb`/`.twbx` from Tableau Cloud/Server (`--list` / `--name` / `--project`).
- `scripts/tableau_shots.py` — export PNGs of a workbook's dashboard + worksheets for the visual-QA gate.
- `scripts/hex_shots.py` — headless Playwright screenshot of the built Hex app (persistent profile, one-time login) for the visual-QA loop.
- `credentials/tableau.env.example` — template for Tableau PAT + pod + site. Copy to `tableau.env` (gitignored).
- `tableau_exports/`, `working/` — local downloads + scratch (gitignored).

## Hex CLI cheat-sheet (verified against `hex 1.2026.07.21`)
- **Notebook agent (default build):** `hex thread create "<prompt>" --project <id> --json` → `url` (**hand to the customer to watch/intervene**) + `thread_id`; poll `hex thread get <id>` (`RUNNING`→`IDLE`); iterate `hex thread continue <id> "<prompt>"`. Uses Hex credits; needs the headless-agent-threads feature.
- **Generative app (default form):** the prompt **must open** with "Build this as a GENERATIVE APP…, not a classic notebook" — no CLI flag controls form. Verify with `hex project export <id>` → `genAppFiles` non-empty; re-prompt if it built classic.
- **Hex app screenshot (visual-QA gate):** one-time `python scripts/hex_shots.py --login` (headed; customer signs in), then `python scripts/hex_shots.py "<url>" -o working/shots/migrated.png` (headless). Needs `pip install playwright && playwright install chromium`.
- **Cells:** `hex cell create` makes only code/sql/markdown; INPUT (parameter) cells + connection-less dataframe-SQL companions are authored in YAML (fallback / pre-built-SQL). ⚠️ Injected markdown reference cells (brief, spec, `.twb`) must be `{% raw %}`-wrapped or their `{{ }}` tokens ERROR the run. `hex cell run <id> --with-output` returns result rows; after a YAML import use the **API id from `hex cell list`**, not the export `cellId`.
- **Guides (headless):** `hex guide preview <*.md>` → `preview_id`; `hex guide publish <preview_id>`. Markdown only.
