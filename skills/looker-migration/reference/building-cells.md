# Building Hex cells (fallback build: coding agent hand-builds native cells)

⚠️ **This is the FALLBACK path, not the default.** Use it **only** when the notebook
agent is unavailable — the headless-agent-threads feature is off, or there are no
Hex credits. The default build is a **Generative app** built by the notebook agent
→ [`build-generative-app.md`](build-generative-app.md). Here *this coding agent*
turns the gated SQL cells into native Hex chart/KPI cells by cloning templates: it
spends the customer's frontier-model tokens and **no Hex credits**, every cell is
deterministic and diff-able — but you're **blind to the rendered result**, so a
human visual-QA gate replaces the automated visual-QA loop
([`visual-qa-loop.md`](visual-qa-loop.md), which only works on a rendered app).

How to turn the gated SQL cells into native cells, and how each **Looker tile type**
maps to a Hex cell. (The SQL shape itself — clustering tiles into shared queries —
is covered in §9 of [`lookml-semantics.md`](lookml-semantics.md).)

What's Looker-specific here is the **tile-type → cell-kind map** and the
**`value_format` → `displayFormat`** carry-through, both below. The templates and
clone-and-override mechanics are just how you build native Hex cells.

> ⚠️ **What EXPLORE/METRIC can and can't aggregate.** A Hex EXPLORE chart cell and
> the METRIC (KPI) cell aggregate **one column** with a single built-in
> aggregation (`Sum, Avg, Count, CountDistinct, Min, Max, Median, StdDev,
> Variance…`). There is **no per-field formula / calculated-measure** in the cell
> spec. So a **ratio of measures** (`SUM(a)/SUM(b)` — a LookML `type: number`
> measure, margin %, conversion rate) or any table calc must be **pre-computed in
> SQL** — a thin companion query grouped to the chart's grain that reads the
> shared dataframe and emits the value as a column (see the ratio rule in
> [`lookml-semantics.md`](lookml-semantics.md) §9). Additive measures
> (Sum/Count/CountDistinct) aggregate fine in EXPLORE straight off the shared cell.

---

## Looker tile type → Hex cell

Read the tile's type from `query.vis_config.type` (the contract's `tileType`) —
**not** `element.type`, which is always `"vis"` for chart tiles / `"text"` for
text tiles.

