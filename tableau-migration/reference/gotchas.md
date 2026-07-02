# Gotchas & quirks (parsing rules, Hex CLI, app layout)

Consult these when you hit the relevant step. The parsing rules are correctness landmines — getting them wrong produces silently-wrong numbers, not errors.

---

## Parsing correctness rules

- **Resolve fields by definition, not by caption.** Duplications and renames in Tableau can make a field's caption misleading — resolve each field through its encoding → internal name → underlying formula/column, so you port what it actually computes, not what it's labeled.
- **Sweep ALL filter scopes.** Tableau filters live at four scopes:
  - **worksheet** (`<worksheet>//filter`) — stays **per-chart** (an EXPLORE cell filter); does **not** fork the query.
  - **dashboard**
  - **data-source** (`<datasource>/filter`)
  - **shared / context / workbook** (`workbook/shared-views/shared-view//filter`, often `context=true`).

  Context/workbook + data-source filters apply to **every** sheet on that datasource — push them into the shared query's `WHERE`. Missing a shared-scope filter silently changes totals.
  - *Relative-date / date-range filters:* translate the window deliberately. Relative windows are defined by period offsets that **include the current period**, so an offset can span one more calendar period than the number suggests — work out the actual start/end dates instead of mapping the offset literally, and **sanity-check the resulting totals/row counts** against the source.
- **Preserve field data types in the SQL translation — dates especially.** Keep Tableau date fields as real DATEs end-to-end; don't cast a date to a string (it breaks the chart's date axis). Set the base-axis `dataType: DATE` and carry the pill's granularity as `truncUnit` (`tqr`→`quarter`, `tmn`→`month`, `YEAR()`→`year`), which preserves Hex's date formatting + granularity controls. And **confirm a field's actual type before applying date/number functions** — a field that reads like a date (e.g. a "month" or "period" column) may really be a number or string, so a date function will error or silently mislead.
- **Maps: no native cell.** Build maps as a Python CODE cell (`px.scatter_geo(df, lat=, lon=, color=, size=, projection="natural earth")`), not an EXPLORE scatter of lat/lon.
- **Tooltips are aggregate-only** (measures, not text/dimension values) → Tableau's **detail/LOD text dimension has no clean EXPLORE equivalent**. Note the gap, don't hack around it. Per-row point charts needing text granularity → Python cell.
- **A field may live on a joined table, not the fact table.** A published (`sqlproxy`) datasource can join several physical tables, and a column may belong to any of them. Querying only the primary table for a field that actually lives on a joined table fails with an invalid-identifier error. Resolve each field to its owning table via the datasource's `<relation>`/metadata and reproduce the join on the shared key in your SQL. Newer datasources model this in the logical "relationships" layer with no explicit join clause — infer the key from the shared id column.
- **External file / spreadsheet data sources aren't in the `.twb`.** Lookups loaded from Excel/CSV — region → sales-region maps, quarterly goals, targets (`class='excel-direct'` / `'textscan'` under a `federated` connection) — appear in the XML as **schema + join only; the actual rows are NOT there** and can't be recovered from the `.twb`. If a workbook joins/blends a file-based source, **ask the customer for the source file (or a CSV export)** and build the lookup from it. Never fabricate the mapping values.
- **Don't prune a field that only drives styling.** A dimension used *solely* as an **encoding — color, size, shape, or detail** — can look like an unused dependency and get dropped, which silently kills the visual (e.g. losing the color split). These live **nested under a worksheet's `<encodings>`** (a `<color>`/`<size>`/etc. element pointing at the field), which a shallow tag scan can miss. **Rule of thumb: a field referenced *anywhere* in a worksheet — including its encodings — is in use.** Keep it in the SQL and carry it onto the chart. This matters for styling fidelity → map it per [`building-cells.md`](building-cells.md).

---

## Hex CLI quirks (confirmed)

