# SQL-fidelity review gate (Phase 1.5)

A mandatory review pass **between oracle-validation (step 4) and building native
cells (step 6)**. It catches the **dangerous error class**: SQL that is
*syntactically fine* — it runs, the run-status oracle returns COMPLETED — but is
**semantically wrong**. Missed an explore-level filter, wrong week anchor,
`count` where the measure was `count_distinct`, wrong grain, a `one_to_many` join
that fanned out the rows, resolved a field by label and picked the wrong view.
The oracle can't see any of these (they all COMPLETE), and **the agent that wrote
the SQL is the worst judge of it** — it made the mistake precisely because it
didn't notice.

The fix is four things together — **structured + independent + targeted + measured**:

1. **Structured** — a translation ledger makes the LookML→SQL mapping explicit.
2. **Independent** — a *fresh-context* pass re-derives the intended SQL straight
   from the LookML + contract and **diffs** it against what was written.
3. **Targeted** — a checklist of the known mistake classes, and **differential
   probes** that *prove* a filter/join behaves.
4. **Measured** — Looker will tell you the **actual numbers**
   (`looker_fetch.py query`). Diff Hex's real output against Looker's real output
   per cluster — a direct *value* check, the strongest signal you have.

Run this per SQL cluster (per shared SQL cell), not per tile — the cluster is the
unit that carries the filters, joins, and grain.

---

## 1. Write the translation ledger (structured)

Before building any charts, record — per tile, grouped by the SQL cluster it maps
to — an explicit **source → target** mapping. This is the artifact the review
diffs against; making the mapping explicit is itself the first place mistakes
surface.

For each tile capture:

| Ledger field | From LookML + the contract (source) | In the SQL (target) |
|---|---|---|
| **Fields** | each `view.field` id → its view's `dimension`/`measure` `sql:` | the `SELECT` expression |
| **Measures** | measure `type:` (sum / average / **count_distinct** / median…) | the aggregate emitted |
| **Filters — every scope** | explore `sql_always_where`/`always_filter`/`access_filter`; dashboard filter defaults; tile `query.filters` | which land in the shared `WHERE` vs. the per-tile cell |
| **Grain** | the explore + join graph the tile renders at | the query's grain (+ keys) |
| **Date granularity** | `dimension_group` timeframe suffix (`_month`/`_week`/…) + `week_start_day` | `DATE_TRUNC` unit + real `DATE` type |
| **Table calcs / windows** | `dynamic_fields` Looker expression | the translated SQL (`OVER(...)`) |
| **Joins / model** | explore `join`s: keys + `relationship:` | the `FROM … JOIN …` |
| **RLS** | `access_filter` / user-attribute Liquid | ported / flagged (§checklist) |

Keep it in the migration plan/manifest alongside the `sql_cell → [tiles]` mapping.
Reuse the status legend (✅/🔸/🐍/⚠️) from
[`lookml-semantics.md`](lookml-semantics.md) — the reviewer checks the ✅/🔸 rows
hard and treats 🐍/⚠️ as deliberately deferred.

## 2. Independent re-derivation & diff (independent)

> **The point is independence.** Re-derive from the source, don't re-read the
> answer. An agent grading its own SQL reproduces its own blind spot.

**On Claude Code (and hosts with subagents): spawn a subagent.** Give it *only*
the LookML (the explore JSON + view files) and the cluster's ledger row — **not**
the SQL you wrote — and ask it to **independently derive the SQL each tile in the
cluster should produce**, then diff its derivation against the actual SQL and
report every divergence. You may also hand it **Looker's generated SQL**
(`looker_fetch.py sql`) as an independent reference — but note it's full of
resolved scratch-table names and expanded joins, so diff *structure/semantics*,
not text.

**On hosts without subagents: fresh-context self-review.** Re-open the LookML and
**re-compute** each tile's intended query from scratch — deliberately *without*
looking at the SQL you wrote — then compare. Not "does this look right"; **"here's
what it should be — does it match?"**

