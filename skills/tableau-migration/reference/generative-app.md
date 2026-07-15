# Building a generative (React) app

An alternative to the classic native-cell app. **Same SQL cells, different presentation layer** — instead of native chart cells laid out in an `appLayout` grid, a generative app renders the data with **React** (the `genAppFiles`). A generative app is *not* a cell type; it's a project-level app mode over the cells you already built.

## Classic vs generative — pick with the customer
| | Classic native-cell app | Generative app |
|---|---|---|
| Charts | native Hex cells (METRIC/EXPLORE) | React components (d3) you author |
| Look & feel | native Hex | fully custom — match Tableau closely / go fancier |
| Interactivity | native (drill, explore, filters) | only what you code |
| Embedded **agent / Threads chat** | ✅ can include | ❌ none (bespoke UI) |
| Build cost | deterministic clone-and-override | agent writes React (does this well), but you maintain it |
| Best for | fast, faithful, self-serve + chat | pixel/brand fidelity, custom UX |

**Phase 1 (Tableau → consolidated SQL) is identical** — only this build step differs. Ask the customer which they want *before* building the presentation.

## Anatomy (project YAML)
Beyond `cells`, a generative app adds:
- **`genAppFiles`** — an array of `{ path, contents }`, i.e. a small React project:
  - `App.js` — entry; composes the page and ends with `render(h(App))`.
  - `components/*.js` — chart/UI components (BarChart, LineChart, DonutChart, DataTable, KpiCard, …).
  - `lib/*.js` — helpers (formatting, etc.).
  - `app.css` — styles; use Hex theme CSS vars (`var(--color-*)`, `var(--space-*)`).
- **`dataAppCellIds`** — the cell IDs the app reads.
- `appLayout` still exists and coexists; the app view uses the generative one.

## Runtime contract (`app/_data.js`)
```js
import { React, render, useHexData, LucideIcons, d3 } from "app/_data.js";
const h = React.createElement;

// read a SQL cell's output BY CELL ID → { rows: [ { COL: value, ... }, ... ] }
const { rows } = useHexData("<sql-cell-id>");   // row keys are the SQL columns (UPPERCASE for Snowflake)

render(h(App));   // mount at the end of App.js
```
- Components `import { React }` (and `d3` for charts) from `"app/_data.js"`, and `import "app/app.css"`.
- `useHexData` binds to a cell by its **ID** (from the export), not its result-variable name.

## Build recipe
1. **Build the consolidated SQL cells** exactly as in Phase 1 (shared with the classic path). Note each cell's `id` — that's the argument to `useHexData`.
2. **Get a component kit** — either:
   - **Write from scratch** — author small React components per chart type (bar/line/donut/table/KPI) following the contract above (`d3` is available). Agents do this well.
   - **Reuse the reference kit** (if you have access) — export the reference generative app and copy its `components/` + `lib/` + `app.css` verbatim, then read each component's JSDoc header for its props:
     ```bash
     hex project export 019f383d-dfdf-712c-8bbb-ea53f96d3a0f -o inventory-app.yaml --profile app
     ```
     ("Inventory and shipping performance" — a full kit: BarChart, LineChart, DonutChart, DataTable, KpiCard, Tabs, Select, Switch, Tooltip, DatePicker, `lib/format.js`. Each file's top comment documents its props.)
3. **Author `App.js`** — map each Tableau worksheet to a component and wire it to its SQL cell via `useHexData(cellId)`:
   ```js
   import "app/app.css";
   import { React, render, useHexData } from "app/_data.js";
   import { BarChart } from "app/components/BarChart.js";
   import { KpiCard } from "app/components/KpiCard.js";
   import { fmtMoney, firstRow } from "app/lib/format.js";
   const h = React.createElement;

   function TotalArr() {
     const { rows } = useHexData("<total-arr-cell-id>");        // [{ TOTAL_ARR: 509000 }]
     return h(KpiCard, { label: "Total ARR", value: fmtMoney(firstRow(rows)?.TOTAL_ARR) });
   }
   function ArrByStage() {
     const { rows } = useHexData("<arr-by-stage-cell-id>");     // [{ STAGE_NAME, ARR }, ...]
     return h(BarChart, { data: rows, x: "STAGE_NAME", y: "ARR" });
   }
   function App() {
     return h("div", { className: "app" }, h(TotalArr), h(ArrByStage));
   }
   render(h(App));
   ```
4. **Set `dataAppCellIds`** to the SQL cell IDs the app uses.
5. **Import → run → QA** — `hex project import`, then `hex project run`, then hand the link to the customer. Same mechanics as the classic path. (Confirm the import round-trips `genAppFiles`; the contents are plain JS strings in the YAML.)

## Tableau viz → generative component
| Tableau | Component |
|---|---|
| KPI / big number | `KpiCard` |
| bar / stacked bar | `BarChart` |
| line / area | `LineChart` |
| pie / donut | `DonutChart` |
| crosstab / text table | `DataTable` |
| parameter / filter control | `Select` / `Switch` / `DatePicker` (drive via a Hex input or client state) |
| map | still a Python cell (no React map in the kit) unless a React map lib is warranted |

## Keep in mind
- **Accuracy first, same as classic** — the SQL is the source of truth; React is presentation. The upstream rules (consolidation, filter-scope sweep, data types) are unchanged.
- **No embedded agent** — if the customer wants chat-with-data / Threads / the Notebook Agent, that's a reason to pick the classic native-cell app (or offer both).
- Validate the YAML the same way (`*.hex.yaml` + RedHat extension); `genAppFiles` contents are plain JS strings.
