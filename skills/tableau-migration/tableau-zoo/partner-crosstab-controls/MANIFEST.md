# partner-crosstab-controls

A hand-authored minimal `.twb` reproducing three real-world regressions from a
large partner-bookings workbook: crosstab detection, quick-filter column-name
landmines, and a measure-switcher parameter. Synthetic XML on the demo retail
star.

## Artifacts

| File | What it is |
|---|---|
| `workbook-content.twb` | 1 Automatic-mark crosstab worksheet (Partner rows × quarter cols), 1 Automatic-mark multi-measure BAR (the over-fire guard — must NOT be read as a crosstab), 1 dashboard, a `<shared-view>` with 3 quick filters, and an integer measure-swap parameter with value aliases |
| `get-workbook.json`, `master-columns.json` | Offline discovery aids |

## Features exercised

1. **Automatic-mark crosstab** — dims on both shelves + Measure Names on
   columns → a pivot/crosstab, *not* a flat table. Plus a guard case: an
   Automatic-mark worksheet with measure **values** on rows is a BAR, not a
   crosstab.
2. **Quick-filter column-name landmines** — filter columns with no `caption`,
   multi-word names, Tableau **groups** (`[Partner Level (group)]`), and slashes
   (`[Mkt Sourced/Influenced]`). All must resolve to real columns, none dropped.
3. **Measure-switcher parameter** — an integer parameter (1→TCV / 2→Product TCV
   / 3→ACV) whose CASE swaps which aggregated field is displayed; the control
   must show the **alias labels**, not raw `1 / 2 / 3`.

## What Phase 1 (Tableau → SQL) must handle

- **Parameter → Hex input parameter cell** (dropdown of the alias labels) wired
  into the shared SQL via a Jinja `{{ var }}` `CASE` that swaps the measure.
- **Quick filters → shared-SQL predicates** (or per-cell filters), resolving the
  awkward column names to real warehouse columns.

## What Phase 2 (SQL → Hex cells) must handle

- **Crosstab → Hex pivot-table cell** (rows = Partner, columns = quarter, values
  = measure) with grand-total row + column.
- The over-fire guard worksheet → a bar EXPLORE, not a pivot.
- The parameter control renders with alias labels.

## Tableau subtleties to preserve (dialect-independent facts)

- Tableau's **default `Automatic` mark** can still be a crosstab — detect by
  "dims on both rows and columns (+ Measure Names)," not by mark type alone.
- Distinguish Measure **Names** (a pivot header) from Measure **Values** (a
  multi-measure bar) — the latter is not a crosstab.
- Filter/parameter columns may carry no caption, be Tableau groups, or contain
  slashes / spaces — resolve by internal name, don't truncate to the first word.
- An integer parameter's **value aliases** are the control's display labels.

## Parity ground truth (upstream live run)

Built on the live warehouse: the pivot rendered as a grouped crosstab with a
grand-total row + column; the segmented control showed the alias labels; flipping
it changed the measure column (grand total 119,038 → 1,593) while a static column
held — proving the parameter switches the calculation.
