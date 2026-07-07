# Building Hex cells (Phase 2: SQL → native chart cells)

How to turn the Phase-1 SQL cells into native Hex chart/KPI cells by cloning
templates. (The SQL shape itself — clustering worksheets into shared queries —
is a Phase-1 concern; see the "Consolidate into shared SQL cells" section in
[`tableau-semantics.md`](tableau-semantics.md).)

> ⚠️ **What EXPLORE/METRIC can and can't aggregate.** A Hex EXPLORE chart cell
> and the METRIC (KPI) cell aggregate **one column** with a single built-in
> aggregation (`Sum, Avg, Count, CountDistinct, Min, Max, Median, StdDev,
> Variance…`). There is **no per-field formula / calculated-measure** in the cell
> spec. So a **ratio of aggregates** (`SUM(a)/SUM(b)` — margin %, return rate) or
> any derived measure must be **pre-computed in SQL** — a thin companion query
> grouped to the chart's grain that reads the shared dataframe and emits the ratio
> as a column, which the chart then plots (see the "keep separate when" ratio rule
> in `tableau-semantics.md`). The higher-fidelity alternative is a semantic-model
> MEASURE. Additive measures (Sum/Count/CountDistinct) aggregate fine in EXPLORE
> straight off the shared cell.

---

## Native-cell templates (clone-and-override library)

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

