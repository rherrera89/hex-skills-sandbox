# Tableau semantics → Hex (Phase 1: code conversion)

The reference for **Phase 1** of a migration — translating a Tableau workbook's
calc logic into warehouse SQL (or Python for the genuine gaps). Phase 2
(SQL → native Hex chart/KPI cells) lives in `building-cells.md`.

The value here is the **Tableau side**: what each construct *means* and the
handful of behaviors that are easy to get subtly wrong. The SQL side is whatever
dialect your resolved Hex connection speaks — this doc does **not** enumerate
every 1:1 function rename (see "Dialect" below).

## How to use

1. **Resolve the connection's warehouse** (`connection-mapping.md`) — Snowflake,
   BigQuery, Redshift, Databricks, Postgres, DuckDB, etc.
2. **Load that warehouse's SQL reference (mandatory — do not skip).** Before
   translating, pull up the dialect's function docs and confirm the syntax for
   the constructs this workbook actually uses. See "Dialect step" below for what
   to verify and the doc links.
3. Sweep the `.twb` for calcs, LOD, table calcs, filters, parameters, sets (see
   `gotchas.md` for the filter-scope + field-name sweep).
4. Translate each with the rules below, targeting the **resolved dialect** (the
   SQL examples here are Snowflake — *illustrative*; re-emit for the real
   warehouse using the docs from step 2).
5. Consolidate into as few SQL cells as the clusters allow (§9 below) — don't
   fork a query per calc.
6. Sanity-check totals against the source's rendered numbers (parity). For
   warehouse-backed workbooks parity is **exact**, not "drift" — a gap is a bug.

## Dialect step: check the warehouse's docs before translating

Hex customers run on every mainstream cloud warehouse, and the SQL is **not**
portable — function names, date/time semantics, format tokens, and even whether
a keyword like `QUALIFY` exists all vary. **Never assume Snowflake.** This is an
explicit step, not a footnote.

**After resolving the connection, open the warehouse's function reference and
verify the syntax for what this workbook uses.** When unsure, actually fetch/
search the docs (the agent has WebFetch/WebSearch) rather than guessing a
function name — a wrong name fails loudly, but a wrong *semantic* (Monday vs
Sunday week, ASC vs DESC rank) fails silently as a parity gap.

| Warehouse | Function reference |
|---|---|
| Snowflake | https://docs.snowflake.com/en/sql-reference-functions |
| BigQuery | https://cloud.google.com/bigquery/docs/reference/standard-sql/functions-and-operators |
| Amazon Redshift | https://docs.aws.amazon.com/redshift/latest/dg/c_SQL_functions.html |
| Databricks SQL | https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-functions.html |
| PostgreSQL | https://www.postgresql.org/docs/current/functions.html |
| DuckDB | https://duckdb.org/docs/sql/functions/overview |

Most scalar functions (logical, string, math, date, aggregate, regex) are a
**direct 1:1 rename** in every warehouse — translate those and move on; the
sections below cover only the constructs with real subtlety.

### What actually varies per warehouse — confirm each against the docs

- **`QUALIFY`** (for Top-N / dedup): Snowflake, BigQuery, Databricks yes;
  Postgres, Redshift **no** → use a ranked subquery filtered in an outer `WHERE`.
- **Week start / `DATE_TRUNC('week', …)`**: some anchor Monday, some Sunday, some
  are configurable — and Tableau is Sunday. Confirm and adjust (see §2).
- **Date-part / truncation unit names** (`'week'` vs `'iso_week'`, `'dow'` vs
  `'dayofweek'`) and whether weekday is 0- or 1-based, Sunday- or Monday-first.
- **Date parsing tokens**: `TO_DATE`/`PARSE_DATE`/`STR_TO_DATE` differ in name,
  arg order, and format-token grammar (`YYYY` vs `yyyy` vs `%Y`).
