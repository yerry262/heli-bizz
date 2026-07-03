import React, { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { createRoot } from "react-dom/client";

/* ---------- helpers ---------- */
const fmtDate = (s) => {
  if (!s) return "—";
  if (/^\d{8}$/.test(s)) return `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6)}`;
  return s;
};
const fmtNum = (n) => n.toLocaleString("en-US");
const faaUrl = (n) =>
  `https://registry.faa.gov/AircraftInquiry/Search/NNumberResult?nNumberTxt=${encodeURIComponent(n)}`;

const CHIP_DEFS = [
  { id: "all", label: "All" },
  { id: "ems", label: "★ EMS / Air-Medical" },
  { id: "manned", label: "Manned only" },
  { id: "gov", label: "Government" },
  { id: "statelocal", label: "State / Local" },
  { id: "new", label: "New this run" },
  { id: "companies", label: "Companies" },
  { id: "individuals", label: "Individuals" },
  { id: "drones", label: "Drones / UAS" },
];
const COMPANY_CODES = new Set(["2", "3", "4", "7", "8", "9"]);

function chipTest(chip, e) {
  switch (chip) {
    case "ems": return e.is_ems === 1;
    case "manned": return e.is_unmanned !== 1;
    case "drones": return e.is_unmanned === 1;
    case "gov": return e.is_government === 1;
    case "statelocal": return e.is_state_local === 1;
    case "new": return !!e.is_new;
    case "companies": return COMPANY_CODES.has(e.registrant_type_code) && e.is_unmanned !== 1;
    case "individuals": return e.registrant_type_code === "1";
    default: return true;
  }
}

function useDebounced(value, ms) {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

const COLS = [
  { key: "n_number", label: "N-Number", w: "8%" },
  { key: "registrant_name", label: "Registrant", w: "25%" },
  { key: "city", label: "City", w: "12%" },
  { key: "state", label: "ST", w: "4%" },
  { key: "mfr", label: "Manufacturer", w: "16%" },
  { key: "model", label: "Model", w: "11%" },
  { key: "year_mfr", label: "Year", w: "6%" },
  { key: "registrant_type", label: "Type", w: "9%" },
  { key: "last_action_date", label: "Last action", w: "9%" },
];

/* ---------- CSV export ---------- */
function exportCsv(rows) {
  const keys = ["n_number","serial","registrant_name","street","city","state","zip",
    "registrant_type","mfr","model","year_mfr","cert_issue_date","last_action_date",
    "is_ems","is_government","is_state_local","is_unmanned","seats","is_new",
    "first_seen","last_seen","status"];
  const esc = (v) => {
    const s = v == null ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const csv = [keys.join(","), ...rows.map((r) => keys.map((k) => esc(r[k])).join(","))].join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `helicopters_${rows.length}.csv`;
  a.click();
  URL.revokeObjectURL(a.href);
}

/* ---------- stat tile ---------- */
function Tile({ label, value, sub, accent, active, onClick }) {
  return (
    <button className={`tile ${accent || ""} ${active ? "active" : ""}`} onClick={onClick}>
      <span className="tile-label">{label}</span>
      <span className="tile-value">{fmtNum(value)}</span>
      {sub && <span className="tile-sub">{sub}</span>}
    </button>
  );
}

/* ---------- SVG bar chart: top 15 states ---------- */
function BarChart({ title, data, selected, onSelect, labelW = 34, truncate = 0 }) {
  const [hover, setHover] = useState(null);
  if (!data.length) return null;
  const max = data[0][1];
  const rowH = 24, gap = 6, valueW = 56, H = data.length * (rowH + gap) - gap;
  const W = 460, plotW = W - labelW - valueW;
  return (
    <div className="chart-card">
      <div className="chart-title">{title}</div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={title}>
        {data.map(([st, n], i) => {
          const y = i * (rowH + gap);
          const w = Math.max(4, (n / max) * plotW);
          const isSel = selected === st, isHov = hover === st;
          return (
            <g key={st} style={{ cursor: "pointer" }}
              onMouseEnter={() => setHover(st)} onMouseLeave={() => setHover(null)}
              onClick={() => onSelect(isSel ? "" : st)}>
              <rect x="0" y={y} width={W} height={rowH} fill="transparent" />
              <text x={labelW - 8} y={y + rowH / 2} className="chart-cat" dominantBaseline="central" textAnchor="end">{truncate && st.length > truncate ? st.slice(0, truncate - 1) + "…" : st}</text>
              <rect x={labelW} y={y + 3} width={w} height={rowH - 6} rx="4"
                className={`bar ${isSel ? "bar-sel" : ""} ${isHov ? "bar-hov" : ""}`} />
              <text x={labelW + w + 8} y={y + rowH / 2} className="chart-val" dominantBaseline="central">{fmtNum(n)}</text>
            </g>
          );
        })}
      </svg>
      <div className="chart-hint">{selected ? `Filtering: ${selected} — click bar again to clear` : "Click a bar to filter the table"}</div>
    </div>
  );
}

const topCounts = (rows, keyFn, n) => {
  const counts = new Map();
  for (const r of rows) {
    const k = keyFn(r) || "??";
    counts.set(k, (counts.get(k) || 0) + 1);
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, n);
};

/* ---------- detail drawer ---------- */
function Detail({ row, onClose }) {
  if (!row) return null;
  const fields = [
    ["N-Number", row.n_number], ["Serial", row.serial],
    ["Registrant", row.registrant_name], ["Street", row.street],
    ["City", row.city], ["State", row.state], ["ZIP", row.zip],
    ["Registrant type", `${row.registrant_type} (${row.registrant_type_code})`],
    ["Manufacturer", row.mfr], ["Model", row.model], ["Year mfr", row.year_mfr],
    ["Cert issued", fmtDate(row.cert_issue_date)], ["Last action", fmtDate(row.last_action_date)],
    ["EMS / air-medical", row.is_ems ? "Yes — helmet prospect" : "No"],
    ["Unmanned (drone)", row.is_unmanned ? "Yes — no pilot" : "No"],
    ["Seats", row.seats != null && row.seats >= 0 ? row.seats : "—"],
    ["Government", row.is_government ? "Yes" : "No"],
    ["State / local", row.is_state_local ? "Yes" : "No"],
    ["New this run", row.is_new ? "Yes" : "No"],
    ["First seen", row.first_seen], ["Last seen", row.last_seen],
    ["Status", row.status],
  ];
  return (
    <>
      <div className="drawer-scrim" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-label={`Details for N${row.n_number}`}>
        <header className="drawer-head">
          <div>
            <div className="drawer-nnum">N{row.n_number}</div>
            <div className="drawer-name">{row.registrant_name}</div>
          </div>
          <button className="drawer-close" onClick={onClose} aria-label="Close details">✕</button>
        </header>
        <dl className="drawer-fields">
          {fields.map(([k, v]) => (
            <div className="field" key={k}><dt>{k}</dt><dd>{v || "—"}</dd></div>
          ))}
        </dl>
        <a className="faa-link" href={faaUrl(row.n_number)} target="_blank" rel="noreferrer">
          Open in FAA registry ↗
        </a>
      </aside>
    </>
  );
}

/* ---------- virtualized table ---------- */
const ROW_H = 36;
function VTable({ rows, sort, onSort, onRow }) {
  const outer = useRef(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [viewH, setViewH] = useState(600);
  useEffect(() => {
    const el = outer.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setViewH(el.clientHeight));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const onScroll = useCallback((e) => setScrollTop(e.currentTarget.scrollTop), []);
  const total = rows.length * ROW_H;
  const start = Math.max(0, Math.floor(scrollTop / ROW_H) - 8);
  const end = Math.min(rows.length, Math.ceil((scrollTop + viewH) / ROW_H) + 8);
  const slice = rows.slice(start, end);
  return (
    <div className="vtable">
      <div className="vhead" role="row">
        {COLS.map((c) => (
          <button key={c.key} style={{ width: c.w }} className="vth" onClick={() => onSort(c.key)}>
            {c.label}
            <span className="sort-ind">{sort.key === c.key ? (sort.dir === 1 ? "▲" : "▼") : ""}</span>
          </button>
        ))}
      </div>
      <div className="vbody" ref={outer} onScroll={onScroll}>
        <div style={{ height: total, position: "relative" }}>
          {slice.map((r, i) => {
            const idx = start + i;
            return (
              <div key={r.n_number + "-" + idx} className="vrow"
                style={{ transform: `translateY(${idx * ROW_H}px)` }}
                onClick={() => onRow(r)}>
                <span style={{ width: COLS[0].w }} className="cell mono">N{r.n_number}{r.is_new ? <em className="new-dot" title="New this run" /> : null}</span>
                <span style={{ width: COLS[1].w }} className="cell">
                  {r.registrant_name}
                  {r.is_ems === 1 ? <i className="tag tag-ems">EMS</i> : null}
                  {r.is_government === 1 ? <i className="tag tag-gov">GOV</i> : null}
                  {r.is_state_local === 1 ? <i className="tag tag-sl">S/L</i> : null}
                  {r.is_unmanned === 1 ? <i className="tag tag-uas">UAS</i> : null}
                </span>
                <span style={{ width: COLS[2].w }} className="cell">{r.city}</span>
                <span style={{ width: COLS[3].w }} className="cell mono">{r.state}</span>
                <span style={{ width: COLS[4].w }} className="cell dim">{r.mfr}</span>
                <span style={{ width: COLS[5].w }} className="cell dim">{r.model}</span>
                <span style={{ width: COLS[6].w }} className="cell mono">{r.year_mfr || "—"}</span>
                <span style={{ width: COLS[7].w }} className="cell dim">{r.registrant_type}</span>
                <span style={{ width: COLS[8].w }} className="cell mono dim">{fmtDate(r.last_action_date)}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/* ---------- operators view ---------- */
function OpTable({ groups, onPick }) {
  const shown = groups.slice(0, 500);
  return (
    <div className="optable">
      <div className="vhead" role="row">
        <span className="vth" style={{ width: "10%" }}>Fleet</span>
        <span className="vth" style={{ width: "44%" }}>Operator</span>
        <span className="vth" style={{ width: "26%" }}>Cities</span>
        <span className="vth" style={{ width: "6%" }}>ST</span>
        <span className="vth" style={{ width: "14%" }}>Type</span>
      </div>
      <div className="vbody opbody">
        {shown.map((g) => (
          <div key={g.key} className="vrow" style={{ position: "static", transform: "none" }} onClick={() => onPick(g)}>
            <span className="cell mono" style={{ width: "10%" }}>{fmtNum(g.count)}</span>
            <span className="cell" style={{ width: "44%" }}>
              {g.name}
              {g.gov ? <i className="tag tag-gov">GOV</i> : null}
              {g.sl ? <i className="tag tag-sl">S/L</i> : null}
            </span>
            <span className="cell dim" style={{ width: "26%" }}>{g.cities}</span>
            <span className="cell mono" style={{ width: "6%" }}>{g.state}</span>
            <span className="cell dim" style={{ width: "14%" }}>{g.type}</span>
          </div>
        ))}
        {groups.length > shown.length && (
          <div className="op-more">Showing top {fmtNum(shown.length)} of {fmtNum(groups.length)} operators — narrow the filters to see more.</div>
        )}
      </div>
    </div>
  );
}

/* ---------- saved views ---------- */
const PRESET_KEY = "rotorwatch.presets";
const loadPresets = () => {
  try { return JSON.parse(localStorage.getItem(PRESET_KEY)) || []; } catch { return []; }
};

/* ---------- app ---------- */
function App() {
  const [payload, setPayload] = useState(null);
  const [err, setErr] = useState(null);
  const [query, setQuery] = useState("");
  const q = useDebounced(query, 200);
  const [chip, setChip] = useState("all");
  const [stateSel, setStateSel] = useState("");
  const [mfrSel, setMfrSel] = useState("");
  const [sort, setSort] = useState({ key: "registrant_name", dir: 1 });
  const [detail, setDetail] = useState(null);
  const [view, setView] = useState("aircraft");
  const [presets, setPresets] = useState(loadPresets);

  const savePreset = () => {
    const name = window.prompt("Name this view:", stateSel || chip !== "all" ? `${chip}${stateSel ? " · " + stateSel : ""}` : "My view");
    if (!name) return;
    const next = [...presets.filter((p) => p.name !== name), { name, chip, stateSel, mfrSel, query }];
    setPresets(next);
    localStorage.setItem(PRESET_KEY, JSON.stringify(next));
  };
  const applyPreset = (p) => { setChip(p.chip); setStateSel(p.stateSel); setMfrSel(p.mfrSel || ""); setQuery(p.query); };
  const removePreset = (name) => {
    const next = presets.filter((p) => p.name !== name);
    setPresets(next);
    localStorage.setItem(PRESET_KEY, JSON.stringify(next));
  };

  useEffect(() => {
    // Works in both layouts: local serve.py (page at /dashboard/, data at
    // /data/) and GitHub Pages (dashboard flattened to site root, data at
    // ./data/). Try same-level first, then the parent-level fallback.
    const candidates = ["data/entities.json", "../data/entities.json"];
    (async () => {
      let lastErr = "not found";
      for (const url of candidates) {
        try {
          const r = await fetch(url);
          if (r.ok) { setPayload(await r.json()); return; }
          lastErr = `HTTP ${r.status}`;
        } catch (e) { lastErr = String(e); }
      }
      setErr(lastErr);
    })();
  }, []);
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && setDetail(null);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const entities = payload ? payload.entities : [];

  const stats = useMemo(() => ({
    total: entities.length,
    manned: entities.filter((e) => e.is_unmanned !== 1).length,
    ems: entities.filter((e) => e.is_ems === 1).length,
    gov: entities.filter((e) => e.is_government === 1).length,
    stateLocal: entities.filter((e) => e.is_state_local === 1).length,
  }), [entities]);

  const states = useMemo(
    () => [...new Set(entities.map((e) => e.state).filter(Boolean))].sort(),
    [entities]
  );

  const filtered = useMemo(() => {
    const needle = q.trim().toUpperCase();
    let rows = entities;
    if (chip !== "all") rows = rows.filter((e) => chipTest(chip, e));
    if (stateSel) rows = rows.filter((e) => e.state === stateSel);
    if (mfrSel) rows = rows.filter((e) => e.mfr === mfrSel);
    if (needle) {
      rows = rows.filter((e) =>
        (e.registrant_name && e.registrant_name.includes(needle)) ||
        (e.city && e.city.includes(needle)) ||
        (e.n_number && e.n_number.includes(needle))
      );
    }
    return rows;
  }, [entities, chip, stateSel, mfrSel, q]);

  const stateData = useMemo(() => topCounts(entities, (e) => e.state, 15), [entities]);
  const mfrData = useMemo(() => topCounts(entities, (e) => e.mfr, 12), [entities]);

  const sorted = useMemo(() => {
    const { key, dir } = sort;
    const numeric = key === "year_mfr";
    return [...filtered].sort((a, b) => {
      let av = a[key] || "", bv = b[key] || "";
      if (numeric) { av = +av || 0; bv = +bv || 0; return (av - bv) * dir; }
      return av < bv ? -dir : av > bv ? dir : 0;
    });
  }, [filtered, sort]);

  const operators = useMemo(() => {
    if (view !== "operators") return [];
    const map = new Map();
    for (const e of filtered) {
      const key = `${e.registrant_name}|${e.state}`;
      let g = map.get(key);
      if (!g) {
        g = { key, name: e.registrant_name, state: e.state, count: 0, citySet: new Set(),
              gov: e.is_government === 1, sl: e.is_state_local === 1, type: e.registrant_type };
        map.set(key, g);
      }
      g.count++;
      if (e.city) g.citySet.add(e.city);
    }
    return [...map.values()]
      .map((g) => ({ ...g, cities: [...g.citySet].slice(0, 3).join(", ") + (g.citySet.size > 3 ? "…" : "") }))
      .sort((a, b) => b.count - a.count || (a.name < b.name ? -1 : 1));
  }, [filtered, view]);

  const pickOperator = (g) => { setQuery(g.name); setView("aircraft"); };

  const onSort = (key) =>
    setSort((s) => (s.key === key ? { key, dir: -s.dir } : { key, dir: 1 }));

  if (err) return <div className="load-state">Could not load data: {err}<br />Serve this page with serve.py from the repo root.</div>;
  if (!payload) return <div className="load-state"><span className="rotor" />Loading 27,000+ registrations…</div>;

  return (
    <div className="shell">
      <header className="masthead">
        <div className="brand">
          <span className="rotor rotor-small" aria-hidden="true" />
          <div>
            <h1>ROTORWATCH</h1>
            <p className="tagline">U.S. civil helicopter registry · run #{payload.run.run_id} · {new Date(payload.generated_at).toLocaleDateString()}</p>
          </div>
        </div>
        <div className="readout" aria-live="polite">
          <span className="readout-n">{fmtNum(sorted.length)}</span>
          <span className="readout-d"> / {fmtNum(stats.total)} airframes</span>
        </div>
        <button className="export" onClick={() => exportCsv(sorted)}>
          Export CSV ({fmtNum(sorted.length)} rows)
        </button>
      </header>

      <section className="tiles">
        <Tile label="Registered rotorcraft" value={stats.total} sub={`${fmtNum(stats.manned)} manned · ${fmtNum(stats.total - stats.manned)} drones`} accent="t-amber" active={chip === "all" && !stateSel && !mfrSel && !query} onClick={() => { setChip("all"); setStateSel(""); setMfrSel(""); setQuery(""); }} />
        <Tile label="★ EMS / Air-Medical" value={stats.ems} sub="premier helmet market" accent="t-teal" active={chip === "ems"} onClick={() => setChip("ems")} />
        <Tile label="Government" value={stats.gov} accent="t-blue" active={chip === "gov"} onClick={() => setChip("gov")} />
        <Tile label="State / local agencies" value={stats.stateLocal} accent="t-violet" active={chip === "statelocal"} onClick={() => setChip("statelocal")} />
      </section>

      <div className="deck">
        <div className="chart-stack">
          <BarChart title="Top 15 states by helicopter count" data={stateData} selected={stateSel} onSelect={setStateSel} />
          <BarChart title="Top 12 manufacturers" data={mfrData} selected={mfrSel} onSelect={setMfrSel} labelW={130} truncate={18} />
        </div>

        <div className="table-card">
          <div className="controls">
            <input className="search" type="search" placeholder="Search name, city, or N-number…"
              value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Search registrations" />
            <select className="state-select" value={stateSel} onChange={(e) => setStateSel(e.target.value)} aria-label="Filter by state">
              <option value="">All states</option>
              {states.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div className="chips" role="tablist">
            {CHIP_DEFS.map((c) => (
              <button key={c.id} className={`chip ${chip === c.id ? "on" : ""}`} onClick={() => setChip(c.id)}>{c.label}</button>
            ))}
            <span className="view-toggle">
              <button className={`chip ${view === "aircraft" ? "on" : ""}`} onClick={() => setView("aircraft")}>Aircraft</button>
              <button className={`chip ${view === "operators" ? "on" : ""}`} onClick={() => setView("operators")}>Operators</button>
            </span>
            <span className="count">{view === "operators" ? `${fmtNum(operators.length)} operators` : `${fmtNum(sorted.length)} shown`}</span>
          </div>
          {(presets.length > 0 || chip !== "all" || stateSel || query) && (
            <div className="presets">
              <button className="chip chip-save" onClick={savePreset} title="Save current search, chip, and state filters">★ Save view</button>
              {presets.map((p) => (
                <span key={p.name} className="preset">
                  <button className="chip" onClick={() => applyPreset(p)}>{p.name}</button>
                  <button className="preset-x" onClick={() => removePreset(p.name)} aria-label={`Delete view ${p.name}`}>✕</button>
                </span>
              ))}
            </div>
          )}
          {view === "operators"
            ? <OpTable groups={operators} onPick={pickOperator} />
            : <VTable rows={sorted} sort={sort} onSort={onSort} onRow={setDetail} />}
        </div>
      </div>

      <Detail row={detail} onClose={() => setDetail(null)} />
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
