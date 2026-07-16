# SQL-fidelity review gate (Phase 1.5)

A mandatory review pass **between oracle-validation (step 4) and building native
cells (step 6)**. It exists to catch the **dangerous error class**: SQL that is
*syntactically fine* — it runs, the run-status oracle returns COMPLETED — but is
**semantically wrong**. Missed a context filter, off-by-one date window, `COUNT`
where the source used `COUNTD`, wrong grain, a join that fanned out the rows,
resolved a field by caption and picked the wrong table. The oracle can't see any
of these (they all COMPLETE), and **the agent that wrote the SQL is the worst
judge of it** — it made the mistake precisely because it didn't notice.

The fix is not "re-read the query and see if it looks right." It's three things
together — **independent + structured + targeted**:

1. **Structured** — a translation ledger makes the source→target mapping explicit
   so there's something concrete to check against.
2. **Independent** — a *fresh-context* pass re-derives the intended SQL straight
   from the `.twb` and **diffs** it against what was written. Fresh eyes catch the
   blind spot the first pass had.
3. **Targeted** — a checklist of the known silly-mistake classes, and
   **differential probes** that *prove* a filter/join behaves using real queries,
   not reading.

Run this per SQL cluster (per shared SQL cell), not per chart — the cluster is
the unit that carries the filters, joins, and grain.

---

## 1. Write the translation ledger (structured)

Before building any charts, record — per worksheet, grouped by the SQL cluster it
maps to — an explicit **source → target** mapping. This is the artifact the
review diffs against; making the mapping explicit is itself the first place
mistakes surface.

For each worksheet capture:

| Ledger field | From the `.twb` (source) | In the SQL (target) |
|---|---|---|
| **Fields** | by **internal name** (not caption) → underlying column/formula | the `SELECT` expression |
| **Marks / measures** | measure + **aggregation kind** (SUM / AVG / **COUNTD** / MIN…) | the aggregate emitted |
| **Filters — every scope** | worksheet / dashboard / data-source / context-workbook / extract | which land in the shared `WHERE` vs. the per-chart cell |
| **Grain** | the row grain the sheet renders at | the query's grain (+ keys) |
| **Date granularity** | pill trunc (`tqr`/`tmn`/`YEAR()`) + type | `truncUnit` + real `DATE` type |
| **Calcs / LOD / window** | the Tableau expression + its status legend mark | the translated SQL (`OVER(...)`, CTE, …) |
| **Joins / model** | tables + join keys + expected cardinality | the `FROM … JOIN …` |

Keep it in the migration plan/manifest alongside the `sql_cell → [charts]`
mapping. Reuse the calc **status legend** (✅/🔸/🐍/⚠️) from
[`tableau-semantics.md`](tableau-semantics.md) — the reviewer checks the ✅/🔸
rows hard and treats 🐍/⚠️ as deliberately deferred.

## 2. Independent re-derivation & diff (independent)

> **The point is independence.** Re-derive from the source, don't re-read the
> answer. An agent grading its own SQL reproduces its own blind spot.

**On Claude Code (and hosts with subagents): spawn a subagent.** Give it *only*
the `.twb` XML (or the parsed source facts) and the cluster's ledger row —
**not** the SQL you wrote — and ask it to **independently derive the SQL each
worksheet in the cluster should produce**, then diff its derivation against the
actual SQL and report every divergence. A fresh context is the whole value; don't
hand it your reasoning.

**On hosts without subagents (Codex, etc.): fresh-context self-review.** Re-open
the `.twb` and **re-compute** each worksheet's intended query from scratch —
deliberately *without* looking at the SQL you wrote — then compare. Not "does
this look right"; **"here's what it should be — does it match?"**

Either way the output is a **divergence list**: for each mismatch, the worksheet,
what the source implies, what the SQL does, and which checklist class (§3) it
falls under. No divergences → gate passes. Any divergence → fix the SQL and
re-run step 4's oracle before proceeding.

## 3. Targeted checklist — the known silly-mistake classes

Run every cluster against this. Each line is a real class of oracle-invisible
error; the linked docs carry the full rule.

- ☐ **Filter-scope sweep.** Every data-source / context-workbook / extract filter
  is in the shared `WHERE`; worksheet filters stay per-cell; **filter *actions*
  are NOT `WHERE` clauses**. A missed shared-scope filter silently changes every
  total. → [`gotchas.md`](gotchas.md) *Sweep ALL filter scopes*.
- ☐ **Relative-date off-by-one.** "Last N years/months" windows include the
  current period in Tableau — verify the window boundary, don't eyeball it. →
  [`tableau-semantics.md`](tableau-semantics.md) §2.
- ☐ **Week anchoring.** Tableau weeks are **Sunday**-anchored; most warehouses
  `DATE_TRUNC('week')` to **Monday**. → [`tableau-semantics.md`](tableau-semantics.md) §2.