- **Conditional shorthand**: `IFF`/`IF`/`IIF` exist on some, not others — `CASE`
  is the portable fallback.
- **Regex function names**: `REGEXP_SUBSTR` vs `REGEXP_EXTRACT` vs `regexp_*`.
- **Percentile / median syntax**: `PERCENTILE_CONT(p) WITHIN GROUP (ORDER BY x)`
  vs `PERCENTILE_CONT(x, p)` vs `APPROX_QUANTILES`.
- **String indexing base** and `SUBSTR`/`SUBSTRING` naming.
- **Boolean type**: native `BOOLEAN` vs integer 0/1 (affects set/flag columns).
- **Identifier quoting + case-folding**: `"..."` vs backticks; upper- vs
  lower-fold of unquoted names.

---

## 1. Conditional / null (the non-obvious few)

Everything else (`IF/ELSEIF/ELSE`, `CASE WHEN`) is a straight `CASE` rewrite.

| Tableau | SQL | Note |
|---|---|---|
| `IIF(c,t,f)` | `IFF(c,t,f)` / `CASE WHEN c THEN t ELSE f END` | some dialects lack `IFF` — fall back to `CASE` |
| `ZN(x)` | `COALESCE(x, 0)` | Tableau `ZN` = "zero if null" |
| `ATTR(x)` | `x` | drop the wrapper — it's a Tableau viz-safety guard, no SQL meaning |
| set membership `[x] IN [set]` | `x IN (…)` or `CASE` | expand the set's members |

## 2. Dates (direct except these)

`DATEPART/DATETRUNC/DATEADD/DATEDIFF/DATENAME/MAKEDATE/TODAY/NOW` all have
same-shaped equivalents (`DATE_PART`, `DATE_TRUNC`, `DATEADD`, `DATEDIFF`,
`MONTHNAME`, …). The traps:

- 🔸 **Week anchoring.** Tableau truncates weeks **Sunday-anchored**; most
  warehouses (`DATE_TRUNC('week', …)`) anchor **Monday**. Left unadjusted, every
  weekly bucket shifts by a day and parity fails. Adjust the trunc (e.g. shift by
  the weekday offset) to match Tableau's Sunday start.
- 🔸 **`DATEPARSE(fmt, str)`** → warehouse `TO_DATE`/`TO_TIMESTAMP` reverses the
  arg order (`TO_DATE(str, fmt)`) **and** uses different format tokens (Tableau's
  Java-style `yyyy-MM-dd` vs warehouse `YYYY-MM-DD`). Translate the tokens; verify.
- 🔸 **ISOYEAR / ISO-week.** Tableau's ISO year uses the Thursday-shift rule
  (`DATE_PART('yearofweekiso', …)` in Snowflake), which disagrees with plain
  `YEAR()` at year boundaries. Don't map ISO calcs to `YEAR`.
- **Relative-date filters** (last N years/months): translate the window
  deliberately and sanity-check the total. Tableau counts the current period,
  so "last 1 year" can mean the current + prior year — an off-by-one here
  produces a large, silent value gap. See `gotchas.md`.

## 3. LOD expressions → window functions (default)

**Default form = `OVER (PARTITION BY …)`** — it keeps the consolidated SQL as one
flat result set (no extra CTEs/joins per calc), which fits the
one-SQL-feeds-many-charts model.

| Tableau | SQL |
|---|---|
| `{FIXED [d]: SUM([x])}` | `SUM([x]) OVER (PARTITION BY [d])` |
| `{FIXED [d1],[d2]: AVG([x])}` | `AVG([x]) OVER (PARTITION BY [d1], [d2])` |
| `{INCLUDE [d]: SUM([x])}` | partition by the **viz dims + [d]** |
| `{EXCLUDE [d]: SUM([x])}` | partition by the **viz dims minus [d]** |

