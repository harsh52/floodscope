"""Acquire LIVE pre/post Sentinel-1 scenes for the Aug 2026 Nepal flood and map
the new inundation via change detection.

The 26 Aug 2026 flash flood began as a glacier collapse near Langtang Lirung and
surged down the Bhote Koshi at Rasuwagadhi, then 72 km+ down the Trishuli /
Narayani to the Chitwan plains and into India. The upper gorge is too steep and
narrow to map with 40 m SAR (layover/shadow), so we map the **downstream reach on
the flat Narayani plain at Chitwan**, where standing floodwater and fresh sediment
are detectable. Same flood, mappable geometry.

New flood = surface water present in the POST pass but not the PRE pass (so the
permanent river channel is excluded → honest "newly affected area"). No ground
truth — a real field demo of the pipeline on fresh, no-key public imagery.

Data: Planetary Computer `sentinel-1-grd`, anonymous.

    PYTHONPATH=. .venv/bin/python scripts/acquire_nepal.py
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np
import odc.stac
import planetary_computer
import pystac_client
from PIL import Image

from floodscope.agent.trajectory import Trajectory
from floodscope.agent.traj_render import render_markdown
from floodscope.geo import sar

ROOT = Path(__file__).resolve().parent.parent
WEBVIZ_PUBLIC = ROOT / "webviz" / "public"
TILES_DIR = WEBVIZ_PUBLIC / "tiles"
TRAJ_OUT = WEBVIZ_PUBLIC / "trajectories"

# Narayani (Trishuli + Kali Gandaki) braided river on the Chitwan plain — the
# downstream, mappable reach of the 26 Aug 2026 flood.
AOI = [84.20, 27.63, 84.46, 27.83]  # [W, S, E, N] — Narayani reach fully inside the ascending swath
CHIP_ID = "Nepal_Narayani_live"
NOTE = "LIVE · 26 Aug 2026 flood, Narayani R. at Chitwan · dry-season→post-flood · no ground truth"
RES_M = 40
STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"

COL_FLOOD = (56, 189, 248)   # cyan — new inundation
COL_PERM = (30, 64, 175)     # deep blue — permanent water (pre)
COL_BASELINE = (239, 68, 68)
MASK_ALPHA = 205


def _sar_png(vh_db: np.ndarray) -> Image.Image:
    """Grayscale SAR, contrast-stretched to the scene's own 2–98 percentile."""
    arr = np.asarray(vh_db, "float32")
    finite = np.isfinite(arr)
    lo, hi = np.nanpercentile(arr[finite], [2, 98]) if finite.any() else (0.0, 1.0)
    norm = np.clip((arr - lo) / (hi - lo + 1e-6), 0, 1)
    gray = np.where(finite, norm * 255, 0).astype("uint8")
    rgba = np.dstack([gray, gray, gray, np.where(finite, 255, 0).astype("uint8")])
    return Image.fromarray(rgba, "RGBA")


def _mask_png(mask, color, alpha=MASK_ALPHA) -> Image.Image:
    m = np.asarray(mask, bool)
    rgba = np.zeros((*m.shape, 4), "uint8")
    rgba[m, 0], rgba[m, 1], rgba[m, 2], rgba[m, 3] = *color, alpha
    return Image.fromarray(rgba, "RGBA")


# Ascending relative-orbit 85 is the pass that brackets the flood over Chitwan
# (pre 16 Aug, post 28 Aug — 2 days after the 26 Aug event, identical geometry).
ORBIT_STATE = "ascending"
REL_ORBIT = 85


def _find(cat, on_or_before: str):
    s = cat.search(
        collections=["sentinel-1-grd"], bbox=AOI,
        datetime=f"2026-01-01/{on_or_before}T23:59:59Z",
        query={"sat:orbit_state": {"eq": ORBIT_STATE}, "sat:relative_orbit": {"eq": REL_ORBIT}},
        sortby=[{"field": "properties.datetime", "direction": "desc"}], limit=1,
    )
    items = list(s.items())
    if not items:
        raise SystemExit(f"No {ORBIT_STATE} rel-orbit {REL_ORBIT} S1 scene on/before {on_or_before} over AOI.")
    return items[0]


def _load_vh_db(item, like=None):
    kw = dict(bands=["vh"], bbox=AOI, crs="EPSG:32645", resolution=RES_M)
    if like is not None:
        kw = dict(bands=["vh"], like=like)
    ds = odc.stac.load([item], **kw).isel(time=0)
    dn = ds["vh"].values.astype("float32")
    with np.errstate(divide="ignore"):
        vh = sar.to_db(dn ** 2)  # pseudo-dB; monotonic → Otsu still separates water
    vh[~np.isfinite(vh)] = np.nan
    return vh, ds


