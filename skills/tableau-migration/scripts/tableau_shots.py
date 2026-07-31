#!/usr/bin/env python3
"""Export PNG images of a workbook's views (dashboard + worksheets) for QA.
Reuses credentials/tableau.env. Usage: tableau_shots.py "<workbook name>"
"""
import sys
from pathlib import Path
import tableauserverclient as TSC

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ENV = ROOT / "credentials" / "tableau.env"
OUT = ROOT / "tableau_exports" / "shots"


def load_env(path):
    env = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
    return env


def main():
    wb_name = sys.argv[1]
    env = load_env(ENV)
    OUT.mkdir(parents=True, exist_ok=True)
    auth = TSC.PersonalAccessTokenAuth(
        env["TABLEAU_PAT_NAME"], env["TABLEAU_PAT_SECRET"], site_id=env["TABLEAU_SITE"]
    )
    server = TSC.Server(env["TABLEAU_SERVER"], use_server_version=True)
    with server.auth.sign_in(auth):
        wb = next((w for w in TSC.Pager(server.workbooks) if w.name == wb_name), None)
        if not wb:
            sys.exit(f"workbook not found: {wb_name}")
        server.workbooks.populate_views(wb)
        hires = TSC.ImageRequestOptions(imageresolution=TSC.ImageRequestOptions.Resolution.High)
        for v in wb.views:
            server.views.populate_image(v, hires)
            safe = "".join(c if c.isalnum() else "_" for c in v.name)[:60]
            p = OUT / f"{safe}.png"
            p.write_bytes(v.image)
            print(f"  {v.name} -> {p.name} ({len(v.image)//1024} KB)")
    print(f"\nSaved to {OUT}/")


if __name__ == "__main__":
    main()