**Drop to a CTE (`GROUP BY [d]` joined back) only when:**
- the LOD is **nested** (`AVG({FIXED …: COUNT(…)})`) — build innermost grouping
  first as a CTE, then aggregate its output in the next CTE; or
- the outer aggregate must read a **coarser grain** than the base rows (a
  row-weighted average over base rows is wrong — group first, then aggregate).

⚠️ A `{FIXED}` used with **no worksheet context** (not on any shelf) has no viz
dims to partition by — carry the calc onto the sheet that uses it, or flag it.

## 4. Window / table calcs → SQL `OVER()` (resolve in Phase 1)

Table calcs **must** be computed in the SQL cell — Hex's native EXPLORE/METRIC
cells aggregate and filter but do **not** do window math. Never defer these to
Phase 2.

| Tableau | SQL |
|---|---|
| `RUNNING_SUM(SUM(x))` | `SUM(SUM(x)) OVER (ORDER BY <addr>)` |
| `RUNNING_AVG/MIN/MAX(SUM(x))` | `AVG/MIN/MAX(SUM(x)) OVER (ORDER BY <addr>)` |
| `WINDOW_AVG(SUM(x), -n, 0)` | `AVG(SUM(x)) OVER (ORDER BY <addr> ROWS BETWEEN n PRECEDING AND CURRENT ROW)` |
| `WINDOW_SUM(SUM(x))` unbounded | `SUM(SUM(x)) OVER (PARTITION BY <part>)` |
| `SUM(x) / WINDOW_SUM(SUM(x))` | `SUM(x) / SUM(SUM(x)) OVER (PARTITION BY <part>)` (share of total) |
| `RUNNING_SUM(SUM(x)) / TOTAL(SUM(x))` | pareto: `SUM(SUM(x)) OVER (ORDER BY <addr>) / SUM(SUM(x)) OVER ()` |
| `RANK(SUM(x))` | `RANK() OVER (ORDER BY SUM(x) DESC)` |
| `RANK_DENSE` / `RANK_UNIQUE` | `DENSE_RANK()` / `ROW_NUMBER()` |
| `INDEX()` | `ROW_NUMBER() OVER (ORDER BY <addr>)` |
| `LOOKUP(agg, -n)` | `LAG(agg, n) OVER (ORDER BY <addr>)` |
| `LOOKUP(agg, n)` | `LEAD(agg, n) OVER (…)` |
| `(ZN(SUM(x)) - LOOKUP(SUM(x),-1)) / ABS(LOOKUP(SUM(x),-1))` | period-over-period %: `(COALESCE(SUM(x),0) - LAG(SUM(x),1) OVER(…)) / ABS(LAG(SUM(x),1) OVER(…))` |

