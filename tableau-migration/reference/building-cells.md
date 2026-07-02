# Building Hex cells (SQL strategy + native chart cells)

How to turn a parsed Tableau workbook into Hex cells: first decide the SQL shape (consolidate), then build the chart/KPI cells by cloning templates.

---

## SQL consolidation — one query feeds many charts

**Mental model:** In Tableau, a dashboard's worksheets almost all sit on **one data source**; each worksheet is just a different viz + shelves + worksheet filter over the same rows. Hex mirrors this: **one SQL cell = the "data source"**, and many EXPLORE/METRIC cells read that same dataframe. Because **EXPLORE aggregates and filters over its input dataframe**, you do *not* need a pre-aggregated SQL per chart. One-SQL-per-chart is the anti-pattern — it duplicates logic, bloats the project, and drifts out of sync when a calc changes.

**Cluster worksheets into shared queries (do this in planning).** Group worksheets that share ALL of:
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

**Make it reviewable:** in the plan/manifest, record the `sql_cell → [charts]` mapping. Target: the **fewest SQL cells that don't force an incompatible grain** — usually 1–3 per dashboard, not one per worksheet.

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

| Styling | In the `.twb`? | Map it? |
|---------|----------------|---------|
| Chart type, stacking, dual-axis | Yes | **Yes** |
| **Colors / palette** (per member) | Yes (color encodings) | **Yes, high value** → `colorMappings` |
| **Number/date formats** ($, %, decimals) | Yes (field/axis `<format>`) | **Yes, high value** → `displayFormat` |
| **Data labels** (show/hide + field) | Yes (mark Label shelf) | **Yes** → `series[].text.dataLabels` |
| Axis titles, legend on/off | Partial | Best-effort |
| Donut hole, label position, fonts | **No Tableau source** | **No** — Hex default / manual polish |

Bottom line: map **chart type, colors, number formats, and data-labels-on/off** from the XML — those drive most of the visual fidelity. Leave cosmetic-only knobs as sensible Hex defaults.
