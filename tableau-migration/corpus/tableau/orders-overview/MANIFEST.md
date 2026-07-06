# tableau / orders-overview

The standard "Orders Overview" demo dashboard on a retail Snowflake star
(ORDER_FACT + CUSTOMER_DIM / PRODUCT_DIM / STORE_DIM / DATE_DIM / PROMO_DIM /
DIM_TIME). A real `.twb` (204 KB) — the broadest single-workbook coverage in the
corpus, and the first case to get Hex goldens.

## Artifacts

| File | What it is |
|---|---|
| `workbook-content.twb` | Full Tableau workbook XML — federated / published-VDS datasource, calc fields incl. an LOD FIXED, worksheets + dashboard |
| `signals.json` | Parsed discovery signals: 7 views, per-view headers + per-column kind / distinct / sample / numeric range (the parity ground truth) |

## Features exercised

- Federated datasource over a published Virtual Connection
- **FIXED LOD** calc field (per-tier / per-customer fixed aggregate)
- Multi-table joins across the star (fact + 5 dims)
- Metric translation: Gross Margin Pct, Return Rate, Revenue Per Order
- Aggregate viz types: bar by region / category, KPI-style ratios

## What Phase 1 (Tableau → SQL) must handle

- Resolve the federated/VDS datasource to the warehouse tables + join keys.
- Translate the FIXED LOD to SQL — either `SUM(x) OVER (PARTITION BY <dims>)`
  (broadcast) or a `GROUP BY <dims>` CTE joined back (reduce), depending on the
  consuming worksheet's grain.
- Translate the three ratio metrics (Gross Margin Pct = margin/revenue, Return
  Rate, Revenue Per Order) as aggregate expressions.
- Consolidate: the worksheets share one base + join, so cluster into a small
  number of SQL cells at the finest grain any chart needs.

## What Phase 2 (SQL → Hex cells) must handle

- Bar EXPLORE cells (region, category) + ratio KPIs as METRIC cells.
- Carry number/percent display formats from the `.twb`.

## Parity ground truth

Upstream live run recorded strict chart parity **5/5** — Revenue by Region,
Orders by Category, Return Rate by Ship Speed Category, Gross Revenue by Ship
Speed Category, Gross Margin % by Customer Value Tier. Values in `signals.json`
are a captured snapshot; on a live migration, re-verify against the warehouse
(the same one Tableau reads), not against baked numbers.