**Addressing = the fiddly part.** Tableau's "compute using" sets the window's
`PARTITION BY` + `ORDER BY`:
- **`ORDER BY <addr>`** = the addressing dimension (usually the viz's axis dim);
  carry Tableau's `<computed-sort>` ("sort dim X by measure Y") into it.
- **`PARTITION BY <part>`** = the partitioning dimension (usually the color/pane
  dim). Default "Table (Across)" = order by the axis dim, no partition.

**Dialect-independent facts to preserve:**
- 🔸 `RANK()` defaults to **DESC** in Tableau (SQL defaults ASC — always emit the
  explicit direction).
- 🔸 `LOOKUP(agg, -1)` is the **previous** row → `LAG(agg, 1)`; positive → `LEAD`.
- 🔸 Unbounded `WINDOW_MAX/MIN/SUM` is **constant per partition** — no `ORDER BY`;
  don't `SUM` a partition constant (it multiplies by row count).
- Week dims: Sunday-anchored (see §2).

**Flag for manual review (no clean auto-mapping):** restart-every /
pane-relative addressing, multi-dimension partitions beyond a single split,
`WINDOW_MEDIAN/PERCENTILE/CORR/VAR/STDEVP`, `PREVIOUS_VALUE`, `SIZE`,
`FIRST`/`LAST` (except as a "latest row" filter → `QUALIFY ROW_NUMBER() … = 1`),
and any table calc embedded inside a larger expression.

## 5. Parameters, sets, bins

- 🔸 **Parameter → Hex input cell.** Create an input cell mirroring the
  parameter's domain and default (range→number/slider, list→dropdown,
  boolean→toggle, date→date input), then reference it in the shared SQL via Jinja
  `{{ param_name }}`. Find the parameter's **usages** (calcs / filters / CASE
  swaps) and wire the variable into each. A measure-switcher parameter becomes a
  `CASE {{ param }} WHEN … END` in the shared SQL that swaps which measure is
  selected — one control drives every chart on that SQL.
  - ⚠️ **Do NOT wrap the Jinja tag in quotes.** Hex substitutes `{{ param }}`
    with a properly-typed value — including quoting strings for you. Writing
    `'{{ param }}'` makes the tag a literal string (`WHERE region = '{{ param }}'`
    is read as the text `{{ param }}`, not the value). Use `WHERE region =
    {{ param }}` and let Hex handle the typing/quoting.
  - ⚠️ **Place the input cell UPSTREAM of the SQL that uses it.** Hex runs cells
    as a dependency graph, so an input parameter must come **before** every cell
    that references its `{{ var }}` — the consuming cells are downstream. Put
    input cells at the top (above the shared SQL); an input placed after its
    consumer leaves the variable unresolved and the run errors. See `gotchas.md`.
- **Bins** → `FLOOR(x / size) * size`. Note `BinFixed`'s bin **index** is
  **1-based** (`FLOOR(x/size) + 1`) if the workbook uses the index rather than
  the bucket floor.
- **Member / condition set** → a boolean column (`CASE WHEN … THEN TRUE …`).
- **Top-N set / `RANK(…) <= N`** → `QUALIFY ROW_NUMBER() OVER (ORDER BY m DESC)
  <= N` where the dialect supports `QUALIFY` (Snowflake, BigQuery, Databricks);
  else a ranked subquery filtered in an outer `WHERE`.
- **Parameter-driven Top-N** → the same, with `<= {{ n_param }}`.

## 6. Data model (joins, relationships, blends, custom SQL)

- **Physical joins / relationships ("noodles")** → SQL `FROM … JOIN …` on the
  keys. Preserve cardinality (default many-to-one). Physical table names live in
  the **published datasource** (`.tds`/`.tdsx`), not always the `.twb` — see
  `gotchas.md`.
- **Data blend** (`<datasource-relationships>`) → a `JOIN` on the linking
  field(s) when both sides are warehouse-reachable; if the secondary isn't,
  materialize it (a Python/CSV load) and join. Non-additive looked-up measures
  need care (don't double-count across the join grain).
- **Custom SQL** (`relation type='text'`) → use it as (or fold it into) the
  cluster's SQL, repointed at the resolved connection.

## 7. RLS / security — detect + flag only (v1)

Detect row/column security and **report it for manual recreation** — don't
auto-apply in v1.

| Tableau | Report as |
|---|---|
| `USERNAME()` | current-user identity → warehouse `CURRENT_USER()` / Hex user context; recreate as a Hex/warehouse-side row filter |
| `ISMEMBEROF('group')` | group membership check — needs the group provisioned |
| `USERATTRIBUTE('attr')` | user-attribute lookup — needs the attribute provisioned |

Surface these in the migration notes with the identity calc they gate, so the
customer can rebuild the policy deliberately.

## 8. Gaps → Python cell (or flag)

Hex has no native map cell, and some Tableau constructs have no clean SQL
equivalent. Build these as a **Python code cell** (or flag if out of scope):

- **Maps** → `plotly.express.scatter_geo/choropleth` (never approximate with an
  EXPLORE scatter of lat/lon).
- **Per-row / LOD detail text** that can't be expressed as an aggregate.
- **Non-warehouse sources** (Google Sheets, spatial/OGR, web data, Mapbox) and
  **`.hyper` extract-only fields** — can't repoint to the warehouse; load via
  Python or note as skipped.

## 9. Consolidate into shared SQL cells — one query feeds many charts

Once each construct is translated, decide the **SQL cell shape**. Don't emit one
SQL per chart — that's the anti-pattern (duplicated logic, bloat, drift when a
calc changes).