| Looker `vis_config.type` | Hex cell | Notes |
|---|---|---|
| `single_value` / `looker_single_record` | **METRIC** | KPI tile. Feed a 1-row SQL (METRIC displays, doesn't aggregate — see below). |
| `looker_column` | EXPLORE **bar** (vertical) | default `explore_bar.json` |
| `looker_bar` | EXPLORE **bar** + `orientation: horizontal` | Looker `looker_bar` = **horizontal** bars |
| `looker_line` | EXPLORE **line** | `explore_line.json` |
| `looker_area` | EXPLORE **area** | flip `series[].type` to `area`, or `explore_area.json` |
| `looker_scatter` | EXPLORE **scatter** | two measures → `explore_scatter.json` |
| `looker_pie` / `looker_donut_multiples` | EXPLORE **pie** (donut via `series[].radius`) | `donut_multiples` per-multiple facet → warn or facet |
| `looker_grid` / `table` / `looker_grid` | EXPLORE **pivot-table** / table | `explore_pivot.json`; carry column order + hidden fields (below) |
| `looker_funnel` / `looker_waterfall` / `looker_boxplot` / `looker_timeline` | nearest native + **warn**, or Python | no exact native equivalent |
| `looker_map` / `looker_geo_*` | **Python cell** (`plotly` geo) | no native map cell — see [`lookml-semantics.md`](lookml-semantics.md) §8 |
| `text` | **Markdown/Text cell** | tile `body_text` (markdown) |
| custom / marketplace viz (anything else) | approximate + **warn**, or Python | flag if no faithful equivalent |

**Table column order, labels & hidden fields (for grid/table tiles).**
- **Order** follows the Looker *visualization* order — `vis_config.column_order`
  (captured on the contract element's `vis_config`) — not `query.fields`.
- **Labels** prefer the viz label (`vis_config.series_labels`) over the humanized
  field name.
- **Hidden** columns (`vis_config.hidden_fields`) get `hidden: true` on the Hex
  column **but stay in the query** — a field hidden from the viz is still in
  Looker's result and still sets the grain, so dropping it would silently change
  the numbers. Never *drop* a hidden dimension; hide it.
- ⚠️ **A hidden *table calc* still has to be computed.** `hidden_fields` can name a
  `dynamic_fields` table calculation (e.g. `calculation_1`), not just a column —
  hidden from the viz but often a dependency of a *visible* calc or sort. Translate
  it into the SQL (§7.5 of [`lookml-semantics.md`](lookml-semantics.md)) even though
  it isn't shown; only its display is hidden. (Seen live: `business_pulse`'s "Total
  Sales YoY" hides `calculation_1`.)

---

## Native-cell templates (clone-and-override library)

Real, valid exported cell configs live in `templates/`. **Clone one, override a
few fields, import.** This beats building native cells from the JSON schema
(which fails on hidden required fields like `displayTableConfig`,
`showAllBaseTableDetailFields`).

| File | Cell type | Covers (Looker equivalent) |
|------|-----------|------------------------------|
| `metric.json` | METRIC | `single_value` KPI |
| `explore_bar.json` | EXPLORE (bar) | `looker_column` (vertical), `looker_bar` (set `orientation: horizontal`); **grouped** via `chartConfig.series[].barGrouped=true`, **stacked** = default |
| `explore_line.json` | EXPLORE (line) | `looker_line`; **area** = flip `series[].type` to `area` |
| `explore_faceted.json` | EXPLORE (bar + facet) | small-multiples / `donut_multiples` panels |
| `explore_pivot.json` | EXPLORE (`pivot-table`) | `looker_grid` / `table` / pivoted query (also carries a filter example) |
| `explore_pie.json` | EXPLORE (pie/donut) | `looker_pie`; **donut** via `series[].radius`, data labels via `series[].text.dataLabels` |
| `explore_area.json` | EXPLORE (area) | `looker_area` |
| `explore_scatter.json` | EXPLORE (scatter) | `looker_scatter` (two measures) |

### How to clone-and-override
1. Load the template JSON, assign a **new `cellId`** — import **won't change an existing cell's type**, so native replacements need new ids (then repoint the `appLayout`).
2. Set `config.dataframe` to the upstream SQL cell's output dataframe.
3. Rewrite `config.spec.fields[]`: set each field's `value` to the (UPPERCASE, for Snowflake) column, its `dataType`, `aggregation` (for measures), `truncUnit` (for a DATE axis), and `displayFormat`. ⚠️ **Preserve the seriesId linkage — this is the #1 way a cloned chart silently renders blank.** In a template, every field's `seriesId` equals `chartConfig.series[].id` equals the id in `chartConfig.seriesGroups`. The chart renders from `chartConfig.series`, so if you regenerate the fields' `seriesId` but leave `series[].id`/`seriesGroups` at the template's value (or vice-versa), the series binds to nothing and the chart draws empty/partial — **yet the cell still runs COMPLETED**. Safest: **reuse the template's existing series id** on all fields and leave `chartConfig` alone. If you must regenerate, change all three in lockstep, then assert `{field.seriesId} == {series.id} == {seriesGroups ids}`.
   - Reset template residue: `colorMappings: {}`, `spec.details.fields: []`, `displayTableConfig.columnProperties: []` (else they reference the template's columns), and fix `chartConfig.orientation` / drop `series[].normalize` if the template's differ (e.g. a faceted template ships `normalize: "base-axis"` = 100%-stacked, wrong for a rate chart).
   - ⚠️ **COMPLETED ≠ renders correctly.** The run oracle only proves the query ran; a broken viz spec passes it. Chart correctness is a **human visual-QA gate** — never report a chart "built" on COMPLETED alone. (Numeric correctness you *can* pre-check against Looker — see [`sql-review.md`](sql-review.md) §4a.)
4. For METRIC: it **displays a single value, it does not aggregate.** A METRIC reads one column at one row (`valueColumn` at `valueRowIndex: 0`); `valueAggregate` is **rejected by the import API** (any value 500s with an opaque "unknown API error", though it passes JSON-schema validation). So for a computed KPI (a Looker `single_value` tile), feed it a **1-row SQL**:
   - **Warehouse-scalar query (CLI-friendly — default).** A normal SQL cell, e.g. `SELECT SUM(<col>) AS TOTAL FROM <base>`. `hex cell create --data-connection-id …` mints it directly.
   - **Dataframe-SQL over the shared df** (`dataFrameCell: true`, `dataConnectionId: null`, `SELECT SUM(<col>) AS TOTAL FROM <shared_df>`) reuses the consolidated cell — **but `hex cell create` CANNOT mint this** (it ERRORs); author it in YAML.

   Then set the METRIC's `valueVariableName` = that 1-row dataframe, `valueColumn` = its column, `valueRowIndex: 0`, `valueAggregate: null`, + `displayFormat`.
5. Put the cell in `cells[]`, add a matching `appLayout` element, import, then `hex project run`.
6. **Validate against the Hex file-format JSON Schema before importing — necessary, not sufficient.**
   - **Live, while editing (recommended):** name the working file `*.hex.yaml` and install the **[RedHat YAML extension](https://marketplace.visualstudio.com/items?itemName=redhat.vscode-yaml)**; it auto-loads the schema from **[SchemaStore](https://www.schemastore.org/)** for real-time validation + autocomplete + hover docs.
   - **CLI / CI:** validate against `https://static.hex.site/hex-file-schema.json` (fetch at run time; don't vendor a copy that drifts).
   - **Necessary, not sufficient:** a spec can pass schema validation and still be rejected by the import API (e.g. METRIC `valueAggregate`). If `hex project import` returns "unknown API error", bisect: import the base export (round-trips clean), then add cells back one at a time.

### Feature references (how to mirror Looker)
- **Date axis → a DATE column at a grain, NEVER a numeric proxy.** A Looker `dimension_group` timeframe field (`orders.created_month`) is a **date at a grain**. Bind the Hex axis to the real DATE/TIMESTAMP column with `dataType: DATE` and carry the grain as `truncUnit` (`_week`→`week`, `_month`→`month`, `_quarter`→`quarter`, `_year`→`year`, `_date`→`day`).
  - ⚠️ **The trap:** don't bind a numeric column whose *name* matches the grain (a pre-bucketed `MONTH_NUM`, a `..._period` integer) to a date axis — it renders a number line, not a time axis, and Hex's date-granularity controls break. **Confirm the field's real warehouse type** (`SELECT YEAR(<col>)` probe — see [`gotchas.md`](gotchas.md)); use the true DATE column at the timeframe's grain.
- **Faceting → small-multiples / `donut_multiples`:** a `config.spec.fields[]` field with `channel: "h-facet"` or `"v-facet"`, `fieldType: "COLUMN"`.
- **Per-cell filters → tile `query.filters`:** shape `{"column": ..., "fieldType": "COLUMN", "predicate": {"op": "IS_ONE_OF", "arg": [...]}, "queryPath": [], "columnType": "STRING"}`. Chart cells: `config.spec.filters`. Pivot/table cells: `config.displayTableConfig.filters`. (Explore-level / mandatory filters go into the SQL `WHERE` instead — see [`lookml-semantics.md`](lookml-semantics.md) §6.)
- **Pivot / crosstab → a pivoted Looker query (`query.pivots`):** `config.spec.visualizationType: "pivot-table"` with `row`/`column`/`value` channel fields (the pivot dimension → `column`).
- **Color split → a Looker pivot or a `dimension` on the series:** a field on the `color` channel. Don't drop a dimension that only drives color — it's still in use.
- **Valid EXPLORE channels:** `base-axis, cross-axis, color, opacity, tooltip, h-facet, v-facet, row, column, value, source, destination`. There is **no `detail` channel**.

---

## Dashboard objects beyond chart tiles

A Looker dashboard also holds non-chart tiles — handle them, don't silently drop.

| Looker tile | Hex |
|---|---|
| **Text tile** (`type: text`, `body_text` markdown) | **Markdown/Text cell** — port the markdown. |
| **Button / link tile** | No clean equivalent — flag for manual app setup. |
| **Image in a text tile** (markdown `![](url)`) | Hex renders images in a Markdown cell via **file upload (drag-drop)**, *not* by URL. Download the image, add it to the cell, place the cell in `appLayout`. |
| **`note_text` / `subtitle_text`** on a tile | No spec slot — concatenate into the chart title or add an adjacent text cell. |
| **Filter tiles / dashboard filters** | → input-parameter cells (see [`lookml-semantics.md`](lookml-semantics.md) §7); default values with explore scope go into the SQL `WHERE`. |

---

## Styling — what maps from Looker

Styling lives in `config.spec.chartConfig` (data labels `series[].text.dataLabels`, donut `series[].radius`, legend `settings.legend.position`, colors via `colorMappings`). Split it — don't try 1:1:

| Styling | In the Looker tile? | Map it? |
|---------|----------------|---------|
| Chart type, stacking | `vis_config.type` / `stacking` | **Yes** |
| **Colors / palette** (per series) | `vis_config.series_colors` / `color_application` | **Yes, high value** → `colorMappings` |
| **Number/date formats** ($, %, decimals) | LookML measure `value_format_name` / `value_format`; tile `vis_config` overrides | **Yes, high value** → `displayFormat` (see below) |
| **Data labels** (show/hide) | `vis_config.show_value_labels` / `value_labels` | **Yes** → `series[].text.dataLabels` |
| Axis titles, legend on/off | `vis_config.*_axis` / `hide_legend` | Best-effort |
| Fonts, exact spacing, conditional cell colors | partial / no clean source | Hex default / manual polish |

**Number formats carry through — high value.** A LookML measure's
`value_format_name` (`usd`, `usd_0`, `percent_0/1/2`, `decimal_0/1/2`, …) or a
custom `value_format` mask becomes the Hex column `displayFormat` on the tile's
value / KPI value / chart measure. So a `usd` measure renders `$110,342.75` and a
`percent_1` measure renders `12.3%` — not bare numbers. Read the measure's format
from the view LookML (or `looker_fetch.py explore` output) and attach it; counts
and dimensions get no format (raw). Without this, the side-by-side render shows
bare numbers where Looker showed `$`/`%`.

Bottom line: map **chart type, colors, number formats, and data-labels-on/off** —
those drive most of the visual fidelity. Leave cosmetic-only knobs as sensible Hex
defaults.