### How to clone-and-override
1. Load the template JSON, assign a **new `cellId`** — import **won't change an existing cell's type**, so native replacements need new ids (then repoint the `appLayout`).
2. Set `config.dataframe` to the upstream SQL cell's output dataframe.
3. Rewrite `config.spec.fields[]`: set each field's `value` to the (UPPERCASE Snowflake) column, its `dataType`, `aggregation` (for measures), `truncUnit` (for a DATE axis), and `displayFormat`. ⚠️ **Preserve the seriesId linkage — this is the #1 way a cloned chart silently renders blank.** In a template, every field's `seriesId` equals `chartConfig.series[].id` equals the id in `chartConfig.seriesGroups`. The chart renders from `chartConfig.series`, so if you regenerate the fields' `seriesId` but leave `series[].id`/`seriesGroups` at the template's value (or vice-versa), the series binds to nothing and the chart draws empty/partial — **yet the cell still runs COMPLETED** (the query is fine; only the viz is broken). Safest: **reuse the template's existing series id** on all fields and leave `chartConfig` alone. If you must regenerate, change all three in lockstep. After building, assert `{field.seriesId} == {series.id} == {seriesGroups ids}`.
   - Also reset template residue to your data: `colorMappings: {}`, `spec.details.fields: []`, `displayTableConfig.columnProperties: []` (else they reference the template's columns), and fix `chartConfig.orientation` / drop `series[].normalize` if the template's differ from what you want (e.g. a faceted template ships `normalize: "base-axis"` = 100%-stacked, wrong for a rate chart).
   - ⚠️ **COMPLETED ≠ renders correctly.** The run-status oracle only proves the query ran; a broken viz spec (seriesId linkage, wrong channel, bad displayFormat) passes it. Chart correctness is a **human visual-QA gate** — never report a chart "built" on COMPLETED alone.
4. For METRIC: it **displays a single value, it does not aggregate.** A METRIC reads one column at one row (`valueColumn` at `valueRowIndex: 0`); `valueAggregate` is **rejected by the import API** (any value — `"SUM"`, `"Sum"` — 500s with an opaque "unknown API error", though it passes JSON-schema validation). So for a computed KPI, feed it a **1-row SQL** and point the METRIC at that: add a small dataframe-SQL cell (`dataFrameCell: true`, `dataConnectionId: null`, e.g. `SELECT SUM(<col>) AS TOTAL FROM <shared_df>`) that pre-aggregates, then set the METRIC's `valueVariableName` = that 1-row dataframe, `valueColumn` = its column, `valueRowIndex: 0`, `valueAggregate: null`, + `displayFormat`. (This is the same companion-SQL move as ratio charts, and why the template ships `valueRowIndex: 0`.)
5. Put the cell in `cells[]`, add a matching `appLayout` element, import, then `hex project run`.
6. **Validate against the Hex file-format JSON Schema before importing — but know it's necessary, not sufficient.**
   - **Live, while editing (recommended):** name the working file `*.hex.yaml` and install the **[RedHat YAML extension](https://marketplace.visualstudio.com/items?itemName=redhat.vscode-yaml)**; it auto-loads the schema from **[SchemaStore](https://www.schemastore.org/)** (filename-based detection) for real-time validation, key/value autocomplete, and hover docs on every field — the fastest way to author correct YAML and understand the format. (Setup is a prerequisite in `SKILL.md`.)
   - **CLI / CI:** validate against the vendored `reference/hex-file-schema.json` (or `https://static.hex.site/hex-file-schema.json`).
   - **Necessary, not sufficient:** a spec can pass schema validation and still be rejected by the import API (e.g. METRIC `valueAggregate`). If `hex project import` returns "unknown API error", bisect: import the base export (round-trips clean), then add cells back one at a time to isolate the offending cell.

### Feature references (how to mirror Tableau)
- **Faceting → small-multiples/trellis:** a `config.spec.fields[]` field with `channel: "h-facet"` or `"v-facet"`, `fieldType: "COLUMN"` — use for Tableau worksheets that put a dimension on Rows/Columns to create panels.
- **Per-cell filters → Tableau worksheet filters:** shape `{"column": ..., "fieldType": "COLUMN", "predicate": {"op": "IS_ONE_OF", "arg": [...]}, "queryPath": [], "columnType": "STRING"}`. Chart cells: `config.spec.filters`. Pivot/table cells: `config.displayTableConfig.filters`. (Workbook/context filters go into the SQL `WHERE` instead.)
- **Pivot / crosstab → Tableau text table:** `config.spec.visualizationType: "pivot-table"` with `row`/`column`/`value` channel fields.
- **Valid EXPLORE channels:** `base-axis, cross-axis, color, opacity, tooltip, h-facet, v-facet, row, column, value, source, destination`. There is **no `detail` channel**.

---

## Dashboard objects beyond worksheets

A Tableau dashboard also holds non-worksheet **objects** (`<zone type-v2='…'>`) — images, text, web-page embeds, buttons, spacers. Worksheets become native chart cells (above); handle the objects too, don't silently drop them.

| Tableau object (`type-v2`) | Hex |
|---|---|
| **Image** (`bitmap`; `image-file-url` or embedded asset) | Hex renders images in a **Markdown/Text cell via file upload (drag-drop)** — *not* by URL. Download the image (from `image-file-url`, or extract the embedded asset from the `.twbx`/repository), add it to a markdown cell, and place that cell in the `appLayout`. |
| **Text** (`text`) | **Markdown/Text cell** — port the formatted text to markdown. |
| **Web page / URL embed / iframe** (`web`) | ⚠️ **No native equivalent.** Hex text cells don't accept raw HTML/iframes, and Hex's own embedding runs the other way (Hex → other tools, not external sites → Hex). Try a **Python cell** (`from IPython.display import IFrame; IFrame(url, w, h)`); if Hex sanitizes it, **flag as a gap** (same bucket as maps). |
| **Button** (navigation) | No clean equivalent — flag for manual app setup. |
| **Blank** (spacer) | Layout only — reproduce with `appLayout` spacing, no cell. |
| Legend / **filter** card / **paramctrl** / **title** | Legend rides on the chart; filter/param cards → input-parameter cells (see `tableau-semantics.md`); title → the page title header. |

Confirmed against Hex docs: images are **upload-only** in text cells; **HTML/iframe is unsupported**. So **image + text objects port cleanly; web-page/iframe embeds are a known gap** — call them out in the pilot.

---

## Styling — what maps from Tableau

Styling lives in `config.spec.chartConfig` (data labels `series[].text.dataLabels`, donut `series[].radius`, legend `settings.legend.position`, colors via `colorMappings`). Split it — don't try 1:1:

> The field a color/size split rides on lives in the worksheet's `<encodings>`. Make sure your parse actually kept it — a dimension that appears *only* as an encoding is still in use; don't drop it as a dead column (see `gotchas.md`).

| Styling | In the `.twb`? | Map it? |
|---------|----------------|---------|
| Chart type, stacking, dual-axis | Yes | **Yes** |
| **Colors / palette** (per member) | Yes (color encodings) | **Yes, high value** → `colorMappings` |
| **Number/date formats** ($, %, decimals) | Yes (field/axis `<format>`) | **Yes, high value** → `displayFormat` |
| **Data labels** (show/hide + field) | Yes (mark Label shelf) | **Yes** → `series[].text.dataLabels` |
| Axis titles, legend on/off | Partial | Best-effort |
| Donut hole, label position, fonts | **No Tableau source** | **No** — Hex default / manual polish |

Bottom line: map **chart type, colors, number formats, and data-labels-on/off** from the XML — those drive most of the visual fidelity. Leave cosmetic-only knobs as sensible Hex defaults.