**Mental model:** a Tableau dashboard's worksheets almost all sit on **one data
source**; each worksheet is just a different viz + shelves + worksheet filter
over the same rows. Hex mirrors it: **one SQL cell = the "data source"**, and
many native cells read that same dataframe. Because Hex's EXPLORE cells
**aggregate and filter over their input dataframe** (Phase 2), you don't need a
pre-aggregated SQL per chart.

**Cluster worksheets into shared queries (do this in planning).** Group
worksheets that share ALL of:
- the same **base table(s) + join shape**,
- the same **data-source + context/workbook filters** (they apply to every sheet
  on the datasource anyway — put them in the shared `WHERE`),
- a **compatible grain** — build the SQL at the **finest grain any chart in the
  group needs** (plus its date/id keys); each chart rolls up from there.

Then emit **one SQL cell per cluster**, selecting the **union of every column +
measure** the cluster's charts reference. Add shared calculated columns **once**
in that query — never fork a query just to add a column.

**Build only what's *used*.** Select/translate only the fields and calcs a
migrated worksheet actually references. A data source usually defines many calc
fields, measures, and tables that **no** migrated worksheet places on a shelf —
don't build those into the dashboard SQL. Carry unused-but-valuable metrics to
the **data-source guide / semantic layer** instead (see `datasource-guide.md`),
where they power self-serve Q&A without bloating the dashboard queries.

**Keep queries separate when:**
- **different base table or join shape** — no shared grain to stand on;
- one chart needs **row-level detail** while another needs a heavy
  pre-aggregation — sharing would force a huge detail dataframe;
- a chart carries a **data-source-level** filter the others don't (worksheet-level
  filters do *not* force a split — they live on the Phase-2 cell);
- a **scalar KPI** off an unrelated aggregation — a tiny dedicated query is
  cheaper than rolling it out of a wide df;
- a **ratio-of-aggregates / non-additive measure** (margin %, return rate,
  conversion rate). A Hex EXPLORE/METRIC aggregates a **single column** with one
  built-in aggregation — it **cannot** compute `SUM(a)/SUM(b)`. Emit a thin
  **companion grouped SQL that reads the shared dataframe** and pre-computes the
  ratio: `SELECT dim, SUM(a)/SUM(b) AS ratio FROM {{shared_df}} GROUP BY dim`;
  the chart then plots the `ratio` column directly. Because it *reads* the
  consolidated cell, it doesn't fork the base query — consolidation holds.
  (Higher-fidelity alternative: define the ratio as a semantic-model MEASURE.)

**Make it reviewable:** record the `sql_cell → [charts]` mapping in the
plan/manifest. Target the **fewest SQL cells that don't force an incompatible
grain** — usually 1–3 per dashboard, not one per worksheet.

## Status legend (how to record each translation)

| | Meaning |
|---|---|
| ✅ **SQL** | Auto-translated into the cluster SQL. |
| 🔸 **Verify** | Translated but flagged (arg-order / week-anchor / off-by-one / dialect gap) — sanity-check the total. |
| 🐍 **Python** | No SQL equivalent — build as a Python cell (map, per-row detail, non-warehouse source). |
| ⚠️ **Manual** | No faithful equivalent — flag for the customer to recreate (exotic table calcs, RLS policy, extract-only fields). |

Record each worksheet's calcs + their status in the migration plan/manifest so
the parity gate knows what to check and what was deliberately deferred.
