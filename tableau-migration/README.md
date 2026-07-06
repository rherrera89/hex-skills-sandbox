# Tableau → Hex Migration Skill

A durable, portable [Claude Code](https://claude.com/claude-code) skill that migrates Tableau dashboards into Hex — fetch the workbook, parse its XML, map the data connection, and rebuild each worksheet as Hex SQL + native chart cells.

**The full playbook lives in [`SKILL.md`](SKILL.md).** That's the canonical doc Claude reads.

## Install (make it invocable)
One line, from the project you want it in:
```bash
curl -fsSL https://raw.githubusercontent.com/rherrera89/hex-skills-sandbox/main/install.sh | bash -s -- tableau-migration
```
This drops the skill into `.claude/skills/tableau-migration/` (secrets and local scratch are never copied). Then invoke it in Claude Code with `/tableau-migration`, or just ask to "migrate my Tableau dashboards to Hex" — the `description` frontmatter triggers it.

## First-time setup
1. `cp credentials/tableau.env.example credentials/tableau.env` and fill in your Tableau **pod URL**, **site**, and **Personal Access Token**. (Gitignored — never commit it.)
2. Install the [Hex CLI](https://hex.tech/product/cli) and authenticate.
3. Know which **Hex data connection** the migrated cells should query.

## What's in here
| Path | What |
|------|------|
| `SKILL.md` | The playbook — lean workflow spine (Claude reads this to run a migration) |
| `reference/` | On-demand detail: `connection-mapping.md`, `tableau-semantics.md` (Phase 1: Tableau → SQL/Python + consolidation), `building-cells.md` (Phase 2: native charts + styling), `datasource-guide.md` (semantic-layer guide for Threads/agent), `gotchas.md` |
| `tableau-zoo/` | The "Tableau Zoo" — regression fixtures (`.twb` inputs + parity ground truth + Hex goldens) |
| `templates/` | Clone-and-override native Hex cell configs (METRIC, EXPLORE variants) |
| `scripts/tableau_fetch.py` | Fetch `.twb`/`.twbx` from Tableau Cloud/Server |
| `credentials/` | `tableau.env.example` (copy → `tableau.env`, gitignored) |
| `tableau_exports/`, `working/` | Local downloads + scratch (gitignored) |

## How to use it (short version)
0. **Prioritize & organize** the customer's dashboards into one folder — migrate what's used, drop the dead weight.
1. **Pilot 1–2 dashboards** end-to-end, QA against the Tableau originals, tune.
2. **Batch the rest** with the folder loop + `migrations.json` manifest.

See [`SKILL.md`](SKILL.md) for each step in full.
