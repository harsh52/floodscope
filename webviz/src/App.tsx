import { useEffect, useMemo, useState } from "react";
import type { ChipEntry, Mode } from "./types";
import { asset } from "./asset";
import MapView from "./components/MapView";
import MetricsPanel from "./components/MetricsPanel";
import TrajectoryTab from "./components/TrajectoryTab";

export default function App() {
  const [chips, setChips] = useState<ChipEntry[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const mode: Mode = "present"; // baseline submission: before/after only
  const [tab, setTab] = useState<"metrics" | "trajectory">("metrics");
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    fetch(asset("manifest.json"))
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((data: ChipEntry[]) => {
        // Live scenes first, then biggest agent win.
        data.sort((x, y) => {
          if (!!y.live !== !!x.live) return y.live ? 1 : -1;
          return (y.delta_iou ?? -1) - (x.delta_iou ?? -1);
        });
        setChips(data);
        setSelected(data[0]?.chip ?? null);
      })
      .catch((e) => setErr(String(e)));
  }, []);

  const chip = useMemo(() => chips.find((c) => c.chip === selected) ?? null, [chips, selected]);

  if (err)
    return (
      <div className="fatal">
        Could not load <code>manifest.json</code> — run <code>python scripts/export_viz.py</code>{" "}
        first. ({err})
      </div>
    );
  if (!chip) return <div className="fatal">Loading…</div>;

  const labels = [chip.present?.before_label ?? "Before", chip.present?.after_label ?? "After"];

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          FloodScope <span className="sub">· results explorer</span>
        </div>
        <div className="tagline">
          Satellite flood mapping — before/after imagery, agent prediction, and area affected
        </div>
      </header>

      <div className="layout">
        <aside className="rail">
          <div className="rail-head">{chips.length} scene{chips.length === 1 ? "" : "s"}</div>
          <ul className="chiplist">
            {chips.map((c) => (
              <li
                key={c.chip}
                className={c.chip === selected ? "sel" : ""}
                onClick={() => setSelected(c.chip)}
              >
                <div className="chip-name">
                  {c.live && <span className="live-badge">LIVE</span>}
                  {c.chip}
                </div>
                <div className="chip-note">{c.note}</div>
                <div className="chip-metrics">
                  {c.live ? (
                    <span className="badge">{c.metrics.agent.surface_water_km2} km² water</span>
                  ) : (
                    <>
                      <span className="badge">IoU {fmt(c.metrics.baseline.iou)}→{fmt(c.metrics.agent.iou)}</span>
                      <span className={`badge delta ${deltaCls(c.delta_iou)}`}>
                        {c.delta_iou == null ? "" : (c.delta_iou >= 0 ? "+" : "") + c.delta_iou.toFixed(3)}
                      </span>
                    </>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </aside>

        <main className="stage">
          <div className="mapwrap">
            <MapView chip={chip} mode={mode} />
            <div className="swipe-labels">
              <span className="slab">◀ {labels[0]}</span>
              <span className="slab">{labels[1]} ▶</span>
            </div>
            {mode === "present" && chip.present?.legend && (
              <div className="legend">
                {chip.present.legend.map((l) => (
                  <span key={l.label}>
                    <i style={{ background: l.color }} />
                    {l.label}
                  </span>
                ))}
              </div>
            )}
          </div>
          <div className="controls">
            <span className="mode-label">Before / After</span>
            <span className="hint">drag the ⇔ divider to compare</span>
          </div>
        </main>

        <aside className="panel">
          <div className="tabs">
            <button className={tab === "metrics" ? "on" : ""} onClick={() => setTab("metrics")}>
              Metrics
            </button>
            <button className={tab === "trajectory" ? "on" : ""} onClick={() => setTab("trajectory")}>
              Trajectory
            </button>
          </div>
          <div className="panel-title">
            {chip.chip} <span className="muted">· {chip.note}</span>
          </div>
          {tab === "metrics" ? <MetricsPanel chip={chip} /> : <TrajectoryTab chip={chip} />}
        </aside>
      </div>
    </div>
  );
}

const fmt = (v: number | null | undefined) => (v == null ? "—" : v.toFixed(2));
const deltaCls = (d: number | null) => (d == null ? "" : d > 0.001 ? "up" : d < -0.001 ? "down" : "");
