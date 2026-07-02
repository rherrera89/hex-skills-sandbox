# hex-skills

Claude Code skills for [Hex](https://hex.tech). Each subfolder is a self-contained, invocable skill — drop it into a project's `.claude/skills/` directory.

## Skills

| Skill | What it does |
|-------|--------------|
| [`tableau-migration/`](tableau-migration/) | Migrate Tableau dashboards into Hex — fetch `.twb`/`.twbx`, parse the XML, map the data connection, and rebuild each worksheet as Hex SQL + native chart cells. Includes a prioritize→pilot→batch workflow and a clone-and-override native-cell template library. |

## Using a skill
```bash
git clone git@github.com:rherrera89/hex-skills.git
cp -r hex-skills/<skill-name> /path/to/project/.claude/skills/<skill-name>
```
Then invoke it in Claude Code with `/<skill-name>`, or just describe the task — each skill's `description` frontmatter triggers it automatically. See each skill's own `README.md` / `SKILL.md` for setup.
