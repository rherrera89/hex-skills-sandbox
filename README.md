# hex-skills

Agent skills that migrate your BI dashboards into [Hex](https://hex.tech). Point one at your existing **Tableau** or **Looker** content and it rebuilds each dashboard in Hex — reading the source as the source of truth, mapping your data connection, translating the SQL, and **checking every number against the original before anything ships.**

Each skill lives in `skills/<name>/` as a self-contained [Agent Skill](https://vercel.com/docs/agent-resources/skills) (`SKILL.md` + scripts + templates), so it runs in any terminal coding agent — Claude Code, Codex, Cursor, and 70+ others — not just one.

## Which skill do I need?

Pick by the tool you're migrating **from**:

- **Coming from Tableau** — `.twb`/`.twbx` files, or Tableau Cloud/Server views → **[`tableau-migration`](skills/tableau-migration/)**
- **Coming from Looker** — LookML models/explores, Looks, or dashboards → **[`looker-migration`](skills/looker-migration/)**

Both work the same way and share the same guarantees:

- **Prioritize → pilot → batch.** They start by helping you prune (most BI sites are 60–80% dead weight), migrate one or two dashboards end-to-end so you can QA them, then batch the rest.
- **Accuracy first, look-and-feel second.** Every migrated query is gated against the source numbers before it ships. The handful of features with no clean 1:1 in Hex (maps, exotic tooltips) are flagged up front, so "it isn't pixel-identical" is never a surprise.
- **Your data stays yours.** Nothing copies your credentials or downloaded content; the skills run locally through your own agent and the Hex CLI.

## Skills

| Skill | Migrates | What it builds | How accuracy is guaranteed |
|-------|----------|----------------|-----------------------------|
| **[`tableau-migration`](skills/tableau-migration/)** | Tableau `.twb`/`.twbx` files + Tableau Cloud/Server views | Delegates the build to Hex's in-product notebook agent, which produces a **generative app** on a natively-gated SQL layer — reproducing Tableau's bespoke layout and styling far closer than stock chart cells. (Hand-built native cells remain as a fallback.) | A **SQL-fidelity gate** on every query, plus a **visual-QA loop** that screenshots the built app and diffs it against the original dashboard panel by panel. |
| **[`looker-migration`](skills/looker-migration/)** | Looker LookML models/explores, Looks, and user-defined + LookML dashboards (via the Looker REST API) | Rebuilds each tile as native Hex SQL + chart cells. You choose who builds the visuals: your coding agent, or Hex's notebook agent. | A **SQL-fidelity gate** with a **numeric parity oracle** — Looker returns each tile's real SQL *and* its actual result rows over the API, so migrated numbers are diffed against the true values, not just sanity-checked. |

Both also ship a reusable **data-source guide** (a semantic layer for the migrated tables) so your team can keep asking questions in Hex after the dashboards land — not just view static charts.

## Install a skill

With the [`skills` CLI](https://github.com/vercel-labs/skills) — no clone needed:
```bash
npx skills add rherrera89/hex-skills-sandbox --list               # see what's available
npx skills add rherrera89/hex-skills-sandbox --skill tableau-migration    # or looker-migration
npx skills add rherrera89/hex-skills-sandbox                      # install all skills
```

Or with the bundled installer (drops into `.claude/skills/`):
```bash
# straight from GitHub
curl -fsSL https://raw.githubusercontent.com/rherrera89/hex-skills-sandbox/main/install.sh | bash -s -- tableau-migration

# or from a clone
./install.sh                          # list available skills
./install.sh looker-migration         # install into the current project
./install.sh looker-migration ~/proj  # ...or a specific project
```

Neither copies secrets or local scratch. Once installed, invoke the skill via your agent (e.g. a `/tableau-migration` or `/looker-migration` command) or just describe the task — the skill's `description` frontmatter triggers it. See each skill's own `README.md` / `SKILL.md` for setup (Tableau PAT or Looker API credentials, the Hex CLI, and the target data connection).

## Using with other agents (Codex, Cursor, …)

These are standard Agent Skills, not tied to any one tool. The `skills` CLI installs to the right location for whichever agent you name with `-a` — it supports **Codex, Cursor, Claude Code, OpenCode, and 70+ others**:
```bash
npx skills add rherrera89/hex-skills-sandbox --skill looker-migration -a codex        # OpenAI Codex CLI
npx skills add rherrera89/hex-skills-sandbox --skill looker-migration -a cursor       # Cursor
npx skills add rherrera89/hex-skills-sandbox --skill looker-migration -a claude-code  # Claude Code
```
You can target several at once (`-a codex -a cursor`). For an agent that doesn't auto-load skills, just point it at the skill's `SKILL.md` — e.g. reference it from your `AGENTS.md` — and it reads as a plain instruction file. The skill body is agent-neutral: it says "the Agent", runs standard shell + the Hex CLI, and carries its own templates and scripts.
