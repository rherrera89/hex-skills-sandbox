#!/usr/bin/env python3
"""Fetch Looker content over the Looker REST API 4.0 for a Looker -> Hex migration.

Step 1 of the migration flow. Logs in with an API3 key (client_credentials),
then lists / fetches the two Looker layers:

  * the LookML semantic model (models, explores, connections), and
  * the dashboards + Looks (mostly user-defined "UDD", reachable ONLY via the API).

Looker will hand you the **generated warehouse SQL** for any query (`sql`
sub-command) and the **actual result values** (`query` sub-command). Phase 1
becomes "port Looker's SQL", and the SQL-fidelity gate gets a real numeric oracle
— not just the blind COMPLETED/ERRORED check. Use them.

Auth: Looker API 4.0 `POST /api/4.0/login` with client_id/client_secret returns a
short-lived access_token; every other call carries `Authorization: token <token>`.
(Confirmed: https://docs.cloud.google.com/looker/docs/api-auth) Zero third-party
deps — stdlib urllib only.

Usage:
  # confirm auth + role
  python3 scripts/looker_fetch.py whoami

  # inventory (drives Step 0 prioritization)
  python3 scripts/looker_fetch.py list-models
  python3 scripts/looker_fetch.py list-dashboards        # UDD + LookML, one line each
  python3 scripts/looker_fetch.py list-looks

  # resolve the warehouse a model's connection points at (connection-mapping.md)
  python3 scripts/looker_fetch.py connection <connection_name>
  python3 scripts/looker_fetch.py explore <model> <explore>   # field graph + joins

  # pull one dashboard into the normalized contract (UDD or LookML)
  python3 scripts/looker_fetch.py dashboard <dashboard_id>     # -> looker_exports/<id>.contract.json

  # a single Look (one saved query)
  python3 scripts/looker_fetch.py look <look_id>

  # Looker's GENERATED SQL for a tile's query (the Phase-1 shortcut) and its
  # actual VALUES (the Phase-1.5 numeric oracle). Both take a query-spec JSON file
  # ({model, view, fields, filters, sorts, limit, ...}) written from the contract.
  python3 scripts/looker_fetch.py sql   query-spec.json        # -> generated SQL (text)
  python3 scripts/looker_fetch.py query query-spec.json        # -> result rows (JSON)

  # render a dashboard to PNG for the visual-QA loop (reference/visual-qa-loop.md)
  python3 scripts/looker_fetch.py shots <dashboard_id> -o working/shots/looker-<id>.png

  # raw passthrough for anything not wrapped above
  python3 scripts/looker_fetch.py raw GET /lookml_models

Credentials (either source; env file wins):
  * credentials/looker.env  (copy from looker.env.example; gitignored), or
  * ~/.looker/looker.ini    (the Looker SDK standard [Looker] section)
"""
import argparse
import configparser
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = REPO_ROOT / "credentials" / "looker.env"
EXPORT_DIR = REPO_ROOT / "looker_exports"


# --------------------------------------------------------------------------- #
# credentials
# --------------------------------------------------------------------------- #
def load_creds() -> dict:
    """base_url + client_id + client_secret from looker.env, else ~/.looker/looker.ini."""
    creds = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            creds[k.strip()] = v.strip()
        base = creds.get("LOOKER_BASE_URL")
        cid = creds.get("LOOKER_CLIENT_ID")
        secret = creds.get("LOOKER_CLIENT_SECRET")
        verify = creds.get("LOOKER_VERIFY_SSL", "true")
    else:
        ini = Path(os.path.expanduser("~/.looker/looker.ini"))
        if not ini.exists():
            sys.exit(
                f"No credentials. Copy credentials/looker.env.example to "
                f"credentials/looker.env (or create ~/.looker/looker.ini) and fill in "
                f"base_url + client_id + client_secret."
            )
        cp = configparser.ConfigParser()
        cp.read(ini)
        sec = cp["Looker"] if cp.has_section("Looker") else cp[cp.sections()[0]]
        base = sec.get("base_url")
        cid = sec.get("client_id")
        secret = sec.get("client_secret")
        verify = sec.get("verify_ssl", "true")

    if not (base and cid and secret):
        sys.exit("Missing one of base_url / client_id / client_secret.")

    # Normalize base_url -> https://host/api/4.0 . Modern Google-hosted Looker
    # serves the API on 443 (no port); older self-hosted used :19999.
    base = base.rstrip("/")
    if base.endswith("/api/4.0"):
        api = base
    else:
        api = base + "/api/4.0"
    return {
        "api": api,
        "client_id": cid,
        "client_secret": secret,
        "verify_ssl": str(verify).lower() not in ("false", "0", "no"),
    }