Either way the output is a **divergence list**: for each mismatch, the tile, what
the LookML implies, what the SQL does, and which checklist class (§3) it falls
under. No divergences → continue to §3–§4. Any divergence → fix the SQL and re-run
step 4's oracle before proceeding.

## 3. Targeted checklist — the known mistake classes

Run every cluster against this. Each line is a real class of oracle-invisible error.

- ☐ **Filter-scope sweep.** Every explore `sql_always_where` / `always_filter`
  and every dashboard filter with a default that tiles `listen` to is in the
  shared `WHERE`; tile `query.filters` stay per-cell. A missed explore-scope
  filter silently changes every total. → [`gotchas.md`](gotchas.md).
- ☐ **`count` vs `count_distinct`.** Measure `type:` matched exactly. A silent
  count-vs-distinct swap is the classic wrong-number. And **`type: count` on a
  joined view** → `COUNT(DISTINCT pk)`, not `COUNT(*)`.
- ☐ **Join grain / fan-out.** `relationship:` preserved; a `one_to_many` /
  `many_to_many` join that fans out inflates every downstream `SUM`/`COUNT`.
  Prove it with a probe (§4).
- ☐ **Ratio / non-additive measures.** `type: number` measures dividing two sums,
  margin %, conversion rate computed as `SUM(a)/SUM(b)` in SQL — **not** an
  EXPLORE aggregating a pre-divided column. → [`lookml-semantics.md`](lookml-semantics.md) §2, §9.
- ☐ **Week anchoring.** Looker's `week` timeframe honors `week_start_day`
  (default Monday); the warehouse's `DATE_TRUNC('week')` may differ. → §3 of
  [`lookml-semantics.md`](lookml-semantics.md).
- ☐ **Field by definition, not label.** Each `view.field` resolved via its LookML
  `sql:`, not the humanized name; same-caption-on-two-joined-views picks the
  *right* view via the qualified id. → [`gotchas.md`](gotchas.md).
