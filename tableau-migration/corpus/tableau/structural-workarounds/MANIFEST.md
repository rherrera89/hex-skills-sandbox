# tableau / structural-workarounds

A hand-authored minimal `.twb` exercising three *structural* Tableau features
plus a set of easy-to-botch calc translations. Synthetic XML modeled on real
Tableau 2024.1 shapes; the Snowflake connection block matches the demo warehouse.

## Artifacts

| File | What it is |
|---|---|
| `workbook-content.twb` | 3 worksheets, 1 dashboard, 1 storyboard (3 story points); Snowflake primary + textscan secondary blend; nested-FIXED / iso-year / FINDNTH / bin calc columns |
| `get-workbook.json`, `master-columns.json` | Offline discovery aids |
| `views/*.csv` | Small parity ground-truth exports |

## Features exercised

- **Story** — 3 story points (a dashboard + 2 worksheet captures)
- **Cross-source blend** — Snowflake primary + a textscan secondary, linked on `Region`
- **Nested `{FIXED}` LOD** — 2-level (Sum by Region+Customer → Avg by Region)
- **Calc translations:** ISOYEAR, FINDNTH, BinFixed / BinRange

## What Phase 1 (Tableau → SQL) must handle

- **Nested LOD → chained CTEs**, innermost grouping first: `Sum(x) GROUP BY
  region, customer` → `Avg(...) GROUP BY region`. (In SQL this is cleaner than
  any single window expression.)
- **Blend → a JOIN** when both sides are warehouse-reachable, else materialize
  the secondary; link key = `Region`.
- **Story → separate outputs** (one Hex component/page per story point).

## Tableau subtleties to preserve (dialect-independent facts)

- **ISOYEAR** uses the ISO-week / Thursday-shift rule → `DATE_PART('isoyear', d)`
  (not `YEAR(d)`); the two disagree at year boundaries.
- **FINDNTH(s, sub, n)** — find the nth occurrence; when composing via
  split/array, the segment index is **0-based at the slice start** (an off-by-one
  here silently skips the first segment).
- **BinFixed(x, size)** — bin index is **1-based**: `FLOOR(x/size) + 1`.
- A nested LOD's outer aggregate must read the *grouped* grain, not base rows —
  a base-grain average is row-weighted and wrong.

## Parity ground truth (upstream live run)

- ISOYEAR on a first-order date: per-iso-year counts 2019–2024 = 2/3/7/5/5/3,
  exact vs `DATE_PART('isoyear', …)`.
- FINDNTH (2nd `.` in email): sum 378 across 25 rows, exact vs `SPLIT_PART` —
  after correcting the array-slice start to 0.
- BinFixed(revenue, 0, 100000, 10): bin counts 18/2/1/1/2/1, exact vs
  `FLOOR(rev/10000)+1`.
- 2-level nested LOD (Sum by channel×customer → Avg by channel): App 687.81 /
  In-Store 1279.73 / Online 2417.98 — exact only when the outer aggregate reads
  the grouped grain (row-weighted gives App 969.82, wrong).
