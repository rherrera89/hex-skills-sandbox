# Optional: construct a governed Hex semantic model from LookML

The **default** semantic-layer deliverable is a Hex **guide** (headless, no
prerequisites — see [`datasource-guide.md`](datasource-guide.md)). This is the
**optional, higher-fidelity** path: rebuild the LookML as a governed Hex
**semantic model** (`type: model` / `type: view`) the notebook agent and Threads
query directly. LookML *is* a semantic model, so the mapping is nearly 1:1.

> ⚠️ **Prerequisite (not headless):** `hex context` only *populates* an **existing**
> semantic project — no `hex` command creates one. The customer must create an empty
> project in the UI first and give you its **UUID** (see [publish flow](#publish-flow-hex-context)).
> Not willing? Stop here and ship the guide.

## The mapping: LookML → Hex semantic YAML

Multi-document YAML (`---`-separated); each document is one resource keyed by
`type`: **`model`** (dimensions + measures + relations — the LookML *view* analog)
or **`view`** (an optional curated facade — the LookML *explore* analog). Worked
example: [`templates/semantic-model.example.yaml`](../templates/semantic-model.example.yaml).
Full field list, enums, and validation rules: the Hex
[**modeling specification**](https://learn.hex.tech/docs/connect-to-data/semantic-models/semantic-authoring/modeling-specification)
— the table below is just the migration shortcut.

| LookML | Hex semantic YAML | Notes |
|---|---|---|
| `view: x { sql_table_name: DB.SCH.T }` | `type: model`, `base_sql_table: DB.SCH.T` | derived-table view → `base_sql_query: "<SQL>"` instead |
| `dimension: d { sql: ${TABLE}.col ;; type: string }` | `dimensions[]` entry `{id: d, type: string}`; add `expr_sql: col` when id ≠ column | types: `string` / `number` / `date` / `timestamp_tz` / `timestamp_naive` / `boolean` / `other` |
| `primary_key: yes` | `unique: true` on that dimension | **≥1 required per model** |
| `hidden: yes` | `visibility: internal` | `visibility` ∈ `public` (default) / `internal` / `private` |
| `dimension_group: time` (many timeframes) | **one** date/timestamp dimension | Hex truncates at query time — don't emit one dim per timeframe; keep `_month`/`_quarter` legacy copies as `visibility: internal` and warn against them |
| `measure { type: sum, sql: ${x} }` | `{id, func: sum, of: x}` | `func` ∈ `count` (no `of`), `count_distinct`, `sum`, `avg` (**not** `average`), `median`, `min`, `max`, `stddev`/`stddev_pop`, `variance`/`variance_pop` |
| filtered measure (`filters:` on a measure) | native `{func: sum, of: x, filters: [is_won, ...]}` — or `func_sql: "SUM(CASE WHEN … END)"` | `filters` takes boolean dimensions and maps ~1:1; `func_sql` for anything more complex |
| ratio of measures (`type: number, sql: ${a}/${b}`) | `{type: number, func_sql: "${a} / NULLIF(${b}, 0)"}` | ratio of **measures**, never `AVG(a/b)`; guard the divide |
| `${field}` / `${other_view.field}` refs | `${dimension}` / `${other_model.measure}` | cross-model refs resolve through a `relation` |
| `explore.join { sql_on: A=B ;; relationship: many_to_one }` | `relations[]` entry `{id: <target model>, type: many_to_one, join_sql: "${A} = ${<relation>.B}"}` | `type` ∈ `many_to_one` / `one_to_many` / `one_to_one` **only — no `many_to_many`** (decompose via a bridge model or pre-aggregate; see [`lookml-semantics.md`](lookml-semantics.md)). `id` defaults to target model id; set `target` if they differ |
| `explore: e { ... joins ... }` | `type: view` `{base: <base model>, contents: [...]}` | curated entry point; see below |
| `value_format_name` / `value_format` | **not** a model construct | number formatting rides on the chart cell — see [`building-cells.md`](building-cells.md) |
| `access_filter` / user-attribute Liquid | **not** a model construct | RLS → Hex Jinja RBAC in the notebook — see [`lookml-semantics.md`](lookml-semantics.md) §6 |

**The `view`.** `base:` model + `contents:` groups. A base-model group lists
dimensions/measures by id; a related-model group uses `- relation: <id>` (dot-path
for multi-hop, e.g. `orders.customers`). Shortcuts: `...` = all fields, `~field_id`
excludes one, `{dimension: id, name: "…"}` renames. Views are optional — models
carry all analytical capability. Map one view per LookML explore.

**Beyond the 1:1 mapping** (see the spec for detail): `id` rules (2–128 chars,
lowercase/`_`/digits, no reserved names like `this`/`model`/`view`); `base_sql_query`
for derived tables; `expr_calc`/`func_calc` for Hex-formula (non-SQL) fields;
`semi_additive` for balance-style measures. Absent by design: number formatting,
synonyms, `access_grant`s, PDTs.

**Fidelity:** preserve LookML `description`s verbatim — they carry the agent's
"prefer this field" / "don't truncate this legacy column" guidance. After
publishing, spot-check each metric against the same warehouse `SELECT` (and Looker's
value via `looker_fetch.py query`) — same numeric-parity discipline as the SQL gate.

## Publish flow (`hex context`)

Syncs a **local directory of semantic YAML → an existing semantic project** via
`hex_context.config.json`. Team/Enterprise-only; needs a workspace token
(`HEX_API_TOKEN`); synced resources are **read-only in Hex** (edit in the repo). Not
for Snowflake Semantic Views or Databricks Metric Views. Reference:
[Context Sync](https://learn.hex.tech/docs/agent-management/context-management/context-sync).

1. **Customer creates the empty project** and sends its **UUID** — Context Studio →
   Models → the row → ⋯ → "Copy ID". Must be the UUID, not the SQL identifier;
   a nonexistent id → `Forbidden`.

2. **Write models + view** to a dir and a config at the repo root:
   ```json
   {
     "semanticProjects": [{ "id": "<UUID>", "path": "models/" }]
   }
   ```
   Key is **`semanticProjects`** (each `{id, path}`), *not* `semanticModels`. `guides`
   can share the config (`{pattern, transform:{stripFolders}}` or `{path, hexFilePath}`).

3. **Preview** (non-destructive — uploads a throwaway version, live project untouched):
   ```bash
   hex context preview --config-path ./hex_context.config.json [--base draft|latest]
   ```
   `--base`: `latest` (default) diffs against published state, `draft` against draft.
   Also `--title`/`--description` (seed the version, carried to publish), `--force`
   (overwrite conflicting guide files), `--json` (capture the preview id in CI).
   Smoke-test before publishing:
   `hex thread create "<prompt>" --new-project --preview-id <preview_id>`.

4. **Publish:**
   ```bash
   hex context publish <preview_id>   # or `-` for the last preview this session
   ```

> ⚠️ **Publish syncs and prunes by default** — the project's models are made to
> *match your local directory*. Use a **dedicated** project; treat the local dir as
> the source of truth (no partial-model merge). `--no-prune` only spares guides
> absent from the config. **Preview is always safe; publish mutates.**

## When to offer this vs. just the guide

Ship the **guide always** (headless, low effort, retrieved prose). Offer the
**semantic model** when the customer wants a real governed, queryable metrics layer
to replace LookML — and accepts the one-time project-creation step (medium effort:
author + validate YAML, create the project).