# --------------------------------------------------------------------------- #
# minimal API 4.0 client (stdlib only), with a per-process token cache
# --------------------------------------------------------------------------- #
_TOKEN = {"value": None}


def _ssl_ctx(verify: bool):
    import ssl

    if verify:
        return None  # default verification
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def login(creds: dict) -> str:
    if _TOKEN["value"]:
        return _TOKEN["value"]
    data = urllib.parse.urlencode(
        {"client_id": creds["client_id"], "client_secret": creds["client_secret"]}
    ).encode()
    req = urllib.request.Request(creds["api"] + "/login", data=data, method="POST")
    try:
        with urllib.request.urlopen(req, context=_ssl_ctx(creds["verify_ssl"])) as r:
            tok = json.loads(r.read())["access_token"]
    except urllib.error.HTTPError as e:
        sys.exit(f"Login failed ({e.code}): {e.read().decode(errors='replace')[:400]}")
    except urllib.error.URLError as e:
        sys.exit(
            f"Login could not reach {creds['api']}: {e.reason}. If base_url still "
            f"carries :19999 and that port is closed, drop it — modern Looker uses 443."
        )
    _TOKEN["value"] = tok
    return tok


def call(creds: dict, method: str, path: str, body=None, raw_text=False):
    """One API call. `path` starts with '/'. Retries once on 401 with a fresh login."""
    token = login(creds)
    url = creds["api"] + path
    payload = None
    headers = {"Authorization": f"token {token}"}
    if body is not None:
        payload = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=payload, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, context=_ssl_ctx(creds["verify_ssl"])) as r:
            text = r.read().decode(errors="replace")
    except urllib.error.HTTPError as e:
        if e.code == 401:  # token expired mid-session — re-login once
            _TOKEN["value"] = None
            token = login(creds)
            req.headers["Authorization"] = f"token {token}"
            with urllib.request.urlopen(req, context=_ssl_ctx(creds["verify_ssl"])) as r:
                text = r.read().decode(errors="replace")
        else:
            sys.exit(f"{method} {path} -> {e.code}: {e.read().decode(errors='replace')[:600]}")
    if raw_text:
        return text
    return json.loads(text) if text.strip() else None


# --------------------------------------------------------------------------- #
# normalized dashboard contract  (UDD and LookML dashboards, same shape)
# --------------------------------------------------------------------------- #
# tileType comes from query.vis_config.type (NOT element.type, always "vis"); the
# dashboard filters a tile obeys come from result_maker.filterables[].listen;
# dynamic_fields (table calcs / custom measures) arrive as a JSON *string*.
def _parse_dynamic_fields(q: dict):
    df = q.get("dynamic_fields")
    if isinstance(df, str) and df.strip():
        try:
            return json.loads(df)
        except json.JSONDecodeError:
            return df  # keep raw so the agent can see it
    return df