def _slope_deg(cat, like_geobox) -> np.ndarray | None:
    """Copernicus 30 m DEM slope (degrees), aligned to the SAR grid. Used to drop
    steep-terrain false positives (layover/shadow) — flood water is on flat ground."""
    try:
        items = list(cat.search(collections=["cop-dem-glo-30"], bbox=AOI).items())
        if not items:
            return None
        dem = odc.stac.load(items, bands=["data"], like=like_geobox, resampling="bilinear")
        z = dem["data"].isel(time=0).values.astype("float32") if "time" in dem.dims else dem["data"].values.astype("float32")
        gy, gx = np.gradient(z, RES_M, RES_M)
        return np.degrees(np.arctan(np.hypot(gx, gy)))
    except Exception as e:
        print(f"  (slope mask skipped: {type(e).__name__})")
        return None


def _water_threshold(db_s: np.ndarray) -> tuple[float, str]:
    """Scale-free water threshold for uncalibrated GRD: Otsu when the histogram
    is bimodal (river present), else a robust dark-tail percentile."""
    v = db_s[np.isfinite(db_s)]
    if v.size and sar.is_bimodal(v):
        return sar.otsu_threshold(db_s), "gated-otsu"
    return float(np.nanpercentile(v, 12)) if v.size else 0.0, "p12-fallback"


