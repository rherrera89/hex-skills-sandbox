# Optional: construct a governed Hex semantic model from LookML

The **default** semantic-layer deliverable is a Hex **guide** (headless, no
prerequisites — see [`datasource-guide.md`](datasource-guide.md)). This doc is the
**optional, higher-fidelity** path: rebuild the LookML as a governed Hex
**semantic model** (`type: model` / `type: view`) — an enforced metrics layer the
notebook agent and Threads query directly. Many ex-Looker teams will want this,
because LookML *is* a semantic model and the mapping is nearly 1:1.

> ⚠️ **One manual UI step, and it's not optional.** `hex context` (the CLI publish
> path) only **populates an existing** semantic project — it cannot create one, and
> there is no `hex` command that does. So the customer must first **create an empty
> semantic project in the Hex UI** and give you its **project id** (a UUID). A
> nonexistent id → `Forbidden`. Everything after that is CLI. If the customer
> doesn't want that step, stop here and ship the guide instead.

## The mapping: LookML → Hex semantic YAML

Hex semantic YAML is multi-document (`---`-separated); each document is one
resource identified by `type`. Two types: **`model`** (a table's dimensions +
measures + relations — the LookML *view* analog) and **`view`** (an optional
curated facade selecting a subset — the LookML *explore* analog). Worked example:
[`templates/semantic-model.example.yaml`](../templates/semantic-model.example.yaml).

| LookML | Hex semantic YAML | Notes |
|---|---|---|
| `view: x { sql_table_name: DB.SCH.T }` | `type: model`, `base_sql_table: DB.SCH.T` | derived-table view → `base_sql_query: "<SQL>"` instead |
| `dimension: d { sql: ${TABLE}.col ;; type: string }` | a `dimensions[]` entry `{id: d, type: string}` | types: `string` / `number` / `date` / `boolean` |
| `primary_key: yes` | `unique: true` on that dimension | **every model needs exactly one** `unique: true` dim |
| `hidden: yes` | `visibility: internal` | keeps it usable but out of the picker |
| a `dimension_group: time` (many timeframes) | **one** `type: date` dimension | Hex truncates at query time — don't emit one dim per timeframe; collapse to the base date column (keep the `_month`/`_quarter` *legacy numeric* copies only as `visibility: internal` and warn against them) |
| `measure { type: sum, sql: ${x} }` | `{id, func: sum, of: x}` | also `count` (→ `func: count`, no `of`), `count_distinct`, `average`, `min`, `max`, `median` |
| filtered measure (`filters:` on a measure) | `{type: number, func_sql: "SUM(CASE WHEN … THEN ${x} END)"}` | express the filter inline in `func_sql` |
| `measure { type: number, sql: ${a}/${b} }` (ratio of measures) | `{type: number, func_sql: "${a} / NULLIF(${b}, 0)"}` | **ratio of measures**, never `AVG(a/b)`; guard the divide |
| `${field}` / `${other_view.field}` refs | same `${dimension}` / `${other_model.measure}` refs | cross-model refs resolve through a `relation` |
| `explore.join { sql_on: A=B ;; relationship: many_to_one }` | a `relations[]` entry `{id: <target model>, type: many_to_one, join_sql: "${A} = ${target.B}"}` | `type`: `many_to_one` / `one_to_many` / `one_to_one` / `many_to_many` |
| `explore: e { ... joins ... }` | a `type: view` `{base: <base model>, contents: [...]}` | curated entry point; see below |
| `value_format_name` / `value_format` | (carried on the **chart cell**, not the model) | number formatting lives in the workbook/cell layer — see [`building-cells.md`](building-cells.md) |
| `access_filter` / user-attribute Liquid | **not** a model construct | RLS → Hex Jinja RBAC in the notebook, flagged; see [`lookml-semantics.md`](lookml-semantics.md) §6 |

**The `view` (Explore analog).** A `type: view` has a `base:` model and `contents:`
groups. A base-model group lists dimensions/measures by id; a related-model group
uses `- relation: <relation id>` and lists that model's fields. Views are optional
— models alone carry all analytical capability; a view just gives a friendlier
curated surface. Map one Hex view per LookML explore.

**Fidelity notes:**
- Preserve the LookML `description`s — they carry the "which field to prefer" and
  "don't truncate this legacy column" guidance the agent relies on. The example
  keeps them verbatim.
- A LookML measure that references only measures (a ratio) becomes a `func_sql`
  referencing other `${measure}`s — Hex resolves the dependency. Confirm the divide
  is `NULLIF`-guarded.
- **Parity still applies.** After publishing, spot-check a metric against the same
  warehouse `SELECT` (and Looker's own value via `looker_fetch.py query`) — the
  same numeric parity discipline as the SQL-fidelity gate.

## Publish flow (`hex context`)

`hex context` syncs a **local directory of semantic YAML → an existing semantic
project**, via a `hex_context.config.json`. Commands are hidden from
`hex context --help` but real (verified on `hex 1.2026.07.21`).

1. **Customer creates the empty semantic project in the Hex UI** and sends you its
   **project id** (UUID). (The CLI can't create it.)

2. **Write the models + view** to a directory, e.g. `models/`, and a config at the
   repo root (or pass `--config-path`):
   ```json
   {
     "semanticProjects": [
       { "id": "<semantic-project-UUID>", "path": "models/" }
     ]
   }
   ```
   ⚠️ The key is **`semanticProjects`** (not `semanticModels` — the alpha docs are
   stale). `guides` can live in the same config (`{pattern, transform:{stripFolders}}`
   or `{path, hexFilePath}`) to ship the guide in the same publish.

3. **Preview (non-destructive):**
   ```bash
   hex context preview --config-path ./hex_context.config.json [--base draft|latest]
   # → prints a Preview ID + URL. Uploads a THROWAWAY version; the live project is untouched.
   ```
   Optionally point the notebook agent at the previewed context:
   `hex thread create "<prompt>" --new-project --preview-id <preview_id>`.

4. **Publish when it checks out:**
   ```bash
   hex context publish <preview_id>     # or `-` for the last preview created this session
   ```

> ⚠️ **Publish is a directory→project sync and prunes by default** — the project's
> models are made to *match your local directory*. Never point it at a semantic
> project that already holds content you care about unless the local dir is the full
> intended state. Use a **dedicated** project for the migrated model. `--no-prune`
> keeps guides that aren't in the config; there's no partial-model merge, so treat
> the local dir as the source of truth. **Preview is always safe; publish mutates.**

## When to offer this vs. just the guide

| | Guide (default) | Semantic model (optional) |
|---|---|---|
| Headless? | ✅ fully (`hex guide`) | ⚠️ one UI step (create the empty project), then CLI |
| What it is | retrieved prose context | enforced, queryable metrics + joins |
| Agent uses it as | guidance | governed definitions it queries directly |
| Effort | low | medium (author + validate YAML, create project) |

Ship the **guide always**. Offer the **semantic model** when the customer wants a
real governed metrics layer to replace what LookML gave them — and is fine with the
one-time project-creation step.