- ☐ **Field by definition, not caption.** Each field resolved via internal name →
  formula/column; same-caption-on-two-joined-tables picks the *right* table. →
  [`gotchas.md`](gotchas.md) *Resolve fields by definition*.
- ☐ **Real data types (dates especially).** Type confirmed against the
  **warehouse**, not the `.twb` metadata (which mislabels); dates stay `DATE`. →
  [`gotchas.md`](gotchas.md) *Preserve field data types*.
- ☐ **Aggregation kind.** `SUM` vs `AVG` vs `MIN/MAX`, and critically **`COUNT`
  vs `COUNTD`** (`COUNT(DISTINCT …)`) — a silent count-vs-distinct swap is a
  classic wrong-number.
- ☐ **Join grain / fan-out / dedupe.** Cardinality preserved (default
  many-to-one); a one-to-many join that fans out rows inflates every downstream
  `SUM`/`COUNT`. Prove it with a probe (§4).
- ☐ **Null handling.** `ZN` → `COALESCE(x,0)`; nulls in `COUNT`/`AVG`/denominators
  behave as intended; `NULLIF` guards divisions.
- ☐ **Ratio-of-aggregates.** Margin %, conversion rate, etc. computed as
  `SUM(a)/SUM(b)` in SQL — **not** as an EXPLORE aggregating a pre-divided column
  (row-averaged ratios are wrong). → [`tableau-semantics.md`](tableau-semantics.md) §9.
- ☐ **Deferred items are intentional.** Every 🐍/⚠️ ledger row is a *deliberate*
  gap noted for the customer, not an accidental drop.

## 4. Differential probes — prove behavior with the oracle

The oracle only returns COMPLETED/ERRORED, so turn each assertion into an
expression that **raises divide-by-zero (→ ERRORED) exactly when the assertion is
violated**. General form:

```sql
SELECT 1.0 / (CASE WHEN <assertion-holds> THEN 1 ELSE 0 END)
```

**COMPLETED = assertion holds = good. ERRORED = assertion violated = bug.** Run
one per suspect cluster with `hex cell run <cell_id>` + `hex run status … --watch`
(isolates the failure to that cell). This lets you *verify* the counts you can't
read.

- **A filter actually moved the number** (catches a wrong-scope / no-op filter):
  ```sql
  SELECT 1.0 / (CASE WHEN
    (SELECT COUNT(*) FROM base) > (SELECT COUNT(*) FROM base WHERE <filter>)
  THEN 1 ELSE 0 END)
  ```
  ERRORED ⇒ the filter removed **zero** rows — wrong column, wrong scope, or a
  filter action mistaken for a predicate.
- **A join didn't fan out** (many-to-one preserved):
  ```sql
  SELECT 1.0 / (CASE WHEN
    (SELECT COUNT(*) FROM base) = (SELECT COUNT(*) FROM base JOIN dim ON <key>)
  THEN 1 ELSE 0 END)
  ```
  ERRORED ⇒ the join inflated the row count — every downstream `SUM`/`COUNT` is
  overstated. (Equivalent: assert the lookup key is unique — `COUNT(*) =
  COUNT(DISTINCT key)` on `dim`.)
- **Result isn't empty** (catches an over-filtered / mis-translated window):
  ```sql
  SELECT 1.0 / COUNT(*) FROM (<your query>)
  ```
  ERRORED ⇒ zero rows (e.g. a relative-date window that filtered everything out,
  or the `''value''` quoted-Jinja trap). → [`gotchas.md`](gotchas.md) Hex CLI quirks.

⚠️ Probes are **throwaway scaffolding** — `hex cell delete <cell_id>` them (or
trash the scratch project) before handoff, same as the oracle probe cells. The
delivered project holds only real SQL + chart cells.

> Probes prove *behavior* (a filter fired, a join held, rows exist). They do
> **not** prove the magnitude matches the source's rendered number — that remains
> the human **visual-QA** gate (step 7). The review gate shrinks how often visual
> QA finds a defect; it doesn't replace it.

---

## Gate outcome

- **Pass** — ledger complete, independent re-derivation shows no divergence,
  checklist clean, probes COMPLETED. Proceed to build native cells (step 6).
- **Fail** — any divergence or a probe ERRORED. Fix the SQL, re-run the **step 4
  oracle**, then re-run this gate for the affected cluster. Don't build charts on
  unreviewed SQL.
- **Deferred (🐍/⚠️)** — recorded in the ledger + migration notes as a known gap
  for the customer; not a blocker.

**In batch mode** this runs inside Phase 2 (sequential, per workbook), right after
oracle-validation and before native cells — record the gate result in the
manifest `notes`. The independent-review subagent is safe to spawn per workbook;
keep the human visual-QA gate in the main thread (Phase 3).
