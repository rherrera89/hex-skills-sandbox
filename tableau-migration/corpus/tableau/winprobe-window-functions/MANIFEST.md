# tableau / winprobe-window-functions

Eight worksheets, one Tableau window/table-calc family each, over a retail
`ORDER_FACT` demo warehouse. The regression case for **Tableau table calcs →
warehouse SQL window functions** — the mapping Hex handles natively because Hex
cells are raw SQL (no chart-context restriction).

## Artifacts

| File | What it is |
|---|---|
| `workbook-content.twb` | The workbook XML — 8 worksheets, published virtual-connection datasource |
| `get-workbook.json` | View name → id map (offline discovery aid) |
| `master-columns.json` | Field → warehouse column hints for the 6 ORDER_FACT columns |
| `views/*.csv` | Tableau view exports = the parity ground truth (incl. Measure-Names long-format + a quarter-label pivot) |

## Features exercised → SQL target

| Worksheet | Tableau calc | Warehouse SQL (Snowflake) |
|---|---|---|
| WIN Running Revenue | `RUNNING_SUM(SUM(x))` by week | `SUM(SUM(x)) OVER (ORDER BY week)` |
| WIN Moving Avg | `WINDOW_AVG(SUM(x), -3, 0)` | `AVG(SUM(x)) OVER (ORDER BY … ROWS BETWEEN 3 PRECEDING AND CURRENT ROW)` |
| WIN Pct Of Total Region | `SUM(x)/WINDOW_SUM(SUM(x))` | `SUM(x) / SUM(SUM(x)) OVER ()` |
| WIN Rank Category | `RANK(SUM(x))` | `RANK() OVER (ORDER BY SUM(x) DESC)` — Tableau defaults **DESC** |
| WIN Window MaxMin | unbounded `WINDOW_MAX/MIN`, Region × Quarter pivot | `MAX/MIN(...) OVER (PARTITION BY region)` |
| WIN WoW Delta | `ZN(SUM(x) - LOOKUP(SUM(x), -1))` | `COALESCE(SUM(x) - LAG(SUM(x),1) OVER (ORDER BY …), 0)` |
| WIN Weekly Funnel | Measure Names (CountD + Sum + ratio) | one multi-measure select |
| WIN Pareto Category | `RUNNING_SUM(SUM(x))/TOTAL(SUM(x))` | `SUM(SUM(x)) OVER (ORDER BY …) / SUM(SUM(x)) OVER ()` |

## Tableau subtleties to preserve (dialect-independent facts)

- `RANK()` defaults to **DESC** in Tableau (SQL `RANK()` needs the explicit
  `ORDER BY … DESC`).
- `LOOKUP(agg, -1)` = the **previous** row → `LAG(agg, 1)`; positive offset =
  `LEAD`.
- Tableau week-trunc is **Sunday-anchored**; Snowflake `DATE_TRUNC('week')` is
  Monday-anchored — adjust, or the weekly buckets shift by a day.
- `<computed-sort>` ("sort dim X by measure Y") sets the `ORDER BY` that the
  cumulative / rank window follows — carry it.
- Measure-Names worksheets export as LONG rows; pivot to wide (one column per
  measure, named with the verbatim Tableau label) for parity matching.
- Unbounded `WINDOW_MAX/MIN` is constant-per-partition → `OVER (PARTITION BY …)`
  with no `ORDER BY` (or a subquery); don't `SUM` a partition constant.

## Parity ground truth

Upstream live run: **930/930 cells exact** (tol 1e-6) across all 8 families,
three-way (Tableau CSV == warehouse SQL == migrated output). The `views/*.csv`
here are that ground truth. Re-verify against the live warehouse on migration.
