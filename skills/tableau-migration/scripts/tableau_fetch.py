#!/usr/bin/env python3
"""Fetch Tableau workbook(s) from Tableau Cloud and extract the .twb XML.

Step 1 of the Tableau -> Hex migration flow. Signs in with a Personal Access
Token, then either lists workbooks or downloads specific ones. Packaged
workbooks (.twbx) are unzipped so we always end up with the raw .twb XML that
the migration agent parses.

Usage:
  # list every workbook you can see (name + project + id)
  venv/bin/python scripts/tableau_fetch.py --list

  # download one workbook by name (optionally disambiguate with --project)
  venv/bin/python scripts/tableau_fetch.py --name "Sales Overview"
  venv/bin/python scripts/tableau_fetch.py --name "Sales Overview" --project "Finance"

  # download every workbook in a project
  venv/bin/python scripts/tableau_fetch.py --project "Finance"

Credentials are read from credentials/tableau.env (gitignored).
"""
import argparse
import os
import sys
import zipfile
from pathlib import Path

import tableauserverclient as TSC

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = REPO_ROOT / "credentials" / "tableau.env"
EXPORT_DIR = REPO_ROOT / "tableau_exports"


def load_env(path: Path) -> dict:
    if not path.exists():
        sys.exit(
            f"Missing {path}.\n"
            f"Copy credentials/tableau.env.example to credentials/tableau.env "
            f"and fill in your Tableau Cloud details."
        )
    env = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        env[key.strip()] = val.strip()
    required = ["TABLEAU_SERVER", "TABLEAU_SITE", "TABLEAU_PAT_NAME", "TABLEAU_PAT_SECRET"]
    missing = [k for k in required if not env.get(k)]
    if missing:
        sys.exit(f"tableau.env is missing values for: {', '.join(missing)}")
    return env


def extract_twb(path: Path) -> Path:
    """Given a downloaded .twb or .twbx, return the path to the raw .twb XML."""
    if path.suffix.lower() == ".twb":
        return path
    # .twbx is a zip; the workbook XML is the single top-level *.twb entry
    with zipfile.ZipFile(path) as zf:
        twb_names = [n for n in zf.namelist() if n.lower().endswith(".twb")]
        if not twb_names:
            sys.exit(f"No .twb found inside {path.name}")
        inner = twb_names[0]
        out = path.with_suffix(".twb")
        with zf.open(inner) as src, open(out, "wb") as dst:
            dst.write(src.read())
    return out


def main():
    ap = argparse.ArgumentParser(description="Fetch Tableau workbooks and extract .twb XML")
    ap.add_argument("--list", action="store_true", help="List all visible workbooks and exit")
    ap.add_argument("--name", help="Download the workbook with this exact name")
    ap.add_argument("--project", help="Filter/download by project name")
    args = ap.parse_args()

    env = load_env(ENV_FILE)
    EXPORT_DIR.mkdir(exist_ok=True)

    auth = TSC.PersonalAccessTokenAuth(
        env["TABLEAU_PAT_NAME"], env["TABLEAU_PAT_SECRET"], site_id=env["TABLEAU_SITE"]
    )
    server = TSC.Server(env["TABLEAU_SERVER"], use_server_version=True)

    with server.auth.sign_in(auth):
        print(f"Signed in to {env['TABLEAU_SERVER']} (site: {env['TABLEAU_SITE']}), "
              f"API v{server.version}\n")
        workbooks = list(TSC.Pager(server.workbooks))

        if args.list or (not args.name and not args.project):
            print(f"{len(workbooks)} workbook(s) visible:\n")
            for wb in sorted(workbooks, key=lambda w: (w.project_name or "", w.name)):
                print(f"  [{wb.project_name}]  {wb.name}   (id={wb.id})")
            if not args.list:
                print("\nRe-run with --name \"<workbook>\" or --project \"<project>\" to download.")
            return

        targets = workbooks
        if args.project:
            targets = [w for w in targets if w.project_name == args.project]
        if args.name:
            targets = [w for w in targets if w.name == args.name]

        if not targets:
            sys.exit("No workbooks matched your filters. Run with --list to see options.")

        print(f"Downloading {len(targets)} workbook(s) to {EXPORT_DIR}/\n")
        for wb in targets:
            raw = server.workbooks.download(wb.id, filepath=str(EXPORT_DIR), include_extract=False)
            raw_path = Path(raw)
            twb = extract_twb(raw_path)
            size_kb = twb.stat().st_size / 1024
            print(f"  OK  [{wb.project_name}] {wb.name}")
            print(f"      -> {twb.relative_to(REPO_ROOT)}  ({size_kb:.0f} KB)")


if __name__ == "__main__":
    main()
