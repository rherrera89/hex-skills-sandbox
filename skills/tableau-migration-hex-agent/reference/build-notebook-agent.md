# Build via Hex's notebook agent (Phase 2 — the recommended path)

The **default way to build the dashboard**: hand the work to Hex's in-product
notebook agent (`hex thread`), driven by a **migration brief** you write into the
project. Use this doc once you've parsed the workbook (Phase 1) and the customer
has chosen a notebook-agent mode at the build-path gate (SKILL.md).

## Why the notebook agent is the better builder here

This coding agent (the one reading this skill) is **blind to the things that make
the SQL correct and the dashboard usable**:

- It **cannot see the warehouse** — not the live schema, column types, or the
  data. It infers them from the `.twb` + a few probes.
- It **cannot see the customer's Hex context** — Context Studio descriptions,
  endorsed/undorsed tables, semantic models, existing guides, prior projects.
- It **cannot see the rendered result** — every chart is built blind.

The **notebook agent has all three**. It runs inside the workspace, reads the
live schema and the curated context, writes correct dialect SQL against tables it
can actually inspect, and iterates against what it renders. For building *in Hex*,
it is simply better-equipped than this agent. So the division of labor is:

> **This coding agent owns *understanding the Tableau source* and *verifying the
> result*. The notebook agent owns *building it in Hex*.** Accuracy is guaranteed
> by the fidelity gate (which reviews whoever's SQL — see
> [`sql-review.md`](sql-review.md)), not by this agent hand-writing every query.

This is **not** a "prettier output" tradeoff — it's a "the builder can see what
it's building" advantage. The cost is Hex credits.

## The two modes

Both are driven by the brief; they differ only in who first authors the SQL.

- **Mode A — delegate the whole build (default).** You write the brief; the
  notebook agent builds the **SQL cells, the parameters, and the charts**. You
  then run the fidelity gate **post-hoc** on what it built (read its SQL + values,
  diff against the `.twb`). Simplest, and it leans fully on the agent's schema +
  context sight. Verified to reproduce correct, gated SQL from a good brief.
- **Mode B — pre-build the SQL, delegate the viz.** You build + gate the SQL
  cells first, then the agent builds only the charts/params from the brief + those
  cells. Choose this when the **data population is subtle** (aggressive shared
  filters, a fan-out risk, a relative-date window) and you want the numbers pinned
  and gated *before* any viz work — see [`sql-review.md`](sql-review.md). It costs
  a YAML round-trip (`hex cell create` can't mint INPUT or dataframe-SQL companion
  cells — see [`gotchas.md`](gotchas.md)).

When unsure, default to **A** and rely on the post-hoc gate; escalate to **B** for
high-stakes or subtle-population workbooks.

---

## Writing the migration brief

The brief is a **markdown cell in the project** — persistent, re-readable by the
agent across `continue` turns, and visible to the customer. It carries everything
the agent needs and can't get from this skill (which it can't read). It is the
skill's real deliverable: **a faithful, precise transcription of the Tableau
workbook.**

### Describe *intent*, not literal SQL

⚠️ **Do not paste finished SQL for the agent to copy.** The agent can see the
warehouse schema and the customer's context; you can't. If you dictate exact SQL,
you throw away its biggest advantage and re-introduce your blind spots (a guessed
column type, a dialect quirk, an un-endorsed table). Instead, describe **what each
derivation is meant to represent** and let the agent implement it against the
schema it can see.

> Frame it explicitly in the brief: *"These are the SQL derivations of the Tableau
> workbook and what each is meant to represent. Use your judgment and the
> warehouse schema + workspace context you can see to build them correctly."*

Bad (prescriptive): `SELECT SUM(SUM(arr)) OVER (PARTITION BY segment ORDER BY DATE_TRUNC('month', closed_date)) …`
Good (intent): *"Running total of ARR — cumulative SUM(ARR) by calendar month of
close date, accumulating **within each segment** (segment resets the running
total). Source: Tableau `RUNNING_SUM(SUM([ARR]))`, addressed along close-date
month, partitioned by Account Segment."*

The intent form names the **Tableau construct** (so the agent knows the source of
truth) and **what it should compute** (so the agent can verify), but leaves the
dialect SQL to the agent.

### What the brief must contain

Enumerate everything — the agent builds only what you name, so a missed derivation
is a missed chart.

1. **What the dashboard is + who it's for** — one or two sentences of purpose.
2. **Data source** — the resolved connection, database/schema, tables, and the
   **join** (keys + expected cardinality), stated as facts for the agent to
   confirm against the schema it sees. Note where each field lives (which table).
