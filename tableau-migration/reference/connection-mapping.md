# Data connection mapping

Resolve which **Hex data connection** a migrated workbook's cells should query. There's no automatic link from Tableau — match on metadata, not names or hosts. Do this per workbook (step 1 of the porting loop).

## 1. Get the Tableau connection's physical details
Location depends on the connection type:

| Tableau connection | Qualified table names in `.twb`? | How to read it |
|---|---|---|
| **Live / federated** | ✅ Yes — `[DB].[SCHEMA].[TABLE]` + server/db/schema/warehouse in `<named-connection>` | read from the `.twb` |
| **Published datasource** (`sqlproxy`) | ❌ No — hidden behind the proxy | download the published `.tdsx` (`server.datasources.download`) and read its `.tds` `<named-connection>` + `<relation>` |

Pull: `class` (snowflake/bigquery/…), `server`/host, `dbname`, `schema`, `warehouse`.

## 2. Match to a Hex connection
`hex connection list --json` → `hex connection get <id> --json` → `connectionDetails.snowflake.{accountName, database, warehouse, role}`. **Match on `type` + `database` (+ `schema`).**

## 3. Do NOT match on host
The account URL usually differs even for the same data:
```
Tableau:  qib82113.snowflakecomputing.com  /  B2B_DEMO_DATA . PROD
Hex:      co24109.us-east-2.aws            /  b2b_demo_data
          ^ different host,  same database.  (and possibly a different SNAPSHOT — data parity is NOT guaranteed)
```

## 4. Decide
- **Exactly one** Hex connection matches type+database → use it; state the assumption in output.
- **Zero or multiple** → **ask the customer** which Hex connection to target. This is the one genuine human gate on connections — data may live in a different account/snapshot.

## 5. Translate names 1:1
Tableau `[DB].[SCHEMA].[TABLE]` → Hex SQL `DB.SCHEMA.TABLE`. Validate reachability with the run-status oracle (wrong role/schema → `ERRORED`, not silent).

> Naming Hex connections to match Tableau datasources makes step 2 trivial, but it's a **bonus**, not a requirement.
