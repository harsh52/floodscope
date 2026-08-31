"""Export visualization assets for the React results explorer.

For every eval chip we render four georeferenced PNG overlays (SAR, baseline
prediction, agent prediction, ground truth), compute the metrics, and write a
single manifest the front-end reads. We also emit an NDJSON trace of the
deterministic pipeline's steps so the explorer's Trajectory tab has real content
(this is swapped for the LLM agent's trajectory once that lands).

Everything here REUSES the existing science layer — it renders results, it does
not reimplement any flood logic.

    python scripts/export_viz.py                 # all chips in eval/chips.csv
    python scripts/export_viz.py --subset 2      # first 2 chips (quick)
    python scripts/export_viz.py --chips Spain_6860600 Somalia_699062
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image

from floodscope import data
from floodscope.agent.trajectory import Trajectory
from floodscope.agent.traj_render import render_markdown
from floodscope.eval.iou import evaluate
from floodscope.pipeline import FloodConfig, map_flood

ROOT = Path(__file__).resolve().parent.parent
CHIPS_CSV = ROOT / "floodscope" / "eval" / "chips.csv"
WEBVIZ_PUBLIC = ROOT / "webviz" / "public"
TILES_DIR = WEBVIZ_PUBLIC / "tiles"
TRAJ_OUT = WEBVIZ_PUBLIC / "trajectories"

# Display range for SAR VH backscatter (dB) → grayscale.
SAR_DB_LO, SAR_DB_HI = -25.0, 0.0
# Overlay colours (RGB) and alpha for water masks.
COL_BASELINE = (239, 68, 68)    # red
COL_AGENT = (37, 99, 235)       # blue
COL_TRUTH = (34, 197, 94)       # green
MASK_ALPHA = 200


def _load_chips(subset: int | None, only: list[str] | None) -> list[tuple[str, str]]:
    with open(CHIPS_CSV) as f:
        rows = [(r["chip"], r.get("note", "")) for r in csv.DictReader(f)]
    if only:
        rows = [r for r in rows if r[0] in set(only)]
    if subset:
        rows = rows[:subset]
    return rows


def _sar_png(vh_db: np.ndarray) -> Image.Image:
    """VH backscatter → opaque grayscale RGBA image (row 0 = north)."""
    arr = np.asarray(vh_db, dtype="float32")
    finite = np.isfinite(arr)
    norm = np.clip((arr - SAR_DB_LO) / (SAR_DB_HI - SAR_DB_LO), 0.0, 1.0)
    gray = (norm * 255).astype("uint8")
    gray = np.where(finite, gray, 0)
    h, w = gray.shape
    rgba = np.zeros((h, w, 4), dtype="uint8")
    rgba[..., 0] = rgba[..., 1] = rgba[..., 2] = gray
    rgba[..., 3] = np.where(finite, 255, 0)
    return Image.fromarray(rgba, mode="RGBA")


def _mask_png(mask: np.ndarray, color: tuple[int, int, int], alpha: int = MASK_ALPHA) -> Image.Image:
    """Boolean mask → transparent-except-where-True RGBA overlay."""
    m = np.asarray(mask, dtype=bool)
    h, w = m.shape
    rgba = np.zeros((h, w, 4), dtype="uint8")
    rgba[m, 0], rgba[m, 1], rgba[m, 2] = color
    rgba[m, 3] = alpha
    return Image.fromarray(rgba, mode="RGBA")


def _optical_png(chip: str) -> Image.Image | None:
    """Sentinel-2 true-colour (B4/B3/B2) RGBA for a presentable 'imagery' layer.
    Returns None if the optical layer is unavailable."""
    try:
        paths = data.download_chip(chip, kinds=("S2Hand",))
        with rasterio.open(paths["S2Hand"]) as ds:
            # Sen1Floods11 S2Hand is 13-band L1C; true colour = B4,B3,B2 (bands 4,3,2)
            rgb = np.stack([ds.read(4), ds.read(3), ds.read(2)], axis=-1).astype("float32")
    except Exception as e:
        print(f"    (optical unavailable for {chip}: {type(e).__name__})")
        return None
    # reflectance*10000; stretch 0–3000 → 0–255 with a mild gamma for punch
    norm = np.clip(rgb / 3000.0, 0, 1) ** 0.8
    arr = (norm * 255).astype("uint8")
    h, w = arr.shape[:2]
    rgba = np.dstack([arr, np.full((h, w), 255, "uint8")])
    return Image.fromarray(rgba, "RGBA")


# Sen1Floods11 chips are 10 m/pixel.
PIXEL_M = 10.0


def _metrics_dict(res, label) -> dict:
    m = evaluate(res.water, label)
    d = m.as_dict()
    # floats are JSON-friendly; round for a tidy manifest.
    for k in ("iou", "precision", "recall", "f1"):
        d[k] = None if np.isnan(d[k]) else round(float(d[k]), 4)
    valid = int((label != -1).sum())
    d["area_km2"] = round(d["pred_water_px"] * (PIXEL_M ** 2) / 1e6, 2)
    d["area_pct"] = round(100 * d["pred_water_px"] / valid, 1) if valid else None
    d["threshold_method"] = res.threshold_method
    d["threshold_db"] = round(float(res.threshold_db), 2)
    return d


def _write_pipeline_trajectory(chip: str, note: str, res, metrics: dict) -> Path:
    """Emit an NDJSON trace of the deterministic pipeline run for this chip.

    This gives the explorer's Trajectory tab real, honest content today: it is
    the *pipeline* step log (speckle → threshold → cleanup), labelled as such,
    and doubles as a committed trajectory deliverable under trajectories/.
    The LLM agent's trajectory replaces it once the advanced solution runs.
    """
    traj = Trajectory(agent="floodscope-pipeline", case=chip)
    traj.set_phase("analyze")
    traj.system_prompt(
        "Deterministic flood-mapping pipeline. Classify open water in a Sentinel-1 "
        "VV/VH scene using verification-gated thresholding and terrain-aware cleanup."
    )
    traj.user_prompt(f"Map flood water for chip {chip} ({note}).")
    for step in res.provenance.get("steps", []):
        name = step.split("(")[0]
        traj.tool_call(name, {"detail": step})
        traj.tool_result(name, summary=step, ok=True)
    # The verification signal: was the threshold gated to Otsu or forced to fallback?
    method = res.threshold_method
    passed = "fallback" not in method
    traj.verification(
        passed=passed,
        checks={
            "threshold_method": method,
            "bimodal_histogram": passed,
            "note": "Otsu trusted only on genuinely bimodal scenes; else fixed dB fallback.",
        },
    )
    traj.human_review(decision="pending", note="flood map awaiting analyst sign-off before publication")
    traj.checkpoint({"metrics": metrics})
    traj.phase_complete("analyze")
    path = traj.close()
    render_markdown(path)  # human-readable transcript alongside the NDJSON
    return path


def export_chip(chip: str, note: str) -> dict:
    data.download_chip(chip)
    vv, vh = data.read_s1(chip)
    label = data.read_label(chip)
    jrc = data.read_jrc_permanent(chip)
    ref = data.chip_path(chip, "S1Hand")
    bounds_ltrb = data.chip_bounds(chip)  # (left, bottom, right, top) EPSG:4326
    left, bottom, right, top = bounds_ltrb

    base = map_flood(vv, vh, FloodConfig.baseline(), jrc=jrc, ref_tif=ref, bounds=bounds_ltrb)
    agent = map_flood(vv, vh, FloodConfig.full_benchmark(), jrc=jrc, ref_tif=ref, bounds=bounds_ltrb)

    base_m = _metrics_dict(base, label)
    agent_m = _metrics_dict(agent, label)

    # Render + write PNG overlays.
    out = TILES_DIR / chip
    out.mkdir(parents=True, exist_ok=True)
    _sar_png(vh).save(out / "sar.png")
    _mask_png(base.water, COL_BASELINE).save(out / "baseline.png")
    _mask_png(agent.water, COL_AGENT).save(out / "agent.png")
    _mask_png(label == 1, COL_TRUTH).save(out / "truth.png")
    # Optical true-colour imagery for the presentable "before" layer (S2 → SAR fallback).
    optical = _optical_png(chip)
    if optical is not None:
        optical.save(out / "optical.png")
        imagery_rel = f"tiles/{chip}/optical.png"
    else:
        imagery_rel = f"tiles/{chip}/sar.png"

    # Pipeline trajectory → webviz/public/trajectories/<chip>.ndjson
    src = _write_pipeline_trajectory(chip, note, agent, agent_m)
    TRAJ_OUT.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, TRAJ_OUT / f"{chip}.ndjson")

    h, w = label.shape
    return {
        "chip": chip,
        "note": note,
        # Leaflet LatLngBounds order: [[south, west], [north, east]]
        "bounds": [[bottom, left], [top, right]],
        "center": [(bottom + top) / 2, (left + right) / 2],
        "size": [h, w],
        "pixel_m": PIXEL_M,
        "tiles": {**{k: f"tiles/{chip}/{k}.png" for k in ("sar", "baseline", "agent", "truth")},
                  "optical": imagery_rel},
        # Presentable "imagery ↔ prediction" view: same optical imagery both sides,
        # flood prediction overlaid on the right.
        "present": {
            "before": imagery_rel,
            "after": imagery_rel,
            "mask": f"tiles/{chip}/agent.png",
            "before_label": "Satellite imagery",
            "after_label": "Imagery + flood prediction",
            "mask_label": "Flood (agent)",
            "legend": [{"color": "#2563eb", "label": "predicted flood water"}],
        },
        "trajectory": f"trajectories/{chip}.ndjson",
        "metrics": {"baseline": base_m, "agent": agent_m},
        "delta_iou": (
            None if base_m["iou"] is None or agent_m["iou"] is None
            else round(agent_m["iou"] - base_m["iou"], 4)
        ),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--subset", type=int, default=None, help="only first N chips")
    ap.add_argument("--chips", nargs="*", default=None, help="specific chip ids")
    args = ap.parse_args()

    chips = _load_chips(args.subset, args.chips)
    WEBVIZ_PUBLIC.mkdir(parents=True, exist_ok=True)
    # Preserve any live-acquired entries (e.g. Nepal) that this script doesn't produce.
    mpath = WEBVIZ_PUBLIC / "manifest.json"
    existing = json.loads(mpath.read_text()) if mpath.exists() else []
    rebuilt = {c for c, _ in chips}
    manifest = [e for e in existing if e.get("live") or e["chip"] not in rebuilt]
    for chip, note in chips:
        print(f"  exporting {chip} ...", flush=True)
        entry = export_chip(chip, note)
        manifest.append(entry)
        b, a = entry["metrics"]["baseline"]["iou"], entry["metrics"]["agent"]["iou"]
        print(f"    IoU baseline={b} agent={a} Δ={entry['delta_iou']}  [{entry['metrics']['agent']['threshold_method']}]")

    (WEBVIZ_PUBLIC / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nwrote {WEBVIZ_PUBLIC / 'manifest.json'} ({len(manifest)} chips)")
    print(f"tiles → {TILES_DIR}")
    print(f"trajectories → {TRAJ_OUT}")


if __name__ == "__main__":
    main()