- `hex cell create` makes **only** code/sql/markdown cells. Native cells (METRIC/EXPLORE/…) are authored via **YAML export → edit → import** (see `building-cells.md`).
- **A project assembled purely in YAML must register its data connection.** `hex cell create --data-connection-id` attaches the connection to the project automatically, but cells authored only in an imported YAML do not — the project's `sharedAssets.dataConnections` stays empty, so every SQL cell references a connection the project doesn't have and the run **ERRORs with no useful CLI detail**. Add the connection under `sharedAssets.dataConnections` before importing. (Tell-tale: SQL that ran in a CLI-created sibling project ERRORs when the same project is built from YAML.)
- **Hex auto-quotes string parameters in SQL Jinja — don't add your own quotes.** A `{{ var }}` referencing a STRING input renders as a *quoted* literal (`'value'`); wrapping it as `'{{ var }}'` produces `''value''`, which the warehouse reads as the literal string `'value'` (quotes included) and matches nothing — the query **COMPLETEs but returns zero rows** (blank charts, no error, so the COMPLETED/ERRORED oracle won't catch it). Reference string params bare (`{{ var }} = 'All'`); numeric params inject unquoted too.
- **Cannot read cell output.** `cell get` returns source; `run status` returns only COMPLETED/ERRORED/timing. Use **COMPLETED-vs-ERRORED as a boolean oracle** to validate SQL, probe schema, and check type-casts (a bogus table → ERRORED confirms the oracle works).
- `project run` / `cell run` are **async** — no `--no-wait`; poll `run status`. `cell update` has no `-t` flag.
- Freshly imported versions have **no outputs** until you `hex project run` — charts render blank until then.
- **No CLI to start the Notebook Agent** (`hex thread` is list/get only).

---

## App layout (optional polish)

App layout **is** settable via CLI: `hex project export <id> -o f.yaml` → edit the `appLayout` block → `hex project import f.yaml`. Import matches by `projectId`/`sourceVersionId` (both DO NOT CHANGE) and updates in place as a new version.

Schema: `appLayout.tabs[].rows[].columns[]`; a column has `start`/`end` (0–120 grid) + `elements[]`; each element = `{type: CELL, cellId, showLabel, showSource, hideOutput, height}`. Use the **export's** cellIds (they differ from `hex cell` API ids). If an `appLayout` element points at a cellId that isn't present in the file, Hex **silently discards the custom layout and falls back to a default that includes every cell** — so the `.twb` reference and raw SQL cells reappear in the app. Build the layout from a fresh export (or generate the cells and the layout together with self-assigned ids so they always match). Map cells by **position/order** (stable), not by content-sniffing. **Never put the `.twb` source cell or the raw SQL cells in the `appLayout`** — leave them in the notebook (they're working references), and build the app layout from only the native chart/KPI cells.

- ⚠️ **Never set a fixed `height` on a chart-type EXPLORE element — leave it `null` (auto).** A small fixed `height` collapses the chart body to near-zero, so the app shows the cell's title with no chart under it (looks "hidden"; dragging it taller in the UI fixes it). METRIC tiles and pivot/table cells tolerate a fixed `height`; **chart-type EXPLOREs do not** — let them auto-size.

### Mirror the source dashboard's layout (polish)
Reproduce the Tableau dashboard's arrangement rather than inventing one. The `.twb` `<dashboard>/<zones>` carry each tile's geometry on a 0–100000 grid (`x`, `y`, `w`, `h`):
- **Rows:** group tiles by shared `y`; order left→right by `x`.
- **Columns:** map each tile's `w` proportionally onto Hex's 0–120 grid — two ~50%-width tiles → `0–60` and `60–120`; a **2×2** grid → two rows of two; a full-width tile → `0–120`.
- **Bands:** keep KPI tiles, filters, and inputs where Tableau placed them (usually a top band); make the hero chart largest.
- **Height:** mirror the *horizontal* structure (rows + column spans) but let chart height **auto-size** (`null`, per the rule above) instead of matching Tableau's pixel heights.

> **UI gotcha:** after importing an appLayout, the Hex app view still shows the empty "build an app" onboarding screen — click **"edit app manually"** once to reveal it. The import worked; this is just a UI acknowledgment.
