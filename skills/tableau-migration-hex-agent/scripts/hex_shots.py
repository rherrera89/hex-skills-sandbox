#!/usr/bin/env python3
"""Headless screenshot of a Hex app for the Mode-D visual-QA loop.

Uses a persistent Playwright profile so the customer logs into Hex ONCE (headed),
and every later capture is fully headless. The agent never types credentials — the
customer authenticates their own browser during --login.

Setup once:
    pip install playwright && playwright install chromium
    python scripts/hex_shots.py --login          # headed; sign in, then press Enter

Capture (headless, reuses the saved session):
    python scripts/hex_shots.py "<hex_app_url>" -o working/shots/migrated.png

Notes:
- Unpublished drafts show a URL lock screen; pass an editor/app URL and the script
  clicks into "App builder" to reveal the rendered app without publishing.
- full_page alone only grabs the outer viewport (the Hex app is an inner scroll
  container); the script screenshots the app-canvas element when it can find one,
  else falls back to full_page. If a capture looks clipped, adjust the selector.
"""
import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PROFILE = ROOT / "working" / "hex-screenshot-profile"

# Candidate selectors for the rendered app canvas, most specific first. Hex markup
# changes over time — if captures clip, confirm/extend these against the live DOM.
APP_CANVAS_SELECTORS = [
    "[data-testid='app-view']",
    "[class*='appView']",
    "[class*='AppView']",
    "main",
]
APP_BUILDER_SELECTORS = [
    "text=App builder",
    "button:has-text('App builder')",
    "[data-testid='app-builder-tab']",
]


def login():
    PROFILE.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(PROFILE), headless=False, viewport={"width": 1600, "height": 1000}
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://app.hex.tech/login")
        print("A browser window opened. Sign into Hex, then return here.")
        input("Press Enter once you're fully logged in… ")
        ctx.close()
    print(f"Session saved to {PROFILE}. Later captures are headless.")


def reveal_app(page):
    """On an editor/draft URL, click into App builder so the render is visible."""
    for sel in APP_BUILDER_SELECTORS:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click()
                page.wait_for_timeout(2500)
                return
        except Exception:
            continue


def capture(url, out):
    if not PROFILE.exists():
        sys.exit("No saved profile. Run:  python scripts/hex_shots.py --login")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(PROFILE), headless=True, viewport={"width": 1600, "height": 1000}
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(url, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(3000)  # let charts finish rendering
        reveal_app(page)
        try:
            page.wait_for_load_state("networkidle", timeout=30000)
        except Exception:
            pass

        el = None
        for sel in APP_CANVAS_SELECTORS:
            el = page.query_selector(sel)
            if el:
                break
        if el:
            el.screenshot(path=str(out))
        else:
            page.screenshot(path=str(out), full_page=True)
        ctx.close()
    print(f"Wrote {out}")


def main():
    ap = argparse.ArgumentParser(description="Headless Hex-app screenshot for visual QA.")
    ap.add_argument("url", nargs="?", help="Hex app (or editor) URL to capture")
    ap.add_argument("--login", action="store_true", help="Headed one-time sign-in")
    ap.add_argument("-o", "--out", default="working/shots/migrated.png", help="Output PNG path")
    args = ap.parse_args()

    if args.login:
        login()
        return
    if not args.url:
        ap.error("provide a URL to capture, or use --login for first-time setup")
    capture(args.url, args.out)


if __name__ == "__main__":
    main()
