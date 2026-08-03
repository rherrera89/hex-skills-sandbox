# Offline translation dry-run — `thelookevent` / `business_pulse`

A zero-dependency validation of the skill's **understand-the-source** half
(`lookml-semantics.md` + `gotchas.md` + `sql-review.md`) against real, gnarly LookML.
No Looker instance, no warehouse — just: parse the LookML, translate the
`business_pulse` dashboard's `order_items` tiles the way the skill prescribes, and
record where the reference **held**, was **silent**, or was **wrong**.

Ground-truth SQL: [`expected/business_pulse.order_items.sql`](expected/business_pulse.order_items.sql).

## Verdict

The reference is **solid on the individual constructs** — every hard piece this
dashboard throws (derived tables/PDTs, `explore_source` native DTs with window
`derived_column`s, `count`-on-joined-view, `count_distinct`, filtered measures,
ratio-of-measures, `dimension_group` timeframes, pivots) has a correct mapping. The
gaps are at the **edges and the seams**: Looker's relative-date filter grammar, a
couple of `dimension_group`/dynamic-field cases, one join-cardinality subtlety, and
the fact that a single KPI often composes 4–5 constructs at once.

## What held up ✅

- **`count` on a joined view → `COUNT(DISTINCT pk)`.** The "First Purchasers" KPI is
  `users.count` on the `order_items` explore; the fan-out makes `COUNT(*)` wrong.
  `lookml-semantics.md` §2 flags exactly this. Caught it.
- **Derived tables rebuilt inline.** Both PDTs (`repeat_purchase_facts` raw-SQL,
  `order_facts` `explore_source` with a `RANK() OVER (…)` `derived_column`) map to
  CTEs per §4. The `explore_source` → "translate the referenced explore's fields"
  rule is right.
- **Ratio-of-measures + `NULLIF`.** `average_spend_per_user`, `total_gross_margin_percentage`,
  `30_day_repeat_purchase_rate` are all `type: number` divisions — the skill's
  "SUM(a)/SUM(b), not a pre-divided column, guard the divide" rule holds.
- **Filtered measures → `SUM(CASE…)` / filtered `COUNT(DISTINCT)`.** Correct.
- **`${…}` transitive resolution** through `gross_margin → sale_price / inventory_items.cost`
  and `repeat_purchase_within_30d → days_until_next_order → repeat_purchase_facts.next_order`.
- **Filter-scope sweep + `listen`.** The dashboard filters (`State/City/Traffic
  Source/Gender/Date/Country`) map to different dimensions per tile via `listen:`;
  the "check the listen map, don't assume every filter hits every tile" rule is right,
  and the `Date` default (`90 days`) belongs in the shared `WHERE`.

## Gaps found 🔸 (concrete, worth folding back in)

**1. Looker relative-date filter grammar is under-documented.** This dashboard alone
uses `7 days`, `90 days`, `before 0 months ago`, `4 years`. These are **not** obvious:
`before 0 months ago` = "up to the start of the current month" (excludes the current
partial month); `4 years` = the last 4 years *including* the current partial year.
`lookml-semantics.md` §7 covers `{% date_start/date_end %}` Liquid but **not** the
dashboard-filter/`filters:` relative-date expressions, and `sql-review.md`'s checklist
has a **week-anchor** line but **no relative-date off-by-one** line (the Tableau skill
*does* have one). → Add a relative-date grammar table to §7 and a checklist line to
`sql-review.md` §3.

**2. `month_name` sorts alphabetically unless you carry `month_num`.** The "Total
Sales YoY" tile plots `created_month_name` on the x-axis. Translated naively you get
`FORMAT_TIMESTAMP('%B', …)` and an `ORDER BY` on the *string* → April, August,
December… `lookml-semantics.md` §3 lists `_month_name` → "the matching date-part
function" but doesn't warn that it needs a companion `month_num` for chronological
order. → Add the note to §3.

**3. `FULL OUTER` one_to_one join changes the base row set.** `order_items` joins
`inventory_items` as `type: full_outer relationship: one_to_one`. `one_to_one` means
no fan-out (skill covers that), but **`FULL OUTER`** pulls in unmatched inventory rows
→ `COUNT(*)`/`SUM` over the base can include phantom rows. §5's join table maps
`full_outer` → "the matching JOIN" but doesn't flag that outer-direction changes the
population (only `relationship:` fan-out is called out). → Add a line: outer join
*direction* is a population concern, not just `relationship:`.

**4. Not every `dynamic_fields` entry is a window function.** `business_pulse` has
`table_calculation: goal, expression: '10000'` (a literal) and `date, expression:
now()` (a scalar function). `lookml-semantics.md` §7.5's table maps `running_total`,
`rank`, `offset`, `percent_of_*` → `OVER(…)`, but a **constant** or `now()` is just a
literal / `CURRENT_TIMESTAMP()`, not a window. An agent following the table too
literally might invent a pointless `OVER()`. → Add "constants / scalar functions
(`now()`, literals) translate to themselves, not windows."

**5. A single KPI composes 4–5 constructs — the reference has the pieces but no
worked multi-hop example.** `30_day_repeat_purchase_rate` chains: PDT (rebuild as
CTE) → cross-row `TIMESTAMP_DIFF` to the PDT's `next_order` → a `yesno` dimension →
a *filtered* `count_distinct` → a ratio-of-measures. Every step is documented
separately; nothing shows them stacked. This is where a real migration goes wrong.
→ Consider a single end-to-end worked example (this KPI is a good one) in
`lookml-semantics.md` or `sql-review.md`.

**6. A *hidden* field that is itself a table calc still must be computed.** "Total
Sales YoY" has `hidden_fields: [calculation_1]` — a hidden **table calculation**.
`building-cells.md` says "don't drop hidden *dimensions*, hide them," but doesn't
address a hidden *calc* that downstream visible fields may depend on. → One line:
hidden table-calcs still get translated if anything references them.

## Non-gaps worth noting

- **The LookML `sql:` is already BigQuery** (`TIMESTAMP_DIFF`, `FORMAT_TIMESTAMP`,
  `INT64`, backtick `project.dataset.table`). Translation is largely *passthrough* —
  which makes the skill's "**never assume Snowflake**; confirm the Hex connection is
  the *same* dialect" warning load-bearing: this LookML would break verbatim on
  Snowflake. The dry-run reinforces the existing rule rather than exposing a gap.
- **`bigquery-public-data.thelook_ecommerce` is the public twin** of the private
  `looker-private-demo.ecomm.*` tables. The PDTs (`*_facts`) don't exist there but are
  rebuilt from `order_items` anyway — so the ground-truth SQL is runnable against the
  public dataset with only the table-name repoint.

## What this dry-run does NOT cover

The Looker **REST API** layer (`looker_fetch.py` auth / contract / `sql` / `query` /
`shots`), the **UDD** path (these are file dashboards), and **true numeric parity vs
Looker's own rendered numbers** — all need a live Looker instance with this project
loaded. This validated the translation *reasoning*, not the API plumbing.
