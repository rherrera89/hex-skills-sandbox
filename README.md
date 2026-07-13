# hex-skills

Claude Code skills for [Hex](https://hex.tech). Each skill lives in `skills/<name>/` as a self-contained, invocable unit — drop it into a project's `.claude/skills/` directory.

## Skills

| Skill | What it does |
|-------|--------------|
| [`tableau-migration`](skills/tableau-migration/) | Migrate Tableau dashboards into Hex — fetch `.twb`/`.twbx`, parse the XML, map the data connection, and rebuild each worksheet as Hex SQL + native chart cells. Includes a prioritize→pilot→batch workflow and a clone-and-override native-cell template library. |

## Install a skill

With the [`skills` CLI](https://github.com/vercel-labs/skills) — no clone needed:
```bash
npx skills add rherrera89/hex-skills-sandbox                      # install all skills
npx skills add rherrera89/hex-skills-sandbox --list               # see what's available
npx skills add rherrera89/hex-skills-sandbox --skill tableau-migration
```

Or with the bundled installer:
```bash
# straight from GitHub
curl -fsSL https://raw.githubusercontent.com/rherrera89/hex-skills-sandbox/main/install.sh | bash -s -- tableau-migration

# or from a clone
./install.sh                          # list available skills
./install.sh tableau-migration        # install into the current project
./install.sh tableau-migration ~/proj # ...or a specific project
```

Both drop the skill into `.claude/skills/<name>/` and never copy secrets or local scratch (`tableau.env`, `tableau_exports/`, `working/`). Then invoke it in Claude Code with `/<skill-name>`, or just describe the task — each skill's `description` frontmatter triggers it automatically. See each skill's own `README.md` / `SKILL.md` for setup.
