# Visual-QA loop (headless screenshot → diff → fix)

The **render gate for the generative-app build** (the default). A Generative app has
no diff-able native cells, so the *rendered app* is how you verify look & feel. This
loop closes the blind spot the rest of the skill punts on ("the agent can't render
the app; it's behind login") — it renders the app headlessly with a **persistent
browser profile the customer logs into once**, diffs it panel-by-panel against the
original Looker dashboard PNG, and feeds the notebook agent surgical fixes until
parity.

> **Not a credential-entry step.** The agent never types a password. The *customer*
> logs into Hex **once**, in a headed browser, into a local profile that persists.
> Every later round reuses that saved session and is fully headless. This is the
> customer authenticating their own browser — consistent with the skill's "never
> enter credentials" rule.

## The two screenshot sources

| Side | Tool | Auth | Notes |
|---|---|---|---|
| **Source (Looker)** | `scripts/looker_fetch.py shots <dashboard_id>` | the same API3 key the rest of the skill uses | renders the dashboard to PNG via Looker's **render-task API** (`POST /render_tasks/dashboards/{id}/png` → poll → fetch). Fully headless, no browser. |
| **Migrated (Hex)** | `scripts/hex_shots.py` | one-time headed customer login → persistent profile | Playwright; the agent never types the password. |

The Looker side is a clean API render (no Playwright/login needed) — a nicer setup
than the Tableau skill's source capture. The Hex side needs the one-time login.

> **Looks:** `looker_fetch.py shots` renders **dashboards**. A single **Look** (the
> thin one-tile case) has no dashboard to capture — QA it with a human side-by-side
> against the Look in Looker, or add a `render_tasks/looks/{id}/png` call if you need
> an automated source PNG.

## One-time setup (Phase 0)

`scripts/hex_shots.py` drives Playwright against a **persistent profile** stored in
`working/hex-screenshot-profile/` (gitignored). The first run is **headed** so the
customer signs in; the session is saved and every later run is headless.

```bash
pip install playwright && playwright install chromium   # once
python scripts/hex_shots.py --login                      # headed: customer signs into Hex, then presses Enter
```

After that, capture is one command per app URL:

```bash
python scripts/hex_shots.py "<hex_app_url>" -o working/shots/migrated.png
```

Source dashboard PNGs need no setup beyond the Looker credentials already in
`credentials/looker.env`:

```bash
python3 scripts/looker_fetch.py shots <dashboard_id> -o working/shots/looker-<id>.png
```

- **Unpublished Hex drafts** show a URL lock screen. `hex_shots.py` opens the
  **editor** directly and clicks **App builder** to reveal the rendered app without
  publishing — so you can QA before the app is ever shared.
- **Full-app capture:** `full_page=True` alone only grabs the outer viewport (the Hex
  app is an inner scroll container). The script scrolls the app container and
  stitches, or captures the app-canvas element directly. If a capture looks clipped,
  that's the first thing to check (note in the pilot tune).
- **Looker render size:** pass `--width`/`--height` to `shots` to match the source
  dashboard's aspect so panels line up in the diff.

## The loop

Repeat until the diff is clean — typically **3+ rounds**. Never assume a fix landed;
**re-screenshot and re-diff every round.**

```
1. screenshot the Hex app (headless)  +  render the source PNG (looker_fetch.py shots)
2. diff panel-by-panel — for each dashboard tile, compare:
     • layout / position / relative size
     • the numbers (against the gated SQL cells + Looker's own values, not just the picture)
     • filter + parameter wiring (does changing an input move the right panels?)
     • colors (vs. the styling-spec hex codes), titles, tooltip fields, number/date formats
3. zero discrepancies? → EXIT (hand to human for final confirm)
   else → continue
4. send ONE coherent fix batch:  hex thread continue <thread_id> "<numbered fix list>"
5. wait for IDLE, then go to 1
```

### Diffing well
- **Read the image pair and compare per-panel against a fixed checklist** (layout,
  numbers, filters, colors, titles, tooltips, formats) — a whole-image pixel diff is
  noisy (fonts/antialiasing differ) and misses semantic errors. Go tile by tile.
- **Numbers are verified against the gated SQL cells** (and Looker's own values via
  `looker_fetch.py query`), not the rendered picture — the screenshot confirms the
  *right value is displayed in the right place*, the SQL gate confirms the value is
  *correct*. Both are needed. → [`sql-review.md`](sql-review.md) §4a.
- **Keep each `continue` batch surgical and numbered** — one coherent set of fixes per
  round ("1. Total ARR KPI should be currency with 0 decimals; 2. move the trend
  chart above the table; 3. segment colors are #1f77b4/#ff7f0e, not the defaults").
  Vague or sprawling prompts make the agent thrash.

## Exit

The loop exits when a round produces zero discrepancies. Then do the **final human
confirm**: hand the customer the app link + the original Looker PNGs side-by-side.
The loop gets you to near-parity automatically; the human signs off. (Same human
gate as the rest of the skill — but now they're confirming a near-match, not finding
the errors.)

## Cheat-sheet

- Setup once: `pip install playwright && playwright install chromium`, then `python scripts/hex_shots.py --login`.
- Hex capture: `python scripts/hex_shots.py "<url>" -o working/shots/migrated.png` (headless, reuses the profile).
- Looker source PNG: `python3 scripts/looker_fetch.py shots <dashboard_id> -o working/shots/looker-<id>.png` (API render, no browser).
- Fix: `hex thread continue <thread_id> "<numbered fix list>"` → re-capture → re-diff.
- Profile lives in `working/hex-screenshot-profile/` (gitignored); never commit it.