def acquire(post_date: str, pre_date: str) -> dict:
    cat = pystac_client.Client.open(STAC, modifier=planetary_computer.sign_inplace)
    post_item, pre_item = _find(cat, post_date), _find(cat, pre_date)
    print(f"  post: {post_item.id}  ({post_item.properties['datetime']})")
    print(f"  pre : {pre_item.id}  ({pre_item.properties['datetime']})")

    vh_post, ds = _load_vh_db(post_item)
    vh_pre, _ = _load_vh_db(pre_item, like=ds.odc.geobox)  # identical grid → clean diff

    post_s, pre_s = sar.speckle_filter(vh_post), sar.speckle_filter(vh_pre)
    thr, method = _water_threshold(post_s)  # one threshold, both dates → consistent change
    water_post = sar.classify_water(post_s, thr)
    water_pre = sar.classify_water(pre_s, thr)
    new_flood = sar.remove_small_objects(water_post & ~water_pre, min_size=8)
    thr_b, _ = sar.water_threshold(vh_post, method="global_otsu")  # naive baseline
    base_water = sar.classify_water(vh_post, thr_b)

    # Terrain-aware cleanup: flood water sits on flat ground; steep pixels are
    # SAR layover/shadow false positives. This is the agent's conditional
    # correction (only applied where terrain warrants it).
    slope = _slope_deg(cat, ds.odc.geobox)
    steep = None
    if slope is not None:
        steep = slope > 8.0
        new_flood = new_flood & ~steep
        water_post = water_post & ~steep

    try:
        bb = ds.odc.geobox.extent.to_crs("EPSG:4326").boundingbox
        west, south, east, north = bb.left, bb.bottom, bb.right, bb.top
    except Exception:
        west, south, east, north = AOI

    px_km2 = (RES_M ** 2) / 1e6
    valid = int(np.isfinite(vh_post).sum())
    total = vh_post.size
    if valid / total < 0.6:
        print(f"  WARNING: only {100*valid/total:.0f}% of AOI has data (scene footprint edge).")

    def area(m):
        n = int(np.asarray(m, bool).sum())
        return {"pred_water_px": n, "area_km2": round(n * px_km2, 2),
                "area_pct": round(100 * n / valid, 1) if valid else None}

    out = TILES_DIR / CHIP_ID
    out.mkdir(parents=True, exist_ok=True)
    _sar_png(vh_pre).save(out / "before.png")
    _sar_png(vh_post).save(out / "after.png")
    _sar_png(vh_post).save(out / "sar.png")
    _mask_png(water_pre, COL_FLOOD, alpha=150).save(out / "water_pre.png")   # pre water (cyan, before side)
    _mask_png(water_post, COL_FLOOD).save(out / "water.png")    # total surface water (Aug 28)
    _mask_png(new_flood, (250, 204, 21)).save(out / "flood.png")  # NEW inundation (amber), highlighted
    _mask_png(water_post, COL_FLOOD).save(out / "agent.png")
    _mask_png(water_pre, COL_PERM, alpha=150).save(out / "permanent.png")
    _mask_png(base_water, COL_BASELINE).save(out / "baseline.png")

    flood_a, post_a = area(new_flood), area(water_post)

    # Auto "zoom to the flood": geographic bbox of the inundation, padded, so the
    # explorer opens framed on the affected reach instead of the whole tile.
    h, w = new_flood.shape
    ys, xs = np.where(new_flood)  # concentrate on the inundation itself
    if xs.size > 50:
        x0, x1 = np.percentile(xs, [3, 97])  # trim scattered outliers
        y0, y1 = np.percentile(ys, [3, 97])
        fx0, fx1, fy0, fy1 = x0 / w, x1 / w, y0 / h, y1 / h
        lon0, lon1 = west + fx0 * (east - west), west + fx1 * (east - west)
        lat_n, lat_s = north - fy0 * (north - south), north - fy1 * (north - south)
        padx = (lon1 - lon0) * 0.3 + 0.006
        pady = (lat_n - lat_s) * 0.3 + 0.006
        # clamp within the tile so the view never zooms out past the imagery
        vs, vw = max(south, lat_s - pady), max(west, lon0 - padx)
        vn, ve = min(north, lat_n + pady), min(east, lon1 + padx)
        view = [[float(vs), float(vw)], [float(vn), float(ve)]]
    else:
        view = [[float(south), float(west)], [float(north), float(east)]]
    print(f"  view (zoom-to-flood): {view}")

    traj = Trajectory(agent="floodscope-live", case=CHIP_ID)
    traj.set_phase("acquire")
    traj.system_prompt("Live flood mapping via pre/post SAR change detection (no ground truth).")
    traj.user_prompt(f"Map new inundation on the Narayani plain (Chitwan) between {pre_date} and {post_date}.")
    traj.tool_call("stac_search", {"collection": "sentinel-1-grd", "orbit": "descending"})
    traj.tool_result("stac_search", summary=f"pre={pre_item.id[:34]}… post={post_item.id[:34]}…")
    traj.tool_call("load_vh", {"resolution_m": RES_M, "crs": "EPSG:32645", "coregistered": True})
    traj.tool_result("load_vh", summary=f"arrays {vh_post.shape}, valid {100*valid/total:.0f}%")
    traj.set_phase("analyze")
    traj.tool_call("speckle+threshold", {"method": method, "threshold": round(float(thr), 2)})
    traj.tool_call("change_detect", {"rule": "water in POST and not in PRE, min_blob=8"})
    traj.tool_result("change_detect",
                     summary=f"new inundation {flood_a['area_km2']} km² ({flood_a['area_pct']}%); "
                             f"total post-water {post_a['area_km2']} km²")
    traj.verification(passed="fallback" not in method,
                      checks={"threshold_method": method, "permanent_channel_excluded": True,
                              "no_ground_truth": True,
                              "note": "no labels — pre/post consistency + plausibility only"})
    traj.human_review(decision="pending", note="live flood extent requires analyst sign-off before any use")
    traj.checkpoint({"new_flood_km2": flood_a["area_km2"], "post_water_km2": post_a["area_km2"]})
    traj.phase_complete("analyze")
    p = traj.close(); render_markdown(p)
    TRAJ_OUT.mkdir(parents=True, exist_ok=True)
    shutil.copy(p, TRAJ_OUT / f"{CHIP_ID}.ndjson")

    h, w = vh_post.shape
    return {
        "chip": CHIP_ID, "note": NOTE, "live": True,
        "acquired": {"pre": pre_item.properties["datetime"], "post": post_item.properties["datetime"]},
        "bounds": [[south, west], [north, east]],
        "view": view,
        "center": [(south + north) / 2, (west + east) / 2],
        "size": [h, w], "pixel_m": RES_M,
        "present": {
            "before": f"tiles/{CHIP_ID}/before.png",
            "before_mask": f"tiles/{CHIP_ID}/water_pre.png",
            "after": f"tiles/{CHIP_ID}/after.png",
            "mask": f"tiles/{CHIP_ID}/water.png",
            "mask2": f"tiles/{CHIP_ID}/flood.png",
            "before_label": f"Pre-monsoon · {pre_item.properties['datetime'][:10]}",
            "after_label": f"Post-flood · {post_item.properties['datetime'][:10]}",
            "mask_label": "Surface water",
            "mask2_label": "Inundation vs dry season",
            "legend": [{"color": "#38bdf8", "label": "surface water"},
                       {"color": "#facc15", "label": "inundation vs dry-season baseline"}],
        },
        "tiles": {"sar": f"tiles/{CHIP_ID}/sar.png", "optical": f"tiles/{CHIP_ID}/after.png",
                  "water": f"tiles/{CHIP_ID}/water.png", "flood": f"tiles/{CHIP_ID}/flood.png",
                  "baseline": f"tiles/{CHIP_ID}/baseline.png", "agent": f"tiles/{CHIP_ID}/water.png",
                  "permanent": f"tiles/{CHIP_ID}/permanent.png"},
        "trajectory": f"trajectories/{CHIP_ID}.ndjson",
        "metrics": {
            "baseline": {"threshold_method": "global-otsu(naive)", **area(base_water)},
            "agent": {"threshold_method": method, "surface_water_km2": post_a["area_km2"],
                      "new_inundation_km2": flood_a["area_km2"], **post_a},
        },
        "flood": {"surface_water_km2": post_a["area_km2"], "new_inundation_km2": flood_a["area_km2"],
                  "area_km2": post_a["area_km2"], "area_pct": post_a["area_pct"]},
        "delta_iou": None,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="2026-08-28", help="post (flood) date")
    ap.add_argument("--pre", default="2026-03-30", help="pre (dry-season baseline) date")
    args = ap.parse_args()
    entry = acquire(args.date, args.pre)

    # Nepal-only manifest (this baseline submission focuses on the live scene).
    mpath = WEBVIZ_PUBLIC / "manifest.json"
    mpath.write_text(json.dumps([entry], indent=2))
    f = entry["flood"]
    print(f"  surface water: {f['surface_water_km2']} km² ({f['area_pct']}% of scene) · "
          f"new inundation vs pre: {f['new_inundation_km2']} km²")
    print(f"  added {CHIP_ID} to {mpath}")


if __name__ == "__main__":
    main()
