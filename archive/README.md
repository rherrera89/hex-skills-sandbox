# Archive

Retired skills, kept for reference. **Nothing here is installable** — the
`install.sh` / `npx skills add` resolvers only look under `skills/`, so archived
skills are not offered or copied.

## `tableau-migration-handbuild/`

The original **hand-build-first** Tableau → Hex migration skill: this coding agent
hand-built the native Hex cells (SQL + EXPLORE/METRIC/PIVOT) from a template
library. Retired 2026-07-31.

**Replaced by** the generative-app-first skill now at
[`skills/tableau-migration/`](../skills/tableau-migration/) (previously published as
`tableau-migration-hex-agent`), which delegates the build to Hex's notebook agent and
produces a generative app on a natively-gated SQL layer. The hand-build path didn't
disappear — it survives inside the new skill as an explicit **fallback** for when the
notebook agent isn't available (see that skill's `reference/building-cells.md`).

The `--skill tableau-migration` install command is unchanged and now delivers the new
skill.
