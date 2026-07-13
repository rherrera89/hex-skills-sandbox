# hex-skills

Agent skills for [Hex](https://hex.tech). Each skill lives in `skills/<name>/` as a self-contained, invocable unit — a standard [Agent Skill](https://vercel.com/docs/agent-resources/skills) (`SKILL.md` + resources), so it works with any terminal coding agent, not just one.

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

Or with the bundled installer (drops into `.claude/skills/`):
```bash
# straight from GitHub
curl -fsSL https://raw.githubusercontent.com/rherrera89/hex-skills-sandbox/main/install.sh | bash -s -- tableau-migration

# or from a clone
./install.sh                          # list available skills
./install.sh tableau-migration        # install into the current project
./install.sh tableau-migration ~/proj # ...or a specific project
```

Neither copies secrets or local scratch (`tableau.env`, `tableau_exports/`, `working/`). Once installed, invoke the skill via your agent (e.g. a `/tableau-migration` command) or just describe the task — the skill's `description` frontmatter triggers it. See each skill's own `README.md` / `SKILL.md` for setup.

## Using with other agents (Codex, Cursor, …)

These are standard Agent Skills, not tied to any one tool. The `skills` CLI installs to the right location for whichever agent you name with `-a` — it supports **Codex, Cursor, Claude Code, OpenCode, and 70+ others**:
```bash
npx skills add rherrera89/hex-skills-sandbox --skill tableau-migration -a codex        # OpenAI Codex CLI
npx skills add rherrera89/hex-skills-sandbox --skill tableau-migration -a cursor       # Cursor
npx skills add rherrera89/hex-skills-sandbox --skill tableau-migration -a claude-code  # Claude Code
```
You can target several at once (`-a codex -a cursor`). For an agent that doesn't auto-load skills, just point it at [`skills/tableau-migration/SKILL.md`](skills/tableau-migration/) — e.g. reference it from your `AGENTS.md` — and it reads as a plain instruction file. The skill body is agent-neutral: it says "the Agent", runs standard shell + the Hex CLI, and carries its own templates and scripts.
