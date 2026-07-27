# Extraction front-end: looker-cooker (Phase 1 source-of-truth)

The fastest, most complete way to get everything **out** of Looker is
**[looker-cooker](https://github.com/nick-at/looker-cooker)** (MIT, by Nick
Thompson) — a CLI that produces a resumable, whole-instance backup. Run it first;
the rest of this skill's pipeline consumes its output as the **source of truth**.

Why it's the right front-end: LookML alone needs a running Looker to mean
anything. looker-cooker resolves the abstraction — it emits the **compiled SQL**
(joins, derived tables, filter logic all resolved) and a **rendered screenshot**
for every dashboard, which is exactly what a migration needs and what a
per-dashboard fetch can't give you in bulk.

## What it produces (the artifact contract the pipeline reads)

```
looker_backup_output/
  dashboards/
    Revenue_Overview__42/
      metadata.json      # full dashboard definition from the API (tiles, filters, layout)
      dashboard.lookml   # LookML export where available
      screenshot.png     # rendered dashboard (render API, Playwright fallback for broken tiles)
      queries.sql        # compiled warehouse SQL for every tile
  looks/
    42_Monthly_Revenue.json   # full look definition
    42_Monthly_Revenue.sql    # compiled SQL
  manifest.json          # progress tracker; re-runs resume where they left off
```

How each artifact feeds the pipeline:

| Artifact | Used in | For |
|---|---|---|
| `metadata.json` | Step 0 inventory; Phase 1 planning | the tile/filter/layout facts (same shape `looker_fetch.py dashboard` normalizes) — inventory, clustering, chart specs |
| `dashboard.lookml` + view `.lkml` | Phase 1 ([`lookml-semantics.md`](lookml-semantics.md)) | resolve fields → `sql:`, measures, joins, `sql_always_where` |
| `queries.sql` | Phase 1 + 1.5 | **the compiled-SQL reference** — port/repoint this instead of reverse-engineering (replaces the per-query `looker_fetch.py sql`) |
| `screenshot.png` | Step 0; visual QA (step 7); notebook-agent prompt | the **rendered source image** — see "Screenshots change the visual gate" below |
| `manifest.json` | batch loop | resumability; mirror its status into `migrations.json` |

## Install & run

```bash
pip install git+https://github.com/nick-at/looker-cooker.git   # or clone + `pip install .`
playwright install chromium                                    # required for the screenshot fallback

# credentials: a .env with LOOKERSDK_BASE_URL / LOOKERSDK_CLIENT_ID / LOOKERSDK_CLIENT_SECRET
# (same API3 key as looker_fetch.py; looker-cooker uses the LOOKERSDK_* names)

looker-cooker --limit 5 --verbose        # pilot: test on a handful first
looker-cooker --dashboard-id <ID>        # a single dashboard (scope to the migration shortlist)
looker-cooker                            # full instance
looker-cooker --no-sql                   # metadata + screenshots only (faster)
looker-cooker --backfill-sql             # add compiled SQL to an existing backup
```

Scope it to the **shortlist** from Step 0 (`--dashboard-id` per target, or `--limit`
on a pilot) — you don't need to cook the whole instance to migrate a wave. It's
idempotent; re-run to retry failures, `--force` to redo.

## Division of labor with `looker_fetch.py` (keep both)

looker-cooker is the **bulk extract**; `looker_fetch.py` covers the two things it
doesn't:

| Need | Tool |
|---|---|
| Bulk metadata + LookML + **compiled SQL** + **screenshots**, resumable | **looker-cooker** |
| **Connection dialect / database** (for connection mapping) | `looker_fetch.py connection <name>` |
| **Reference result VALUES** for the numeric-parity gate | `looker_fetch.py query <spec>` — looker-cooker pulls compiled SQL + screenshots, **not** result rows, so this remains the parity oracle ([`sql-review.md`](sql-review.md) §4a) |
| Quick ad-hoc list / explore field graph | `looker_fetch.py list-* / explore` |

So: **looker-cooker to extract, `looker_fetch.py query` to check the numbers.**

## Screenshots change the visual gate

The rest of this skill was written assuming "the agent is blind to rendered
output." With looker-cooker's `screenshot.png` that's no longer fully true:

- **Coding agent (Phase 2 option A):** read the source `screenshot.png`, then read
  a screenshot of the built Hex app, and compare tile-for-tile. The human visual-QA
  sign-off still matters, but the agent can now catch obvious layout/chart-kind/format
  mismatches itself instead of shipping blind.
- **Notebook agent (Phase 2 option B):** the source screenshot is strong context for
  the `hex thread` prompt ("match this layout"), and a before/after check afterward.
- **Step 0:** eyeballing screenshots is the fastest way to spot dead/duplicate
  dashboards during prioritization.

> **Credentials & security.** looker-cooker uses the same Looker API3 key as this
> skill (via `LOOKERSDK_*` env vars / its own `.env`). Prefer a read-only service
> account. The backup contains real business data — treat the output dir
> accordingly and keep it out of git (this skill's `.gitignore` already excludes
> `looker_exports/` and `working/`; point `--output-dir` at one of those or another
> gitignored path).

## Attribution

[looker-cooker](https://github.com/nick-at/looker-cooker) — MIT License, © Nick
Thompson. Referenced (installed from source), not vendored, so it tracks upstream.
