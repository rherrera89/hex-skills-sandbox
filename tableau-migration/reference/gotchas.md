# Gotchas & quirks (parsing rules, Hex CLI, app layout)

Consult these when you hit the relevant step. The parsing rules are correctness landmines — getting them wrong produces silently-wrong numbers, not errors.

---

## Parsing correctness rules

- **Resolve scrambled field names.** Tableau "copy" duplications scramble internal field names — resolve via *encodings → internal-name → caption + formula*, never by caption alone. (A "Total ARR KPI" pill can actually be Closed-Won ARR.)
- **Sweep ALL filter scopes.** Tableau filters live at four scopes:
  - **worksheet** (`<worksheet>//filter`) — stays **per-chart** (an EXPLORE cell filter); does **not** fork the query.
  - **dashboard**
  - **data-source** (`<datasource>/filter`)
  - **shared / context / workbook** (`workbook/shared-views/shared-view//filter`, often `context=true`).

  Context/workbook + data-source filters apply to **every** sheet on that datasource — push them into the shared query's `WHERE`. Missing a shared-scope filter silently changes totals.
  - *Relative-date gotcha:* Tableau counts the current period as one. `first-period=-1, last-period=0, period-type=year` = **last 2 years**, not 1 — the window starts at the beginning of 2 years ago. Don't map `-1` to "1 year back." (Getting this off-by-one produced $9M vs the correct $13M.)
- **Dates stay dates.** Never `TO_CHAR` a Tableau date to a string in SQL — it breaks the EXPLORE date axis. Keep the column a real DATE, set base-axis `dataType: DATE` + `truncUnit` to match the Tableau date pill (`tqr`→`quarter`, `tmn`→`month`, `YEAR()`→`year`). Preserves Hex's date formatting + granularity controls.
- **Watch pre-bucketed numeric "date" columns.** A column like `CLOSED_MONTH` may be a NUMBER, not a date — `DATE_TRUNC` errors on it. Use the real date column (`CLOSED_DATE`).
- **Maps: no native cell.** Build maps as a Python CODE cell (`px.scatter_geo(df, lat=, lon=, color=, size=, projection="natural earth")`), not an EXPLORE scatter of lat/lon.
- **Tooltips are aggregate-only** (measures, not text/dimension values) → Tableau's **detail/LOD text dimension has no clean EXPLORE equivalent**. Note the gap, don't hack around it. Per-row point charts needing text granularity → Python cell.
- **External file / spreadsheet data sources aren't in the `.twb`.** Lookups loaded from Excel/CSV — region → sales-region maps, quarterly goals, targets (`class='excel-direct'` / `'textscan'` under a `federated` connection) — appear in the XML as **schema + join only; the actual rows are NOT there** and can't be recovered from the `.twb`. If a workbook joins/blends a file-based source, **ask the customer for the source file (or a CSV export)** and build the lookup from it. Never fabricate the mapping values.

---

## Hex CLI quirks (confirmed)

- `hex cell create` makes **only** code/sql/markdown cells. Native cells (METRIC/EXPLORE/…) are authored via **YAML export → edit → import** (see `building-cells.md`).
- **Cannot read cell output.** `cell get` returns source; `run status` returns only COMPLETED/ERRORED/timing. Use **COMPLETED-vs-ERRORED as a boolean oracle** to validate SQL, probe schema, and check type-casts (a bogus table → ERRORED confirms the oracle works).
- `project run` / `cell run` are **async** — no `--no-wait`; poll `run status`. `cell update` has no `-t` flag.
- Freshly imported versions have **no outputs** until you `hex project run` — charts render blank until then.
- **No CLI to start the Notebook Agent** (`hex thread` is list/get only).

---

## App layout (optional polish)

App layout **is** settable via CLI: `hex project export <id> -o f.yaml` → edit the `appLayout` block → `hex project import f.yaml`. Import matches by `projectId`/`sourceVersionId` (both DO NOT CHANGE) and updates in place as a new version.

Schema: `appLayout.tabs[].rows[].columns[]`; a column has `start`/`end` (0–120 grid) + `elements[]`; each element = `{type: CELL, cellId, showLabel, showSource, hideOutput, height}`. Use the **export's** cellIds (they differ from `hex cell` API ids). Map cells by **position/order** (stable), not by content-sniffing. **Never put the `.twb` source cell or the raw SQL cells in the `appLayout`** — leave them in the notebook (they're working references), and build the app layout from only the native chart/KPI cells.

> **UI gotcha:** after importing an appLayout, the Hex app view still shows the empty "build an app" onboarding screen — click **"edit app manually"** once to reveal it. The import worked; this is just a UI acknowledgment.
