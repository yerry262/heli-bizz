# heli-bizz

Tracks every US helicopter-owning entity (companies, individuals, agencies) from the
FAA aircraft registry. Each run pulls the latest FAA releasable database, keeps only
rotorcraft, flags government owners — and specifically **state/local** government
entities (sheriffs, police, counties, state universities) — and grows an append-only
list run over run: entities are added when first seen and marked removed when they
drop out, never deleted.

**🌐 Live Dashboard: [https://yerry262.github.io/heli-bizz/](https://yerry262.github.io/heli-bizz/)**

## Tech Stack

- **Python 3 (stdlib only)** — `urllib`, `zipfile`, `csv`, `sqlite3`, `json`; no pip installs
- **SQLite** — append-only entity database
- **Static HTML/JS dashboard** — served locally via `serve.py` or on GitHub Pages

## Quickstart

```bash
python3 heli_tracker.py   # download FAA data, update the SQLite DB, export JSON
python3 serve.py          # serve the dashboard and open it in Chrome
```

Stdlib only (urllib, zipfile, csv, sqlite3, json) — no pip installs.

## File layout

```
heli-bizz/
├── heli_tracker.py      # fetch + parse + diff + load pipeline
├── serve.py             # tiny HTTP server that opens the dashboard
├── dashboard/           # built React dashboard (static output, reads data/entities.json)
├── frontend/            # dashboard source (React 19 + esbuild); `npm run build` → dashboard/
├── data/
│   ├── heli.db          # SQLite database
│   └── entities.json    # JSON export for the dashboard
└── README.md
```

## Dashboard

React 19 single-page app ("ROTORWATCH"), bundled offline with esbuild — no CDNs at
runtime. Source lives in `frontend/src/` (`main.jsx`, `styles.css`, `index.html`);
rebuild with `npm run build` inside `frontend/` (outputs `dashboard/app.js`,
`styles.css`, `index.html`). Serve with `python3 serve.py` and open
`http://localhost:8777/dashboard/`.

Features: clickable stat tiles (total / new this run / government / state-local),
debounced search across name/city/N-number, filter chips (All / Government /
State-Local / New / Companies / Individuals), state dropdown plus a clickable SVG
top-15-states bar chart, sortable virtualized table (27k+ rows) with GOV / S/L tags
and a last-action-date column, live "shown / total airframes" readout, slide-in
detail drawer with all fields and an FAA registry link (Escape closes), CSV export
of the current filtered view, dark/light themes via `prefers-color-scheme`.

## Data source

- URL: `https://registry.faa.gov/database/ReleasableAircraft.zip` (~73 MB)
- Must GET with a browser User-Agent (HEAD and default UAs get 403/503), e.g.
  `curl -A "Mozilla/5.0" -o ReleasableAircraft.zip <url>`
- Files used: `MASTER.txt` (registrations) joined to `ACFTREF.txt` (make/model) on
  `MFR MDL CODE = CODE`
- Rotorcraft filter: `TYPE AIRCRAFT` / `TYPE-ACFT` code `6` (gyroplanes are `9` and excluded)
- Format quirks handled: UTF-8 BOM on the header, space-padded fields, trailing comma
  (empty last field), N-numbers without the `N` prefix, `YYYYMMDD` dates
- **Refresh cadence:** the FAA regenerates the file at 11:30 pm Central each federal
  working day, so running more than once a day gains nothing

## Schema (data/heli.db)

```sql
entities(
  n_number TEXT PRIMARY KEY, serial TEXT, registrant_name TEXT, street TEXT,
  city TEXT, state TEXT, zip TEXT, registrant_type_code TEXT, registrant_type TEXT,
  mfr TEXT, model TEXT, year_mfr TEXT, cert_issue_date TEXT, last_action_date TEXT,
  is_government INTEGER, is_state_local INTEGER,
  first_seen TEXT, last_seen TEXT, status TEXT DEFAULT 'active'
);

runs(run_id INTEGER PRIMARY KEY AUTOINCREMENT, ran_at TEXT,
     total INTEGER, new_count INTEGER, removed_count INTEGER);
```

Registrant type codes (MASTER col 6): 1 Individual, 2 Partnership, 3 Corporation,
4 Co-Owned, 5 Government, 7 LLC, 8 Non Citizen Corporation, 9 Non Citizen Co-Owned.

`data/entities.json`: `{"generated_at": ..., "run": {last runs row},
"entities": [all entity columns + "is_new": true if first_seen == latest run date]}`.

## State/local heuristic (and its limits)

`is_state_local = 1` when the registrant type is Government (`5`) AND the registrant
name does **not** match federal patterns (`US`, `U S`, `UNITED STATES`, `FEDERAL`,
`DEPT OF THE ARMY/NAVY/AIR FORCE`, `FBI`, `DEA`, `CBP`, `NOAA`, `NASA`,
`FOREST SERVICE`, ...). That leaves state, county, city, sheriff, police, and
state-university operators.

Limits: it's name-matching, so oddly-named federal agencies can slip through, some
state entities with "US"-like names can be misclassified, and government aircraft
registered under type Corporation/LLC (common for leased or shell-owned fleets) are
missed entirely. Blank registrant types (~1,200 records overall) are treated as
non-government.

## Future ideas

- Cron the tracker via `claude /loop` (or a scheduled routine) for hands-off daily updates
- International registries: Transport Canada, UK CAA G-INFO, EASA member states
- Ownership change detection (same N-number, new registrant) as a lead signal
- Geocode addresses for a map view
