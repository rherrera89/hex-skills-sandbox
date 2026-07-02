# Hex Template Capture — Minimal Build Checklist

**Goal:** build a *small* Hex project with a few native cells so Claude can export it, extract each cell's config as a **clone-and-override template**, and bundle those templates into the migration skill. This is a **bridge** (until Hex's generative/JS app-building supersedes it) — so keep it minimal, don't gold-plate.

**Why templates, not prose:** hand-building native cells from the JSON schema fails on hidden required fields (`displayTableConfig`, `showAllBaseTableDetailFields`). A real exported cell has them all. Prose specs cover *mapping decisions* (which column → which channel); captured JSON covers *structure*.

---

## Step 1 — Create the project
Name it e.g. **`Hex Template Capture (migration reference)`**.

## Step 2 — First cell: sample data (Python) — paste as-is
Everything charts off `sample`. No data connection needed.

```python
import pandas as pd

months = pd.date_range("2024-01-01", periods=18, freq="MS").strftime("%Y-%m")
segments = ["Enterprise", "Mid-Market", "SMB", "Strategic"]
base = {"Enterprise": 90000, "Mid-Market": 45000, "SMB": 15000, "Strategic": 120000}

rows = []
for i, m in enumerate(months):
    for s in segments:
        arr = base[s] * (1 + 0.03 * i) * (0.8 + 0.4 * ((i + hash(s)) % 5) / 5)
        win_rate = round(0.15 + ((i + len(s)) % 6) / 20, 3)   # a fraction, for the combo line
        rows.append({"month": m, "segment": s, "arr": round(arr), "win_rate": win_rate})
sample = pd.DataFrame(rows)
sample.head()
```

## Step 3 — Build these 4 cells (≈ the whole job)

Configure each **deliberately** — the config is what I capture. Label them clearly.

| # | Cell | Configure as | Covers |
|---|------|--------------|--------|
| 1 | **Metric** (KPI) | Value = `sample.arr`, aggregate **Sum**, format **Currency $**, 0 decimals | All KPI tiles |
| 2 | **Chart → Bar** | X=`month`, Y=`arr` (Sum), Color=`segment`, **Stacked**, vertical | Bar (I derive grouped/horizontal by toggling `barGrouped`/`orientation`) |
| 3 | **Chart → Line** | X=`month`, Y=`arr` (Sum), Color=`segment` | Line / area (area = one series-type flip) |
| 4 | **Pivot** | Rows=`segment`, Columns=`month`, Values=`arr` (Sum), totals on | Crosstab / summary table |

### Optional (only if quick) — nice to have, not required
| # | Cell | Configure as | Covers |
|---|------|--------------|--------|
| 5 | **Chart → Combo (dual-axis)** | X=`month`; bar=`arr` (Sum) + line=`win_rate` (Avg) on a **2nd axis** (format %) | Dual-axis combo |

That's it — 4 cells (5 with combo). Grouped bars, horizontal bars, and area charts don't need their own cells; I generate those by overriding the bar/line templates.

## Step 4 — Hand it back
Tell me the **project ID** (or I'll find it via `hex project list`). I'll then:
1. `hex project export` and extract each cell's config → `context/hex_templates/<cellType>.json`.
2. Validate against `https://static.hex.site/hex-file-schema.json`.
3. Fold the templates + a short clone-and-override note into the migration skill.
4. Prove it by cloning one into a throwaway cell and running it green.

---

### Gotchas already learned
- `import` matches cells by `cellId` and **won't change an existing cell's type** — native replacements need **new cellIds**, and `appLayout` must be repointed.
- After import the app view shows an empty "build an app" state until you click **"edit app manually"** once; a fresh version needs `hex project run` before outputs render.