def normalize_element(el: dict) -> dict:
    """One dashboard_element (tile) -> one contract element."""
    q = el.get("query") or {}
    result_maker = el.get("result_maker") or {}
    vis = (q.get("vis_config") or {}) if q else {}
    # tile type: chart tiles -> query.vis_config.type; text tiles -> element.type
    tile_type = vis.get("type") or el.get("type")
    listen = []
    for f in (result_maker.get("filterables") or []):
        for lst in (f.get("listen") or []):
            listen.append(lst)  # {dashboard_filter_name, field}
    return {
        "id": el.get("id"),
        "title": el.get("title") or el.get("title_text"),
        "tileType": tile_type,
        "model": q.get("model"),
        "explore": q.get("view"),  # Looker "view" on a Query == the explore name
        "fields": q.get("fields"),
        "pivots": q.get("pivots"),
        "filters": q.get("filters"),
        "sorts": q.get("sorts"),
        "limit": q.get("limit"),
        "column_limit": q.get("column_limit"),
        "dynamic_fields": _parse_dynamic_fields(q),
        "vis_config": vis,  # column_order, series_labels, hidden_fields, value formats
        "listen": listen,
        "text": el.get("body_text") or el.get("subtitle_text"),  # for text tiles
        "note_text": el.get("note_text"),
        "query_id": el.get("query_id"),
        "look_id": el.get("look_id"),
    }


def _active_layout(dash: dict):
    layouts = dash.get("dashboard_layouts") or []
    active = next((l for l in layouts if l.get("active")), None) or (layouts[0] if layouts else None)
    comps = {}
    if active:
        for c in (active.get("dashboard_layout_components") or []):
            comps[c.get("dashboard_element_id")] = {
                "row": c.get("row"),
                "column": c.get("column"),
                "width": c.get("width"),
                "height": c.get("height"),
            }
    return comps


def build_contract(dash: dict) -> dict:
    layout = _active_layout(dash)
    elements = []
    for el in (dash.get("dashboard_elements") or []):
        norm = normalize_element(el)
        norm["layout"] = layout.get(el.get("id"))
        elements.append(norm)
    filters = []
    for f in (dash.get("dashboard_filters") or []):
        filters.append(
            {
                "name": f.get("name"),
                "title": f.get("title"),
                "type": f.get("type"),
                "model": f.get("model"),
                "explore": f.get("explore"),
                "dimension": f.get("dimension"),
                "default_value": f.get("default_value"),
                "allow_multiple_values": f.get("allow_multiple_values"),
            }
        )
    dash_id = dash.get("id")
    kind = "LookML" if isinstance(dash_id, str) and "::" in str(dash_id) else "UDD"
    return {
        "id": dash_id,
        "title": dash.get("title"),
        "kind": kind,
        "description": dash.get("description"),
        "elements": elements,
        "filters": filters,
    }


# --------------------------------------------------------------------------- #
# sub-commands
# --------------------------------------------------------------------------- #
def cmd_whoami(creds, args):
    me = call(creds, "GET", "/user")
    roles = call(creds, "GET", f"/users/{me['id']}/roles") or []
    print(f"OK  {me.get('display_name')} <{me.get('email')}>  (id={me.get('id')})")
    print("Roles: " + ", ".join(r.get("name", "?") for r in roles))


def cmd_list_models(creds, args):
    models = call(creds, "GET", "/lookml_models") or []
    for m in sorted(models, key=lambda x: x.get("name", "")):
        exps = [e.get("name") for e in (m.get("explores") or [])]
        print(f"  {m.get('name')}   conn={m.get('allowed_db_connection_names')}   "
              f"explores({len(exps)}): {', '.join(exps[:8])}{' …' if len(exps) > 8 else ''}")


def cmd_list_dashboards(creds, args):
    dashes = call(creds, "GET", "/dashboards?fields=id,title,description") or []
    for d in dashes:
        did = str(d.get("id"))
        kind = "LookML" if "::" in did else "UDD"
        print(f"  [{kind:6}] {did:20} {d.get('title')}")
    print(f"\n{len(dashes)} dashboard(s). Fetch one: dashboard <id>")