3. **Shared filters (the population)** — every data-source/context/workbook filter
   that applies to all charts, described as intent (e.g. "closed deals only; ARR ≥
   the threshold parameter; close date in the last-year window"). Flag the
   [relative-date translation](tableau-semantics.md) and any off-by-one risk.
4. **Parameters + scope** — for each: control type, default, domain/options, and
   **which cells it affects** (all charts vs. named ones). See the scope rule in
   [`tableau-semantics.md`](tableau-semantics.md) §5. Data-population params
   belong in the shared filter; chart-scoped params attach to their cells.
5. **The derivations needed** — the shared base + every companion (running totals,
   ratios/LOD, KPI scalars), each as **intent + the Tableau construct it came
   from**. This is where you prevent the agent from missing a table calc or a
   ratio-of-aggregates. Reuse the calc **status legend** (✅/🔸/🐍/⚠️) from
   [`tableau-semantics.md`](tableau-semantics.md).
6. **The charts** — one line per worksheet: title (exact), chart type, x / y +
   aggregation, color/detail, sort, number format, and which derivation it reads.
   Resolve caption landmines here (name the real field, not the worksheet caption).
7. **Layout** — the row-by-row order the dashboard should assemble into.
8. **Styling** — colors per member + number/date formats (high-value fidelity);
   leave cosmetic-only knobs to Hex defaults.
9. **Gaps** — maps, iframe embeds, per-row detail: name them as known gaps
   (🐍/⚠️) so the agent doesn't silently approximate them.

Keep it tight — intent, not prose. A dashboard's worth of brief is a page or two.

---

## The handoff

1. **Inject the brief** as a markdown cell (`hex cell create -t markdown -l "Migration brief"`).
   In Mode A also attach the data connection to the project (a one-line seed SQL
   cell via `hex cell create --data-connection-id …` does this — the agent needs a
   connection to build SQL against). In Mode B the QA'd SQL cells are already there.
2. **Start the thread with a short prompt** pointing at the brief:
   > *"Read the `Migration brief` cell — it's the full spec for migrating a Tableau
   > dashboard into this project. Build it end to end: the SQL derivations it
   > describes, the input parameters, and the native chart/KPI cells in the given
   > layout. Build **native Hex cells** (SQL + EXPLORE/METRIC/PIVOT + INPUT), not a
   > custom code app. Use the warehouse schema and workspace context you can see to
   > implement the SQL well."*
   (Mode B: add *"the SQL cells already exist — use them as the data source, don't
   rewrite them."*)
3. **⚠️ Surface the live URL to the customer immediately.** `hex thread create
   --json` returns a `url`. Give it to them **as the build starts** so they can
   *watch the agent work in real time and stop/redirect it* if it drifts — the
   build runs several minutes and is otherwise a black box. Don't poll silently.
4. **Prompt framing decides the output *form*.** A chart-type-prescriptive brief →
   **native EXPLORE/METRIC cells** (diff-able — what you want). A loose "make an
   app" prompt → a custom **React app** (`genAppFiles`), not native cells. For a
   migration, prescribe chart types (the brief already does).
5. **Poll** `hex thread get <id>` until `Status: IDLE`; iterate with
   `hex thread continue <id> "<fix>"`.

## Verify + gate (always)

The build is not done until it's gated. The notebook agent is capable but still a
black box that can be confidently wrong — **verify, don't trust.**

- **Confirm cell usage** — `hex project export` and check what it built: SQL cells
  present + (Mode B) unchanged, charts bound to the right dataframes, params wired.
- **Run the SQL-fidelity gate on its SQL** — read every SQL cell's values with
  `hex cell run <id> --with-output`, diff the agent's SQL against your independent
  re-derivation from the `.twb`, run the mistake-class checklist + differential
  probes. Full procedure → [`sql-review.md`](sql-review.md). The gate reviews
  *whoever* wrote the SQL — post-hoc on the agent's cells is a first-class use.
- **Fix divergences** — either `hex thread continue <id> "<name the exact
  divergence>"`, or edit the cell directly (YAML / `hex cell update`) when a
  surgical fix is faster than another agent round-trip.
- **Visual QA is still the human gate** — you can't render the app (it's behind
  login; never enter credentials). Give the customer the original ↔ migrated
  side-by-side (`scripts/tableau_shots.py`). See SKILL.md step "Run and QA".

## Cheat-sheet

- `hex thread create "<prompt>" --project <id> --json` → `url` (hand to customer) + `thread_id`.
- `hex thread get <id>` → `Status: RUNNING｜IDLE`; `hex thread messages <id>` → its reasoning.
- `hex thread continue <id> "<prompt>"` → iterate.
- Needs the headless-agent-threads feature enabled for the workspace. Uses Hex credits.
