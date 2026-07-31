# Tableau → Hex Migration Skill (generative-app build)

A durable, portable **agent skill** that migrates Tableau dashboards into Hex by **delegating the build to Hex's in-product notebook agent**. This coding agent parses the workbook and writes a precise **migration brief** + **styling spec**; Hex's notebook agent — which can see the live warehouse schema and the customer's workspace context — builds a **generative app** on a natively-gated SQL data layer; then this agent verifies with a **SQL-fidelity gate** (on the SQL) and a **visual-QA loop** (on the render). It's a standard [Agent Skill](https://vercel.com/docs/agent-resources/skills), so it works with any terminal coding agent (Codex, Cursor, Claude Code, …) — see the [repo README](../../README.md#using-with-other-agents-codex-cursor-) for multi-agent install.

**The deliverable is a generative app** — a bespoke code app that reproduces Tableau's layout, tab navigation, and pixel styling far closer than native EXPLORE/METRIC cells, while the numbers stay in inspectable, gated SQL cells underneath (the app reads those dataframes; it never re-queries). The render is verified by a headless screenshot-diff loop against the original.

**Why delegate the build:** this coding agent is blind to the warehouse schema, the data, and the rendered result; the notebook agent sees all three. So for building *in Hex* it's the better-equipped agent. This coding agent's durable job is **understanding the Tableau source** (reading the XML, translating calcs/LOD/table-calcs/filters/params into the brief) and **verifying the result** (the two gates). The SQL under the app is gated whether the agent wrote it (post-hoc gate) or you pre-built it (gated first, for subtle-population workbooks). **Hand-building native cells is a fallback only** — used when the notebook agent isn't available (feature off / no Hex credits).

> **Supersedes the earlier hand-build-first variant.** This skill was previously published as `tableau-migration-hex-agent`; it has taken over the `tableau-migration` name. The original hand-build-first skill is retired to [`archive/tableau-migration-handbuild/`](../../archive/tableau-migration-handbuild/) — the hand-build path survives here only as a fallback (see the build-path gate in `SKILL.md`).

**The full playbook lives in [`SKILL.md`](SKILL.md).** That's the canonical doc the agent reads.

## Install (make it invocable)
From the project you want it in:
```bash
npx skills add rherrera89/hex-skills-sandbox --skill tableau-migration
```
Or with the bundled installer:
```bash
curl -fsSL https://raw.githubusercontent.com/rherrera89/hex-skills-sandbox/main/install.sh | bash -s -- tableau-migration
```
Either drops the skill into your agent's skills directory (secrets and local scratch are never copied). Then invoke it via your agent (e.g. a `/tableau-migration` command), or just ask to "migrate my Tableau dashboards to Hex" — the `description` frontmatter triggers it. For Codex, Cursor, and other agents, see the [repo README](../../README.md#using-with-other-agents-codex-cursor-).

## First-time setup
1. `cp credentials/tableau.env.example credentials/tableau.env` and fill in your Tableau **pod URL**, **site**, and **Personal Access Token**. (Gitignored — never commit it.)
2. Install the [Hex CLI](https://hex.tech/product/cli) and authenticate.
3. Know which **Hex data connection** the migrated cells should query, and ensure the **headless-agent-threads feature** is enabled (the default build uses `hex thread`).

## What's in here
| Path | What |
|------|------|
| `SKILL.md` | The playbook — workflow spine (the agent reads this to run a migration) |
| `reference/` | On-demand detail: `connection-mapping.md`, `tableau-semantics.md` (understand the workbook), `build-generative-app.md` (**the default build** — Generative app), `build-notebook-agent.md` (brief + handoff mechanics), `visual-qa-loop.md` (render gate), `sql-review.md` (SQL-fidelity gate), `building-cells.md` (**fallback only** — hand-build native cells), `datasource-guide.md`, `gotchas.md` |
| `tableau-zoo/` | The "Tableau Zoo" — regression fixtures (`.twb` inputs + parity ground truth + Hex goldens) |
| `templates/` | Clone-and-override native Hex cell configs for the **fallback** hand-build (METRIC, EXPLORE variants) |
| `scripts/tableau_fetch.py` | Fetch `.twb`/`.twbx` from Tableau Cloud/Server |
| `scripts/tableau_shots.py` | Export PNGs of a workbook's dashboard + worksheets for visual QA |
| `scripts/hex_shots.py` | Headless Playwright screenshot of the built Hex app (visual-QA loop) |
| `credentials/` | `tableau.env.example` (copy → `tableau.env`, gitignored) |
| `tableau_exports/`, `working/` | Local downloads + scratch (gitignored) |

## How to use it (short version)
0. **Prioritize & organize** the customer's dashboards into one folder — migrate what's used, drop the dead weight.
1. **Pilot 1–2 dashboards** end-to-end: parse → brief + styling spec → gate the SQL → notebook-agent builds the **generative app** → SQL-fidelity gate + visual-QA loop against the Tableau originals, tune.
2. **Batch the rest** with the folder loop + `migrations.json` manifest.

See [`SKILL.md`](SKILL.md) for each step in full.
