# Tableau → Hex Migration Skill

A durable, portable [Claude Code](https://claude.com/claude-code) skill that migrates Tableau dashboards into Hex — fetch the workbook, parse its XML, map the data connection, and rebuild each worksheet as Hex SQL + native chart cells.

**The full playbook lives in [`SKILL.md`](SKILL.md).** That's the canonical doc Claude reads.

## Install (make it invocable)
Drop this folder into a Claude Code project's skills directory:
```bash
git clone git@github.com:rherrera89/hex-skills.git
cp -r hex-skills/tableau-migration /path/to/project/.claude/skills/tableau-migration
```
Then invoke it in Claude Code with `/tableau-migration`, or just ask to "migrate my Tableau dashboards to Hex" — the `description` frontmatter triggers it.

## First-time setup
1. `cp credentials/tableau.env.example credentials/tableau.env` and fill in your Tableau **pod URL**, **site**, and **Personal Access Token**. (Gitignored — never commit it.)
2. Install the [Hex CLI](https://hex.tech/product/cli) and authenticate.
3. Know which **Hex data connection** the migrated cells should query.

## What's in here
| Path | What |
|------|------|
| `SKILL.md` | The playbook (workflow, connection mapping, templates, rules, batch loop) |
| `templates/` | Clone-and-override native Hex cell configs (METRIC, EXPLORE variants) |
| `scripts/tableau_fetch.py` | Fetch `.twb`/`.twbx` from Tableau Cloud/Server |
| `reference/hex-file-schema.json` | Hex file JSON Schema (validate before import) |
| `credentials/` | `tableau.env.example` (copy → `tableau.env`, gitignored) |
| `tableau_exports/`, `working/` | Local downloads + scratch (gitignored) |

## How to use it (short version)
0. **Prioritize & organize** the customer's dashboards into one folder — migrate what's used, drop the dead weight.
1. **Pilot 1–2 dashboards** end-to-end, QA against the Tableau originals, tune.
2. **Batch the rest** with the folder loop + `migrations.json` manifest.

See [`SKILL.md`](SKILL.md) for each step in full.
