# Tableau migration corpus (the "Tableau Zoo")

Real and hand-authored Tableau workbooks that stress every construct the
`tableau-migration` skill has to handle — LOD, window/table calcs, blends,
stories, crosstabs, parameters, tricky column names. Use them as a **regression
set** so parser and builder changes can be smoke-tested without a live Tableau
tenant or a live Hex project.

## Why this exists

The hard part of a Tableau→Hex migration is *reading Tableau correctly* — the
`.twb` XML and its calc semantics. That half is target-agnostic: a `{FIXED}`
LOD, a `RUNNING_SUM`, a Sunday-anchored week trunc mean the same thing no matter
what you migrate *to*. These fixtures pin that half down with ground-truth
inputs and the numbers Tableau actually rendered.

## Layout

```
corpus/tableau/<case>/
  workbook-content.twb        # INPUT — the Tableau workbook XML (source of truth)
  signals.json | views/*.csv  # PARITY GROUND TRUTH — the values Tableau rendered
  get-workbook.json           # view name → id map (offline discovery aid)
  master-columns.json         # Tableau field → warehouse column hints
  MANIFEST.md                 # what it is, features exercised, parity references
  golden/                     # OUR expected outputs (added as we build them out)
    phase1-sql.json           #   Phase 1 target — expected consolidated SQL per cluster
    phase2-cells.json         #   Phase 2 target — expected Hex cell specs
```

## The two-phase golden

A migration runs in two phases, and the golden is checked per phase:

1. **Phase 1 — code conversion (Tableau → SQL/Python).** Parse the `.twb`,
   resolve the connection, translate calcs / LOD / window calcs / filters into
   consolidated warehouse SQL (Python only for genuine gaps like maps and
   per-row detail). `golden/phase1-sql.json` = the expected SQL per cluster.
2. **Phase 2 — visualization build-out (SQL → Hex native cells).** Map each
   worksheet onto a Hex EXPLORE / METRIC / pivot cell via clone-and-override
   YAML. `golden/phase2-cells.json` = the expected cell specs
   (type, channels, filters, display format).

On top of both, **parity** is the end-to-end correctness gate: the migrated SQL,
run against the warehouse via the run-status / CSV-export oracle, must reproduce
the numbers in `signals.json` / `views/*.csv`. Parity is exact for
warehouse-backed workbooks (Hex queries the same warehouse Tableau reads) — a
value gap is a real bug, not "drift." Drift tolerance applies only to
`.hyper`-extract workbooks (frozen snapshots).

Goldens are added incrementally — a case can ship input + parity ground truth
before its `golden/` exists. `orders-overview` is the first case with a Phase-1
golden (`golden/phase1-sql.json`); its Phase-2 golden and the other cases follow.

## Cases

| Case | Source | Exercises |
|---|---|---|
| `orders-overview` | real .twb (204 KB) | federated datasource, FIXED LOD, multi-table joins, metric translation |
| `structural-workarounds` | synthetic .twb | story, cross-source blend, nested `{FIXED}` LOD, ISOYEAR / FINDNTH / bins |
| `winprobe-window-functions` | real .twb | all 8 window/table-calc families (RUNNING_SUM, WINDOW_AVG, RANK, LOOKUP, pareto, …) |
| `partner-crosstab-controls` | synthetic .twb | Automatic-mark crosstabs, quick-filter column-name landmines, measure-switcher parameters |

## Attribution

These fixtures (the `.twb` workbooks, `signals.json`, view CSVs, `get-workbook.json`,
`master-columns.json`) are borrowed from the **`sigma-migration-skills`** project by
**Thomas Wells** (https://github.com/twells89/sigma-migration-skills), MIT-licensed.
We use only the target-agnostic Tableau-side artifacts and write our own Hex-side
goldens. The upstream MIT license is preserved in `ATTRIBUTION.md`.

The data is demo/synthetic (a retail star schema — ORDER_FACT + dims) with no
tokens or customer names.
