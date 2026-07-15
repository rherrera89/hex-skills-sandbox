# Data connection mapping

Resolve which **Hex data connection** a migrated workbook's cells should query. There's no automatic link from Tableau — match on metadata, not names or hosts. Do this per workbook (step 1 of the porting loop).

## 1. Get the Tableau connection's physical details
Location depends on the connection type:

| Tableau connection | Qualified table names in `.twb`? | How to read it |
|---|---|---|
| **Live / federated** | ✅ Yes — `[DB].[SCHEMA].[TABLE]` + server/db/schema/warehouse in `<named-connection>` | read from the `.twb` |
| **Published datasource** (`sqlproxy`) | ❌ No — hidden behind the proxy | download the published `.tdsx` (`server.datasources.download`) and read its `.tds` `<named-connection>` + `<relation>` |
| **Extract** (`.hyper`) | ⚠️ Points at the cached extract, not the warehouse | see *Extracts* below — **ask the customer** which connection it's built on |

Pull: `class` (snowflake/bigquery/…), `server`/host, `dbname`, `schema`, `warehouse`.

### Extracts (`.hyper`) — ask which connection they're built on
An **extract** is a cached snapshot, not a live warehouse link. In the XML the datasource is `class='federated'` with an `<extract>` element and a connection of `class='dataengine'` or `class='hyper'` pointing at the `.hyper` file — **that connection is the local cache, not a migration target.** So:

- **Detect it:** the datasource has an `<extract>` element / a `dataengine`|`hyper` connection.
- **Ask the customer which data connection the extract is built on**, then map *that* to a Hex connection via steps 2–4. This is a legitimate use of the human gate — don't try to read the `.hyper`.
- **If the original source connection is still retained** in the federated wrapper (common for refreshable extracts), propose it as the default and just have them confirm; for a "naked" extract with no retained source, ask outright.
- **Still sweep extract-level filters** (see `gotchas.md`) and expect snapshot drift — a live query may not match the extract-backed dashboard exactly.

## 2. Match to a Hex connection
`hex connection list --json` → `hex connection get <id> --json` → `connectionDetails.snowflake.{accountName, database, warehouse, role}`. **Match on `type` + `database` (+ `schema`).**

## 3. Do NOT match on host
The account URL usually differs even for the same data:
```
Tableau:  <account-a>.snowflakecomputing.com  /  SALES_DB . PUBLIC
Hex:      <account-b>.<region>.aws            /  sales_db
          ^ different host,  same database.  (and possibly a different SNAPSHOT — data parity is NOT guaranteed)
```

## 4. Decide
- **Exactly one** Hex connection matches type+database → use it; state the assumption in output.
- **Zero or multiple** → **ask the customer** which Hex connection to target. This is the one genuine human gate on connections — data may live in a different account/snapshot.

## 5. Translate names 1:1
Tableau `[DB].[SCHEMA].[TABLE]` → Hex SQL `DB.SCHEMA.TABLE`. Validate reachability with the run-status oracle (wrong role/schema → `ERRORED`, not silent).

> Naming Hex connections to match Tableau datasources makes step 2 trivial, but it's a **bonus**, not a requirement.
