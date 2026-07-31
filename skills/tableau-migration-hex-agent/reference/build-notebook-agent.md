# Build via Hex's notebook agent — brief + handoff mechanics

The **shared mechanics** for the default build: how to write the **migration brief**,
inject it, hand the work to Hex's in-product notebook agent (`hex thread`), and
iterate. The default deliverable is a **Generative app** — this doc covers the brief
and the thread; the app-specific prompt, the `genAppFiles` verification, and the
styling spec live in [`build-generative-app.md`](build-generative-app.md). Use this
doc once you've parsed the workbook (Phase 1).

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

## Two ways to author the SQL layer

The presentation is always a Generative app; these differ only in **who first
authors the native SQL cells underneath it** (both end gated the same way):

- **Agent-built SQL (default).** You write the brief; the notebook agent builds the
  **SQL cells, the parameters, and the app**. You then run the fidelity gate
  **post-hoc** on the SQL it built (read its values, diff against the `.twb`).
  Simplest, and it leans fully on the agent's schema + context sight. Verified to
  reproduce correct, gated SQL from a good brief.
- **Pre-built SQL.** You build + gate the SQL cells first, then the agent builds the
  app on top of them. Choose this when the **data population is subtle** (aggressive
  shared filters, a fan-out risk, a relative-date window) and you want the numbers
  pinned and gated *before* any app work — see [`sql-review.md`](sql-review.md). It
  costs a YAML round-trip (`hex cell create` can't mint INPUT or dataframe-SQL
  companion cells — see [`gotchas.md`](gotchas.md)).

When unsure, default to **agent-built** and rely on the post-hoc gate; escalate to
**pre-built** for high-stakes or subtle-population workbooks. Either way, tell the
agent to build a Generative app that *reads* the SQL dataframes and never re-queries
([`build-generative-app.md`](build-generative-app.md)).

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
   ⚠️ **Wrap the brief body in `{% raw %}` … `{% endraw %}`.** Hex markdown cells
   Jinja-render `{{ }}` tokens, and a brief is full of them — `{{ param }}` intent
   notation, and often a literal empty `{{ }}` as an example. On `hex project run`
   the markdown cell tries to render and **ERRORs** on the stray Jinja (an empty
   `{{ }}` is a hard syntax error), failing the whole run even though every SQL cell
   is fine. `{% raw %}` tells Jinja to skip the block; the markdown still renders.
   (Seen live: an un-wrapped brief cell ERRORed the project run; the SQL was all
   clean.) Same rule for the styling spec cell.
   Also inject the **styling spec** the same way (also `{% raw %}`-wrapped). When the
   **agent builds the SQL**, attach the data connection to the project (a one-line
   seed SQL cell via `hex cell create --data-connection-id …` does this — the agent
   needs a connection to build SQL against). When you **pre-built the SQL**, the QA'd
   cells are already there.
2. **Start the thread with the generative-app prompt.** It **must open** with *"Build
   this as a GENERATIVE APP (App builder → Generative app), not a classic notebook"*
   and tell the agent to build the SQL derivations + params, then a Generative app
   that *reads those dataframes* (never re-queries), matching the styling spec. Full
   prompt template → [`build-generative-app.md`](build-generative-app.md). (Pre-built
   SQL: add *"the SQL cells already exist — use them as the data source, don't
   rewrite them."*)
3. **⚠️ Surface the live URL to the customer immediately.** `hex thread create
   --json` returns a `url`. Give it to them **as the build starts** so they can
   *watch the agent work in real time and stop/redirect it* if it drifts — the
   build runs several minutes and is otherwise a black box. Don't poll silently.
4. **Prompt framing decides the output *form* — there's no CLI flag.** Opening with
   "Build this as a GENERATIVE APP…" yields a custom app (`genAppFiles`); a loose or
   chart-type-prescriptive prompt yields classic native cells. Always **verify the
   form** after the build (`hex project export` → is `genAppFiles` non-empty?) and
   re-prompt if it built classic. Full detail → [`build-generative-app.md`](build-generative-app.md).
5. **Poll** `hex thread get <id>` until `Status: IDLE`; iterate with
   `hex thread continue <id> "<fix>"`.

## Verify + gate (always)

The build is not done until it's gated. The notebook agent is capable but still a
black box that can be confidently wrong — **verify, don't trust.**

- **Confirm what it built** — `hex project export`: `genAppFiles` non-empty (it's a
  Generative app, not classic), SQL cells present + (pre-built) unchanged, the app
  reads the right dataframes, params wired.
- **Run the SQL-fidelity gate on the SQL** — read every SQL cell's values with
  `hex cell run <id> --with-output`, diff the SQL against your independent
  re-derivation from the `.twb`, run the mistake-class checklist + differential
  probes. Full procedure → [`sql-review.md`](sql-review.md). The gate reviews
  *whoever* wrote the SQL — post-hoc on the agent's cells is a first-class use.
- **Fix divergences** — either `hex thread continue <id> "<name the exact
  divergence>"`, or edit the cell directly (YAML / `hex cell update`) when a
  surgical fix is faster than another agent round-trip.
- **Verify the render with the visual-QA loop** — headless screenshot → panel-by-panel
  diff vs. the source PNG → surgical fix batch → repeat, then a final human confirm.
  → [`visual-qa-loop.md`](visual-qa-loop.md).

## Cheat-sheet

- `hex thread create "<prompt>" --project <id> --json` → `url` (hand to customer) + `thread_id`.
- `hex thread get <id>` → `Status: RUNNING｜IDLE`; `hex thread messages <id>` → its reasoning.
- `hex thread continue <id> "<prompt>"` → iterate.
- Needs the headless-agent-threads feature enabled for the workspace. Uses Hex credits.
