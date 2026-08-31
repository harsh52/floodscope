import type { ChipEntry } from "../types";

const pct = (v: number | null | undefined) => (v == null ? "—" : (v * 100).toFixed(1) + "%");

function Row({ label, b, a }: { label: string; b?: number | null; a?: number | null }) {
  const delta = a != null && b != null ? a - b : null;
  const cls = delta == null ? "" : delta > 0.001 ? "up" : delta < -0.001 ? "down" : "";
  return (
    <tr>
      <td>{label}</td>
      <td className="num">{pct(b)}</td>
      <td className="num">{pct(a)}</td>
      <td className={`num delta ${cls}`}>
        {delta == null ? "—" : (delta >= 0 ? "+" : "") + (delta * 100).toFixed(1)}
      </td>
    </tr>
  );
}

export default function MetricsPanel({ chip }: { chip: ChipEntry }) {
  const { baseline: b, agent: a } = chip.metrics;

  // Headline "area affected" card.
  const areaCard = chip.live ? (
    <div className="areacard">
      <div className="area-main">
        <span className="area-val">{a.surface_water_km2}</span> km²
        <span className="area-sub">surface water mapped</span>
      </div>
      <div className="area-split">
        <div><b>{a.new_inundation_km2}</b> km²<span>inundation vs dry season</span></div>
        <div><b>{a.area_pct}%</b><span>of scene under water</span></div>
      </div>
    </div>
  ) : (
    <div className="areacard">
      <div className="area-main">
        <span className="area-val">{a.area_km2}</span> km²
        <span className="area-sub">flood extent (agent)</span>
      </div>
      <div className="area-split">
        <div><b>{a.area_pct}%</b><span>of scene flooded</span></div>
        <div><b>{b.area_km2}</b> km²<span>baseline (naive)</span></div>
      </div>
    </div>
  );

  return (
    <div className="metrics">
      {areaCard}

      {chip.live ? (
        <div className="provenance">
          <div className="livenote">
            <b>Live scene — no ground truth.</b> Pre/post change detection on freshly-acquired
            Sentinel-1. Method: <code>{a.threshold_method}</code>. Numbers are plausibility-checked,
            not label-verified.
          </div>
        </div>
      ) : (
        <>
          <table>
            <thead>
              <tr>
                <th></th>
                <th className="num">Baseline</th>
                <th className="num">Agent</th>
                <th className="num">Δ pts</th>
              </tr>
            </thead>
            <tbody>
              <Row label="IoU (water)" b={b.iou} a={a.iou} />
              <Row label="Precision" b={b.precision} a={a.precision} />
              <Row label="Recall" b={b.recall} a={a.recall} />
            </tbody>
          </table>
          <div className="provenance">
            <div>
              <span className="swatch base" /> Baseline · <code>{b.threshold_method}</code>
            </div>
            <div>
              <span className="swatch agent" /> Agent · <code>{a.threshold_method}</code>
            </div>
            <div className="pxnote">
              vs ground truth <b>{a.true_water_px?.toLocaleString()}</b> px · agent predicts{" "}
              <b>{a.pred_water_px?.toLocaleString()}</b> px, baseline{" "}
              <b>{b.pred_water_px?.toLocaleString()}</b> px
            </div>
          </div>
        </>
      )}
    </div>
  );
}
