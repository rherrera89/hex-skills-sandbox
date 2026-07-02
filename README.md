# hex-skills

Claude Code skills for [Hex](https://hex.tech). Each subfolder is a self-contained, invocable skill — drop it into a project's `.claude/skills/` directory.

## Skills

| Skill | What it does |
|-------|--------------|
| [`tableau-migration/`](tableau-migration/) | Migrate Tableau dashboards into Hex — fetch `.twb`/`.twbx`, parse the XML, map the data connection, and rebuild each worksheet as Hex SQL + native chart cells. Includes a prioritize→pilot→batch workflow and a clone-and-override native-cell template library. |

## Install a skill

One line, straight from GitHub — installs into the current project's `.claude/skills/`:
```bash
curl -fsSL https://raw.githubusercontent.com/rherrera89/hex-skills/main/install.sh | bash -s -- tableau-migration
```

Or if you've cloned the repo:
```bash
./install.sh                          # list available skills
./install.sh tableau-migration        # install into the current project
./install.sh tableau-migration ~/proj # ...or a specific project
```

The installer copies the skill into `.claude/skills/<name>/` and never copies secrets or local scratch (`tableau.env`, `tableau_exports/`, `working/`). Then invoke it in Claude Code with `/<skill-name>`, or just describe the task — each skill's `description` frontmatter triggers it automatically. See each skill's own `README.md` / `SKILL.md` for setup.
