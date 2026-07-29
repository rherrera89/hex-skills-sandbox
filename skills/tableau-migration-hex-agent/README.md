# Tableau → Hex Migration Skill (notebook-agent build)

A durable, portable **agent skill** that migrates Tableau dashboards into Hex by **delegating the build to Hex's in-product notebook agent**. This coding agent parses the workbook and writes a precise **migration brief**; Hex's notebook agent — which can see the live warehouse schema and the customer's workspace context — builds the SQL + parameters + a **Hex Generative app** (React app on top of the SQL cells); then this agent verifies with a **SQL-fidelity gate**. It's a standard [Agent Skill](https://vercel.com/docs/agent-resources/skills), so it works with any terminal coding agent (Codex, Cursor, Claude Code, …) — see the [repo README](../../README.md#using-with-other-agents-codex-cursor-) for multi-agent install.

**Why delegate the build:** this coding agent is blind to the warehouse schema, the data, and the rendered result; the notebook agent sees all three. So for building *in Hex* it's the better-equipped agent. This coding agent's durable job is **understanding the Tableau source** (reading the XML, translating calcs/LOD/table-calcs/filters/params into a brief) and **verifying the result** (the gate). A **build-path gate** lets the customer choose: **A** delegate the whole build (default, Hex credits), **B** pre-build + gate the SQL then delegate the viz, or **C** this agent hand-builds everything (fallback — spends the customer's model-subscription tokens, and builds blind).

> **Sibling skill:** [`tableau-migration`](../tableau-migration) is the hand-build-first variant (this coding agent builds the native cells). This skill (`tableau-migration-hex-agent`) is the delegation-first variant. They share the same Tableau-parsing + fidelity-gate core.

**The full playbook lives in [`SKILL.md`](SKILL.md).** That's the canonical doc the agent reads.

## Install (make it invocable)
From the project you want it in:
```bash
npx skills add rherrera89/hex-skills-sandbox --skill tableau-migration-hex-agent
```
Or with the bundled installer:
```bash
curl -fsSL https://raw.githubusercontent.com/rherrera89/hex-skills-sandbox/main/install.sh | bash -s -- tableau-migration-hex-agent
```
Either drops the skill into your agent's skills directory (secrets and local scratch are never copied). Then invoke it via your agent (e.g. a `/tableau-migration-hex-agent` command), or just ask to "migrate my Tableau dashboards to Hex with the notebook agent" — the `description` frontmatter triggers it. For Codex, Cursor, and other agents, see the [repo README](../../README.md#using-with-other-agents-codex-cursor-).

## First-time setup
1. `cp credentials/tableau.env.example credentials/tableau.env` and fill in your Tableau **pod URL**, **site**, and **Personal Access Token**. (Gitignored — never commit it.)
2. Install the [Hex CLI](https://hex.tech/product/cli) and authenticate.
3. Know which **Hex data connection** the migrated cells should query, and ensure the **headless-agent-threads feature** is enabled (the default build uses `hex thread`).

## What's in here
| Path | What |
|------|------|
| `SKILL.md` | The playbook — workflow spine (the agent reads this to run a migration) |
| `reference/` | On-demand detail: `connection-mapping.md`, `tableau-semantics.md` (understand the workbook), `build-notebook-agent.md` (**the default build** — brief + delegation), `sql-review.md` (SQL-fidelity gate), `building-cells.md` (hand-build fallback), `datasource-guide.md`, `gotchas.md` |
| `tableau-zoo/` | The "Tableau Zoo" — regression fixtures (`.twb` inputs + parity ground truth + Hex goldens) |
| `templates/` | Clone-and-override native Hex cell configs for the **fallback** hand-build (METRIC, EXPLORE variants) |
| `scripts/tableau_fetch.py` | Fetch `.twb`/`.twbx` from Tableau Cloud/Server |
| `scripts/tableau_shots.py` | Export PNGs of a workbook's dashboard + worksheets for visual QA |
| `credentials/` | `tableau.env.example` (copy → `tableau.env`, gitignored) |
| `tableau_exports/`, `working/` | Local downloads + scratch (gitignored) |

## How to use it (short version)
0. **Prioritize & organize** the customer's dashboards into one folder — migrate what's used, drop the dead weight.
1. **Pilot 1–2 dashboards** end-to-end: parse → brief → notebook-agent build → SQL-fidelity gate → QA against the Tableau originals, tune.
2. **Batch the rest** with the folder loop + `migrations.json` manifest.

See [`SKILL.md`](SKILL.md) for each step in full.
