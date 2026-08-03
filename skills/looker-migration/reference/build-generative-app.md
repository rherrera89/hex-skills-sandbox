# Build via a Hex Generative app (the default build)

The **default deliverable**: keep the data layer native and gated, then have the
notebook agent build a **Generative app** (a bespoke code/React app — `genAppFiles`
in the export) as the *presentation* layer on top of those cells. This is what lets
the migration reproduce Looker's dashboard layout, tile arrangement, and pixel
styling in a way native EXPLORE/METRIC cells can't — while the numbers stay in
inspectable, gated SQL. It pairs with the **visual-QA loop**
([`visual-qa-loop.md`](visual-qa-loop.md)) so the render is actually verified, not
punted to the human. (Hand-built native cells are the fallback for when the notebook
agent isn't available → [`building-cells.md`](building-cells.md).)

> **Division of labor is unchanged.** This coding agent still owns *understanding
> the Looker source* and *verifying the result*; the notebook agent still owns
> *building in Hex*. The generative-app form only changes **what** it builds
> (a bespoke app vs. native chart cells) — not who guarantees accuracy.

## The core principle: split the layers

A Generative app has **no diff-able native SQL cells** — its data logic can hide
inside the app code, which would gut the SQL-fidelity gate. So the generative layer
never authors SQL:

1. **Data layer — native + gated (this is your accuracy guarantee).** Build the SQL
   derivation cells (agent-built + gated post-hoc, or pre-built + gated first for
   subtle population), run the full **SQL-fidelity gate** on them
   ([`sql-review.md`](sql-review.md)) — including numeric parity against Looker's own
   values. These are ordinary, inspectable SQL cells.
2. **Presentation layer — generative.** The app *reads the existing dataframes*; it
   does not re-query. The prompt says so explicitly. The gate stays valid because
   the numbers live in the gated cells, and the app is pure presentation over them.

⚠️ **Never skip step 1.** "Just prompt for a generative app" produces an app that
generates its own SQL inside code you can't cleanly diff — that defeats the skill.
Gate the SQL, *then* generative-ize the presentation.

### Use Looker's generated SQL as a reference, not a paste

Unlike Tableau custom SQL, **do not lift Looker's generated SQL verbatim** into the
cell. `looker_fetch.py sql` returns SQL full of `LOOKER_SCRATCH` scratch-table names
and fully-expanded joins/PDTs — an opaque, unmaintainable paste. It's your **ground
truth for structure** (diff your translation against it), but the cell should port
the *logic* from the LookML (measures, `dimension_group` grains, join graph, filter
scopes) per [`lookml-semantics.md`](lookml-semantics.md). In the default build the
notebook agent writes that SQL against the live schema; you hand it *intent* (the
brief), not the generated paste. Either way the result is a native SQL cell that
goes through the gate.

---

## The styling spec (drives the prompt AND the diff baseline)

Before the build, distill the parse into a **styling spec** — one block per
dashboard section. It is both what the agent builds from and the ground truth the
visual-QA loop diffs against, so extract values, never eyeball them:

Per section:
- **Exact title + subtitle** (verbatim from the tile / `body_text`).
- **Metrics + definitions** — the derivation each tile reads and what it computes
  (the resolved LookML measure).
- **Filter wiring** — which inputs/params drive this tile (and any cross-filter).
- **Colors as hex codes** — pulled from `vis_config.series_colors` /
  `color_application` in the contract, **not** guessed from a screenshot.
- **Tooltip / label fields** — the measures shown and their formatted labels.
- **Time ranges** — the relative-date / date-range window, already translated
  (honor `week_start_day` / fiscal offsets).
- **Number + date formats** — from the measure's `value_format_name` /
  `value_format` (currency, %, decimals) + the `dimension_group` grain.

Keep it tight and factual — it's a spec, not prose. This is the same information the
brief already carries (see [`build-notebook-agent.md`](build-notebook-agent.md)
§"What the brief must contain"); the generative build just formalizes the
**styling** half into an extractable, diffable block because the visual loop leans
on it.

---

## The handoff prompt

App type is controlled by **prompt wording alone** — there is no CLI flag. The
prompt **must open** by demanding a Generative app, or the agent defaults to a
classic notebook:

> *"Build this as a **GENERATIVE APP** (App builder → Generative app), **not** a
> classic notebook app. Read the `Migration brief` + `Styling spec` cells — they are
> the full spec for migrating a Looker dashboard into this project.*
>
> *The SQL derivation cells already exist and are validated — **use them as the data
> source; do NOT write new SQL or re-query the warehouse.** The app reads these
> dataframes: `<df1>`, `<df2>`, …*
>
> *Build the presentation to match the Styling spec exactly: section titles,
> metrics, filter wiring, the given colors (hex codes), tooltip fields, time ranges,
> and number/date formats. Reproduce the source layout row-by-row. [If multiple
> dashboards:] use **tab navigation**, one tab per dashboard.*
>
> *Wire the input parameters to filter the app interactively per the spec."*

Hand it off:

```bash
hex thread create --new-project "$(cat prompt.txt)" --json   # or --project <id> if cells exist there
```

- **⚠️ Surface the returned `url` to the customer immediately** — the build runs
  several minutes; let them watch and redirect it live.
- **Multiple dashboards in scope → tab navigation** (one tab per source dashboard),
  named in the prompt.

## Verify it actually built a Generative app

The prompt is the only lever, so **confirm the form** post-build:

```bash
hex project export <project_id> -o app.yaml
```

- **`genAppFiles` present and non-empty** → it's a Generative app. ✅
- **`genAppFiles` missing / empty** (and you see EXPLORE/METRIC `cellType`s instead)
  → it built a classic notebook. Re-prompt:
  > *"Rebuild this as a Generative app (App builder → Generative app): move the
  > entire dashboard into the generative app. Do not leave it as classic notebook
  > cells."*
- **Confirm the split held** — the SQL cells are still present and **unchanged**
  (diff the export), and the app reads those dataframes rather than embedding its own
  queries. If the app authored SQL, `continue` it to read the existing cells instead.

## Verify accuracy + fidelity

Two gates, both mandatory:

1. **SQL-fidelity gate on the native cells** — runs on the inspectable SQL cells
   underneath the app, with numeric parity against Looker's own values.
   [`sql-review.md`](sql-review.md).
2. **Visual-QA loop on the render** — because there are no diff-able chart cells, the
   *rendered* app is how you verify look & feel. Headless screenshot →
   panel-by-panel diff vs. the source Looker PNG → surgical fix batch → repeat.
   [`visual-qa-loop.md`](visual-qa-loop.md). This replaces "punt to human visual QA"
   with an actual automated gate (the human still does a final confirm).

## When to fall back to native cells instead

The generative app is the default for every migration. Drop to the hand-built
native-cell path ([`building-cells.md`](building-cells.md)) **only** when the
notebook agent is unavailable — the headless-agent-threads feature is off, or there
are no Hex credits. That's a capability constraint, not a style preference: native
cells are the *fallback*, not an alternative you offer for "diff-ability." (The SQL
layer is diff-able and gated in both paths regardless — the difference is only the
presentation.) If the customer can't do the one-time screenshot login, you can still
ship the generative app; you just lose the automated render gate and fall back to a
side-by-side human visual QA.

## Cheat-sheet

- `hex thread create "$(cat prompt.txt)" --project <id> --json` → `url` (hand to customer) + `thread_id`. (`--new-project` also works if you haven't created one.)
- `hex project export <id> -o app.yaml` → check `genAppFiles` non-empty (Generative) and SQL cells unchanged; re-prompt if it built classic.
- `hex thread continue <id> "<numbered fix list>"` → iterate (drives both the form fix and the visual-QA loop).
- Data layer native + gated; app reads those dataframes, never re-queries.