def cmd_list_looks(creds, args):
    looks = call(creds, "GET", "/looks?fields=id,title,query_id") or []
    for lk in looks:
        print(f"  {str(lk.get('id')):8} {lk.get('title')}")
    print(f"\n{len(looks)} Look(s).")


def cmd_connection(creds, args):
    c = call(creds, "GET", f"/connections/{urllib.parse.quote(args.name)}")
    # the fields that matter for mapping to a Hex connection
    keep = ["name", "dialect_name", "host", "port", "database", "schema", "username",
            "jdbc_additional_params", "tmp_db_name"]
    out = {k: c.get(k) for k in keep if k in c}
    dialect = (c.get("dialect") or {}).get("name") if isinstance(c.get("dialect"), dict) else c.get("dialect_name")
    out["dialect"] = dialect
    print(json.dumps(out, indent=2))
    print("\n-> Match this dialect + database to a Hex connection "
          "(hex connection list --json). See reference/connection-mapping.md.")


def cmd_explore(creds, args):
    e = call(creds, "GET", f"/lookml_models/{args.model}/explores/{args.explore}")
    print(json.dumps(e, indent=2))


def cmd_dashboard(creds, args):
    dash = call(creds, "GET", f"/dashboards/{urllib.parse.quote(str(args.id))}")
    contract = build_contract(dash)
    EXPORT_DIR.mkdir(exist_ok=True)
    out = Path(args.out) if args.out else EXPORT_DIR / f"{args.id}.contract.json"
    out.write_text(json.dumps(contract, indent=2))
    n = len(contract["elements"])
    print(f"OK  [{contract['kind']}] {contract['title']}  ({n} tiles, "
          f"{len(contract['filters'])} filters)\n    -> {out}")


def cmd_look(creds, args):
    lk = call(creds, "GET", f"/looks/{args.id}")
    q = lk.get("query") or {}
    contract = {
        "id": lk.get("id"),
        "title": lk.get("title"),
        "kind": "Look",
        "elements": [normalize_element({"id": lk.get("id"), "title": lk.get("title"),
                                        "type": "vis", "query": q,
                                        "result_maker": {"filterables": []}})],
        "filters": [],
    }
    EXPORT_DIR.mkdir(exist_ok=True)
    out = Path(args.out) if args.out else EXPORT_DIR / f"look-{args.id}.contract.json"
    out.write_text(json.dumps(contract, indent=2))
    print(f"OK  Look {lk.get('title')}\n    -> {out}")


def _load_query_spec(path):
    spec = json.loads(Path(path).read_text())
    # accept either a bare query spec or a contract element (pull the query fields out)
    if "fields" in spec and "model" in spec:
        return {k: spec[k] for k in
                ("model", "view", "explore", "fields", "pivots", "filters", "sorts",
                 "limit", "column_limit", "dynamic_fields") if spec.get(k) is not None}
    return spec


def cmd_sql(creds, args):
    spec = _load_query_spec(args.spec)
    if "view" not in spec and "explore" in spec:
        spec["view"] = spec.pop("explore")  # the API calls the explore "view"
    sql = call(creds, "POST", "/queries/run/sql", body=spec, raw_text=True)
    print(sql)


def cmd_query(creds, args):
    spec = _load_query_spec(args.spec)
    if "view" not in spec and "explore" in spec:
        spec["view"] = spec.pop("explore")
    rows = call(creds, "POST", "/queries/run/json", body=spec, raw_text=True)
    print(rows)


def cmd_raw(creds, args):
    body = json.loads(args.body) if args.body else None
    res = call(creds, args.method, args.path, body=body, raw_text=True)
    print(res)


