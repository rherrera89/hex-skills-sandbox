# Data connection mapping

Resolve which **Hex data connection** a migrated dashboard's cells should query. There's no automatic link from Looker — match on metadata, not names or hosts. Do this per model/explore (step 1 of the porting loop).

## 1. Find the LookML model's connection

A LookML **model** file declares exactly one warehouse connection:

```lookml
connection: "sales_warehouse"
```

Get the model → its connection name → the connection's physical details over the API:

```bash
python3 scripts/looker_fetch.py list-models                 # model -> allowed_db_connection_names
python3 scripts/looker_fetch.py connection sales_warehouse   # dialect + host + database + schema
```

`GET /connections/{name}` returns the fields that matter for mapping:

| Field | Use |
|---|---|
| `dialect` / `dialect_name` | the warehouse type — `snowflake_standard`, `bigquery_standard`, `redshift`, `databricks`, `postgres`, `duckdb`, … → **the SQL dialect you translate to** |
| `database` | the database the explore's tables live in |
| `schema` | default schema (LookML `sql_table_name` may override per view) |
| `host` | warehouse host — **do not match on this** (see §3) |
| `tmp_db_name` | the PDT scratch schema — where persisted derived tables materialize (relevant for `derived_table` cost) |

> **Offline (no API)?** The connection name is in the `.model.lkml`, but the *physical* dialect/database/schema are only in Looker's connection config — ask the customer (or read `GET /connections` once with any API access). The dialect drives every SQL translation, so don't guess it.

## 2. Match to a Hex connection

`hex connection list --json` → `hex connection get <id> --json` → `connectionDetails.<type>.{database, warehouse, schema, …}`. **Match on `type` (dialect) + `database` (+ `schema`).**

Map Looker dialect → Hex connection type:

| Looker `dialect` | Warehouse |
|---|---|
| `snowflake_standard` | Snowflake |
| `bigquery_standard` / `bigquery_legacy` | BigQuery |
| `redshift` | Amazon Redshift |
| `databricks` / `spark` | Databricks SQL |
| `postgres` | PostgreSQL |
| `duckdb` | DuckDB |

## 3. Do NOT match on host

The account URL usually differs even for the same data:
```
Looker: <account-a>.snowflakecomputing.com  /  SALES_DB . PUBLIC
Hex:    <account-b>.<region>.aws            /  sales_db
        ^ different host,  same database.  (and possibly a different SNAPSHOT — data parity is NOT guaranteed)
```

## 4. Decide
- **Exactly one** Hex connection matches type+database → use it; state the assumption in output.
- **Zero or multiple** → **ask the customer** which Hex connection to target. This is the one genuine human gate on connections — data may live in a different account/snapshot.

## 5. Translate names 1:1

A LookML view's physical table comes from `sql_table_name: DB.SCHEMA.TABLE` (or, absent that, `schema.<view_name>`). Translate to Hex SQL `DB.SCHEMA.TABLE`. Validate reachability with the run-status oracle (wrong role/schema → `ERRORED`, not silent).

> ⚠️ **Dev vs. production schemas.** LookML often points at a dev database via `sql_table_name` overridden by a `user_attribute` or a `_dev`/`_prod` suffix pattern. Confirm you're translating the **production** table the dashboard actually reads — Looker's generated SQL (`looker_fetch.py sql`) shows the *resolved* table names, so use it to see which schema Looker really hits.

## 6. Persistent derived tables (PDTs) — a materialized snapshot

If the explore is built on a **persisted derived table** (`datagroup`/`persist_for`), Looker materializes it into the connection's `tmp_db_name` scratch schema on a schedule. Two consequences:

- The dashboard reflects the PDT **as of its last rebuild**, so a fresh query against the base tables can legitimately differ (snapshot drift) — set expectations up front.
- You have a choice: **rebuild the derived SQL inline** as a Hex SQL cell (live, always-fresh — preferred for correctness) or, if the PDT is expensive and the drift is acceptable, point at the materialized scratch table (faster, stale). Default to rebuilding the SQL inline unless the customer says otherwise. See [`lookml-semantics.md`](lookml-semantics.md) §Derived tables.

> Looker connection naming to match a warehouse makes step 2 trivial, but it's a **bonus**, not a requirement.
