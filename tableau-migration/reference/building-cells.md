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
3. Rewrite `config.spec.fields[]`: set each field's `value` to the (UPPERCASE Snowflake) column, its `title`, `dataType`, and shared `seriesId`; set `displayFormat`.
4. For METRIC: set `valueVariableName` (dataframe) + `valueColumn` + `displayFormat`.
5. Put the cell in `cells[]`, add a matching `appLayout` element, import, then `hex project run`.
6. Validate against `reference/hex-file-schema.json` (or `https://static.hex.site/hex-file-schema.json`) before importing.

### Feature references (how to mirror Tableau)
- **Faceting → small-multiples/trellis:** a `config.spec.fields[]` field with `channel: "h-facet"` or `"v-facet"`, `fieldType: "COLUMN"` — use for Tableau worksheets that put a dimension on Rows/Columns to create panels.
- **Per-cell filters → Tableau worksheet filters:** shape `{"column": ..., "fieldType": "COLUMN", "predicate": {"op": "IS_ONE_OF", "arg": [...]}, "queryPath": [], "columnType": "STRING"}`. Chart cells: `config.spec.filters`. Pivot/table cells: `config.displayTableConfig.filters`. (Workbook/context filters go into the SQL `WHERE` instead.)
- **Pivot / crosstab → Tableau text table:** `config.spec.visualizationType: "pivot-table"` with `row`/`column`/`value` channel fields.
- **Valid EXPLORE channels:** `base-axis, cross-axis, color, opacity, tooltip, h-facet, v-facet, row, column, value, source, destination`. There is **no `detail` channel**.

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