- ☐ **Real data types (dates especially).** Type confirmed against the
  **warehouse**, not LookML metadata; `dimension_group` fields stay real DATEs
  (don't bind a numeric `..._month` proxy to a date axis). → [`gotchas.md`](gotchas.md).
- ☐ **Table calcs computed in SQL.** Every `dynamic_fields` calc became an
  `OVER()` in the cluster SQL, with the right addressing. → §7.5 of
  [`lookml-semantics.md`](lookml-semantics.md).
- ☐ **`${...}` refs fully resolved.** No `${TABLE}` / `${view.field}` left
  literal; transitive refs expanded.
- ☐ **RLS handled explicitly.** `access_filter` / user-attribute Liquid is either
  ported (with the chosen Hex mechanism) or **flagged** in the notes — never
  silently dropped. → [`lookml-semantics.md`](lookml-semantics.md) §6.
- ☐ **Deferred items are intentional.** Every 🐍/⚠️ ledger row is a *deliberate*
  gap noted for the customer, not an accidental drop.

## 4. Prove it: numeric parity + differential probes

### 4a. Numeric parity against Looker (the strong signal)

For each cluster, pull Looker's **actual values** and compare to Hex's output:

```bash
python3 scripts/looker_fetch.py query <cluster-representative-query>.json   # Looker's numbers
```

Compare against the Hex cluster's output at the same grain (e.g. metric-by-dimension).
Because Looker gives you real rows, you can check **magnitude**, not just "it ran":
totals tie, per-dimension breakdowns tie, the ranked order matches. A mismatch
localizes the bug to a checklist class above (wrong filter → wrong total; fan-out
→ inflated total; wrong week anchor → shifted buckets).

- ⚠️ **Grain must match on both sides** — compare Looker's aggregated result to
  the *same* aggregation over the Hex dataframe, not raw rows.
- ⚠️ **PDT snapshot drift.** If the explore is on a persisted derived table, a
  small gap between a live Hex query and Looker's materialized snapshot is
  expected, not a bug (connection-mapping §6) — reconcile against the base tables
  or accept documented drift.
- Reading the Hex value: the CLI can't read cell output directly, so land the
  cluster's key aggregates in a tiny result you *can* compare — e.g. write the
  Hex aggregate to a scratch cell and read it via a probe, or export. When you
  genuinely can't read the Hex number over the CLI, fall back to the oracle
  probes (§4b) + the human visual-QA gate for magnitude.

### 4b. Differential oracle probes

The run oracle only returns COMPLETED/ERRORED, so turn each assertion into an
expression that **raises divide-by-zero (→ ERRORED) exactly when the assertion is
violated**:

```sql
SELECT 1.0 / (CASE WHEN <assertion-holds> THEN 1 ELSE 0 END)
```

**COMPLETED = assertion holds = good. ERRORED = assertion violated = bug.** Run one
per suspect cluster with `hex cell run <cell_id>` + `hex run status … --watch`.

⚠️ **ERRORED is overloaded — anchor the oracle first.** A row-level throw (a date/
cast function on an unexpected type, an overflow) *also* returns ERRORED,
indistinguishable from the divide-by-zero you're testing. Before trusting any
probe: **(1)** run **anchor probes** — a known-COMPLETED (`SELECT 1`) and a
known-ERRORED (`SELECT 1/0`); **(2)** keep `<assertion-holds>` an **aggregate
comparison** (scalar `CASE WHEN COUNT(*) … END`), never row-wise arithmetic that
can throw. Full rule → [`gotchas.md`](gotchas.md).

- **A filter actually moved the number** (catches a wrong-scope / no-op filter):
  ```sql
  SELECT 1.0 / (CASE WHEN
    (SELECT COUNT(*) FROM base) > (SELECT COUNT(*) FROM base WHERE <filter>)
  THEN 1 ELSE 0 END)
  ```
  ERRORED ⇒ the filter removed **zero** rows — wrong column/scope.
- **A join didn't fan out** (`many_to_one` preserved):
  ```sql
  SELECT 1.0 / (CASE WHEN
    (SELECT COUNT(*) FROM base) = (SELECT COUNT(*) FROM base JOIN dim ON <key>)
  THEN 1 ELSE 0 END)
  ```
  ERRORED ⇒ the join inflated the row count — every downstream `SUM`/`COUNT` is
  overstated. (Equivalent: assert the lookup key is unique — `COUNT(*) =
  COUNT(DISTINCT key)` on `dim`.)
- **Result isn't empty** (catches an over-filtered window or the `''value''`
  quoted-Jinja trap):
  ```sql
  SELECT 1.0 / COUNT(*) FROM (<your query>)
  ```
  ERRORED ⇒ zero rows. → [`gotchas.md`](gotchas.md).

⚠️ Probes + scratch parity cells are **throwaway scaffolding** — `hex cell delete
<cell_id>` them (or trash the scratch project) before handoff. The delivered
project holds only real SQL + chart cells.

> Numeric parity (§4a) proves *magnitude* against Looker's own answer — the single
> biggest fidelity signal this migration has. Probes (§4b) prove *behavior* (a
> filter fired, a join held, rows exist). Neither proves the rendered chart looks
> right — that remains the human **visual-QA** gate (step 7). The review gate
> shrinks how often visual QA finds a defect; it doesn't replace it.

---

## Gate outcome

- **Pass** — ledger complete, independent re-derivation shows no divergence,
  checklist clean, **numbers tie to Looker** (§4a), probes COMPLETED. Proceed to
  build native cells (step 6).
- **Fail** — any divergence, a parity mismatch, or a probe ERRORED. Fix the SQL,
  re-run the **step 4 oracle**, then re-run this gate for the affected cluster.
  Don't build charts on unreviewed SQL.
- **Deferred (🐍/⚠️)** — recorded in the ledger + migration notes as a known gap
  for the customer; not a blocker.

**In batch mode** this runs inside Phase 2 (sequential, per dashboard), right after
oracle-validation and before native cells — record the gate result (including the
parity outcome, e.g. "3/3 clusters tie to Looker") in the manifest `notes`. The
independent-review subagent is safe to spawn per dashboard; keep the human
visual-QA gate in the main thread (Phase 3).