def _get_bytes(creds: dict, path: str) -> bytes:
    """GET a binary response (a rendered PNG), with a single 401 re-login."""
    token = login(creds)
    req = urllib.request.Request(
        creds["api"] + path, method="GET", headers={"Authorization": f"token {token}"}
    )
    try:
        with urllib.request.urlopen(req, context=_ssl_ctx(creds["verify_ssl"])) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        if e.code == 401:
            _TOKEN["value"] = None
            req.headers["Authorization"] = f"token {login(creds)}"
            with urllib.request.urlopen(req, context=_ssl_ctx(creds["verify_ssl"])) as r:
                return r.read()
        sys.exit(f"GET {path} -> {e.code}: {e.read().decode(errors='replace')[:400]}")


def cmd_shots(creds, args):
    """Render a dashboard to PNG via Looker's render-task API (headless, no browser).

    Source-side capture for the visual-QA loop (reference/visual-qa-loop.md). Creates
    a render task, polls it to completion, then downloads the PNG.
    """
    qs = urllib.parse.urlencode({"width": args.width, "height": args.height})
    task = call(
        creds, "POST",
        f"/render_tasks/dashboards/{urllib.parse.quote(str(args.id))}/png?{qs}",
        body={"dashboard_style": args.style},
    )
    task_id = (task or {}).get("id")
    if not task_id:
        sys.exit(f"render task not created: {json.dumps(task)[:400]}")

    # Render can take a while for big dashboards — poll until success/failure.
    t, status, waited = None, None, 0
    while waited < args.timeout:
        t = call(creds, "GET", f"/render_tasks/{urllib.parse.quote(task_id)}")
        status = (t or {}).get("status")
        if status in ("success", "failure"):
            break
        time.sleep(2)
        waited += 2
    if status != "success":
        sys.exit(f"render task {task_id} ended status={status} "
                 f"(detail: {(t or {}).get('status_detail')})")

    png = _get_bytes(creds, f"/render_tasks/{urllib.parse.quote(task_id)}/results")
    out = Path(args.out) if args.out else (EXPORT_DIR / "shots" / f"{args.id}.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(png)
    print(f"OK  rendered dashboard {args.id} -> {out} ({len(png)//1024} KB)")


def main():
    ap = argparse.ArgumentParser(description="Fetch Looker content over the REST API 4.0")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("whoami")
    sub.add_parser("list-models")
    sub.add_parser("list-dashboards")
    sub.add_parser("list-looks")

    p = sub.add_parser("connection"); p.add_argument("name")
    p = sub.add_parser("explore"); p.add_argument("model"); p.add_argument("explore")

    p = sub.add_parser("dashboard"); p.add_argument("id"); p.add_argument("--out")
    p = sub.add_parser("look"); p.add_argument("id"); p.add_argument("--out")

    p = sub.add_parser("sql"); p.add_argument("spec", help="query-spec JSON (or a contract element)")
    p = sub.add_parser("query"); p.add_argument("spec", help="query-spec JSON (or a contract element)")

    p = sub.add_parser("shots", help="render a dashboard to PNG (visual-QA source capture)")
    p.add_argument("id")
    p.add_argument("--out")
    p.add_argument("--width", type=int, default=1400)
    p.add_argument("--height", type=int, default=2000)
    p.add_argument("--style", default="tiled", help="dashboard_style: tiled | single_column")
    p.add_argument("--timeout", type=int, default=120, help="seconds to wait for the render")

    p = sub.add_parser("raw")
    p.add_argument("method"); p.add_argument("path"); p.add_argument("body", nargs="?")

    args = ap.parse_args()
    creds = load_creds()
    {
        "whoami": cmd_whoami,
        "list-models": cmd_list_models,
        "list-dashboards": cmd_list_dashboards,
        "list-looks": cmd_list_looks,
        "connection": cmd_connection,
        "explore": cmd_explore,
        "dashboard": cmd_dashboard,
        "look": cmd_look,
        "sql": cmd_sql,
        "query": cmd_query,
        "shots": cmd_shots,
        "raw": cmd_raw,
    }[args.cmd](creds, args)


if __name__ == "__main__":
    main()
