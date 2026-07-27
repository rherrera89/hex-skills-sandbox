# Looker → Hex Migration Skill

A durable, portable **agent skill** that migrates Looker dashboards and Looks into Hex — discover content over the Looker REST API 4.0, resolve the LookML model's connection to a Hex data connection, port Looker's generated SQL + LookML calc logic to warehouse SQL, and rebuild the dashboard in Hex. Fully **headless** (CLI-driven). It's a standard [Agent Skill](https://vercel.com/docs/agent-resources/skills), so it works with any terminal coding agent (Codex, Cursor, Claude Code, …).

The **viz build-out is a choice** the customer makes: the coding agent hand-builds the cells (spends their frontier-model subscription tokens, no Hex credits), or Hex's **notebook agent** builds them via `hex thread` (better-looking dashboards, spends Hex credits). The accuracy layer — connection mapping, LookML→SQL translation, and the numeric-parity fidelity gate — is always the coding agent's job.

**The full playbook lives in [`SKILL.md`](SKILL.md).** That's the canonical doc the agent reads.

> ⚠️ **Status: untested against a live Looker instance.** The skill is written to the documented Looker REST API 4.0 (auth, `GET /dashboards/{id}`, `POST /queries/run/{sql,json}`, `GET /connections`, `GET /lookml_models`), but the fetch script and API-shape assumptions have **not** been run end-to-end against a real Looker license yet. Treat the first live run as a validation pass and fold fixes back in.

## Two layers, two conversions
Looker has two independent layers; the skill converts them separately:

| Layer | Source (production = API-first) | Becomes in Hex |
|---|---|---|
| **Semantic model** | LookML views + model + explores (Looker API, or `.lkml` files offline) | shared SQL cells + a Hex **guide** (the semantic layer, headless) |
| **Dashboards / Looks** | `GET /dashboards/{id}` / `GET /looks/{id}` — **user-defined (UDD) AND LookML**, same JSON | a Hex project: SQL + native chart/KPI cells + app layout |

**UDD is the primary path** — most real dashboards are user-defined (in no `.lkml` file) and reachable only via the API.

**Extraction front-end:** the skill uses **[looker-cooker](https://github.com/nick-at/looker-cooker)** (MIT) to bulk-extract the instance — per dashboard: `metadata.json`, `dashboard.lookml`, **`screenshot.png`**, and **`queries.sql`** (compiled SQL), resumable. The screenshots mean the agent isn't blind to layout — it self-checks the built Hex app against the rendered source. `looker_fetch.py` complements it for connection dialect + reference result values (the numeric-parity oracle looker-cooker doesn't provide). See [`reference/extraction.md`](reference/extraction.md).

## Looker hands you the SQL and the numbers
Looker will hand you both the **generated SQL** (`looker_fetch.py sql` → `POST /queries/run/sql`) and the **actual result values** (`looker_fetch.py query` → `POST /queries/run/json`) over the API. So Phase 1 ports Looker's own SQL rather than reconstructing it, and the Phase-1.5 SQL-fidelity gate gets a real **numeric parity oracle** — a direct value check against Looker's own answers.

## Install (make it invocable)
From the project you want it in:
```bash
npx skills add rherrera89/hex-skills-sandbox --skill looker-migration
```
Then invoke it via your agent (e.g. a `/looker-migration` command), or just ask to "migrate my Looker dashboards to Hex" — the `description` frontmatter triggers it.

## First-time setup
1. `cp credentials/looker.env.example credentials/looker.env` and fill in your Looker **base URL** + **API3 client_id/secret** (or use `~/.looker/looker.ini`). Gitignored — never commit it.
2. Install the [Hex CLI](https://hex.tech/product/cli) and authenticate.
3. Install the extractor: `pip install git+https://github.com/nick-at/looker-cooker.git && playwright install chromium` (uses the same Looker API3 key via `LOOKERSDK_*` env vars).
4. Know which **Hex data connection** the migrated cells should query.
5. Smoke-test: `python3 scripts/looker_fetch.py whoami` and `looker-cooker --limit 2 --output-dir working/`.

## What's in here
| Path | What |
|------|------|
| `SKILL.md` | The playbook — lean workflow spine (the agent reads this to run a migration) |
| `reference/` | On-demand detail: `extraction.md` (Phase 1 front-end: looker-cooker), `connection-mapping.md`, `lookml-semantics.md` (Phase 1: LookML → SQL/Python + consolidation), `sql-review.md` (Phase 1.5: SQL-fidelity gate + numeric parity), `building-cells.md` (Phase 2 option A: coding agent builds cells), `datasource-guide.md` (headless guide), `gotchas.md` |
| `templates/` | Clone-and-override native Hex cell configs (METRIC, EXPLORE variants) |
| `scripts/looker_fetch.py` | Looker REST API 4.0 client — `whoami` / `list-*` / `connection` / `explore` / `dashboard` / `look` / `sql` / `query` / `raw` |
| `credentials/` | `looker.env.example` (copy → `looker.env`, gitignored) |
| `looker_exports/`, `working/` | Local downloads + scratch (gitignored) |

## How to use it (short version)
0. **Prioritize & organize** the customer's dashboards into one shortlist — migrate what's used (Looker's System Activity gives real usage), drop the dead weight.
1. **Pilot 1–2 dashboards** end-to-end, QA against the Looker originals (numbers via the API, layout by eye), tune.
2. **Batch the rest** with the id-list loop + `migrations.json` manifest.

See [`SKILL.md`](SKILL.md) for each step in full.
