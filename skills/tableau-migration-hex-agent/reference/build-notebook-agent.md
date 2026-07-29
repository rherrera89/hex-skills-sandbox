# Build via Hex's notebook agent (Phase 2 — the recommended path)

The **default way to build the dashboard**: hand the work to Hex's in-product
notebook agent (`hex thread`), driven by a **migration brief** you write into the
project. **The target output is a Hex Generative app** (see the next section). Use
this doc once you've parsed the workbook (Phase 1) and the customer has chosen a
notebook-agent mode at the build-path gate (SKILL.md).

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
  context sight — a precise brief yields correct, gate-ready SQL.
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

## Target: a Hex Generative app (not a classic notebook app)

**Build the dashboard as a Hex Generative app** (App builder → *Generative app* — a
React app Hex renders client-side), with the **SQL cells kept underneath as the
data sources**. This is the default for this skill, for two reasons:

- **It's where Hex is taking dashboards.** Generative apps are the strategic
  surface — pixel-level layout control (custom KPI cards, formula rows, hover
  tooltips, side-by-side groupings) that classic app-builder cells can't express —
  so a migration lands better long-term as one.
- **It preserves everything underneath.** The SQL cells (+ params) still exist as
  the data layer, so the fidelity gate, the semantic-layer guide, and Threads
  self-serve all work exactly the same — the Generative app is a viz layer *on top*
  of clean SQL, not a replacement for it.

⚠️ **There is no CLI flag for app type.** `hex thread create` builds a **classic
notebook+app by default** unless the prompt **explicitly demands a Generative app**
— the prompt wording is the only control. So:

1. The build prompt must **open by demanding a Generative app** (the template below
   does).
2. **After the thread goes IDLE, verify Hex complied before any gate/QA:**
   `hex project export <project_id> -o app.yaml` and confirm a **non-empty
   `genAppFiles`** list. If it's missing, Hex built a classic notebook+app — do
   **not** proceed. Send:
   > `hex thread continue <thread_id> "You built this as a classic notebook app. Rebuild it as a Generative app (App builder → Generative app): move the whole dashboard into the generative app, keeping the SQL cells as data sources. Do not change any queries."`
   …and re-verify after it goes IDLE.

(The **fallback** Mode C — this coding agent hand-building native EXPLORE/METRIC
cells → [`building-cells.md`](building-cells.md) — produces *native cells, not a
Generative app*. It's the lower-fidelity path for when the notebook agent isn't
available; flag the reduced layout fidelity to the customer.)

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
2. **Start the thread with a short prompt** pointing at the brief. It must **demand
   a Generative app** up front (the only way to control app type — see above):
   > *"Build this as a Hex **Generative app** (App builder → Generative app), NOT a
   > classic notebook+app. Read the `Migration brief` cell — it's the full spec for
   > migrating a Tableau dashboard into this project. Build it end to end: the SQL
   > derivations it describes (as SQL cells that stay as the app's data sources),
   > the input parameters, and the Generative app that reproduces every chart/KPI in
   > the given layout. Use the warehouse schema and workspace context you can see to
   > implement the SQL well."*
   (Mode B: add *"the SQL cells already exist — use them as the data source, don't
   rewrite them."*)
3. **⚠️ Surface the live URL to the customer immediately.** `hex thread create
   --json` returns a `url`. Give it to them **as the build starts** so they can
   *watch the agent work in real time and stop/redirect it* if it drifts — the
   build runs several minutes and is otherwise a black box. Don't poll silently.
4. **Poll** `hex thread get <id>` until `Status: IDLE`; iterate with
   `hex thread continue <id> "<fix>"`. If status is `ERROR`, the run died partway —
   `hex thread continue` to finish; partial work usually landed.
5. **Verify it's a Generative app** (see the section above): export the project and
   confirm a non-empty `genAppFiles`; if Hex built a classic notebook app, send the
   rebuild-as-Generative continue-prompt and re-verify. Do this **before** the gate.

## Verify + gate (always)

The build is not done until it's gated. The notebook agent is capable but still a
black box that can be confidently wrong — **verify, don't trust.**

- **Confirm the shape** — `hex project export` and check: **`genAppFiles` is
  non-empty** (it's a Generative app, not a classic notebook), the **SQL cells are
  present as the data sources** (+ unchanged in Mode B), and the params are wired.
- **Run the SQL-fidelity gate on its SQL** — read every SQL cell's values with
  `hex cell run <id> --with-output`, diff the agent's SQL against your independent
  re-derivation from the `.twb`, run the mistake-class checklist + differential
  probes. Full procedure → [`sql-review.md`](sql-review.md). The gate reviews
  *whoever* wrote the SQL — post-hoc on the agent's cells is a first-class use.
- **Trace panels via the React code when needed** — the Generative app's
  `genAppFiles` (`App.js`, `lib/theme.js`) show which cell/column each panel reads
  and the exact colors/formats; grep them to locate *which* derivation a wrong
  panel is pointed at. It's a debugging aid, not the verification.
- **Fix divergences** — either `hex thread continue <id> "<name the exact
  divergence>"`, or edit the cell directly (YAML / `hex cell update`) when a
  surgical fix is faster than another agent round-trip.
- **Visual parity** — export the original's PNGs with `scripts/tableau_shots.py`
  and compare the Tableau and Hex dashboards **panel by panel**: chart type, axes,
  series and colors, layout order, number formats, tooltips. Seeing the rendered
  pixels is the only check that catches a panel reading the right data but plotting
  it wrong (a cumulative line vs a per-day line — same numbers, different picture).
  The Generative app renders behind a login the CLI can't pass (never enter
  credentials), so capture the Hex side with a **headless browser signed in once**
  (the session persists for later automated rounds), or have the customer confirm
  the side-by-side. Fix discrepancies with `hex thread continue` and re-check.

## Cheat-sheet

- `hex thread create "<prompt>" --project <id> --json` → `url` (hand to customer) + `thread_id`.
- `hex thread get <id>` → `Status: RUNNING｜IDLE`; `hex thread messages <id>` → its reasoning.
- `hex thread continue <id> "<prompt>"` → iterate.
- Needs the headless-agent-threads feature enabled for the workspace. Uses Hex credits.
