"""Live Sentinel-1 acquisition + pre/post flood change-mapping for an arbitrary AOI.

Generalises the logic in scripts/acquire_nepal.py so the LLM orchestrator can pull
imagery for any bounding box and dates. Data: Microsoft Planetary Computer
(`sentinel-1-grd`, anonymous). No science lives in the agent — it lives here.
"""
from __future__ import annotations

import numpy as np
import odc.stac
import planetary_computer
import pystac_client
from PIL import Image

from floodscope.geo import sar

STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
COL_WATER = (56, 189, 248)      # cyan
COL_NEW = (250, 204, 21)        # amber — new inundation
COL_BASE = (239, 68, 68)        # red — naive
MASK_ALPHA = 200


def _client():
    return pystac_client.Client.open(STAC, modifier=planetary_computer.sign_inplace)


def _sar_png(vh_db: np.ndarray) -> Image.Image:
    arr = np.asarray(vh_db, "float32")
    finite = np.isfinite(arr)
    lo, hi = np.nanpercentile(arr[finite], [2, 98]) if finite.any() else (0.0, 1.0)
    g = np.where(finite, np.clip((arr - lo) / (hi - lo + 1e-6), 0, 1) * 255, 0).astype("uint8")
    return Image.fromarray(np.dstack([g, g, g, np.where(finite, 255, 0).astype("uint8")]), "RGBA")


def _mask_png(mask, color, alpha=MASK_ALPHA) -> Image.Image:
    m = np.asarray(mask, bool)
    rgba = np.zeros((*m.shape, 4), "uint8")
    rgba[m, 0], rgba[m, 1], rgba[m, 2], rgba[m, 3] = *color, alpha
    return Image.fromarray(rgba, "RGBA")


class LiveScene:
    """Holds the acquired arrays and the flood-mapping state for one AOI."""

    def __init__(self, bbox, res_m: int = 40, orbit_state: str = "ascending", rel_orbit: int | None = 85):
        self.bbox = list(bbox)  # [W, S, E, N]
        self.res = res_m
        self.orbit_state = orbit_state
        self.rel_orbit = rel_orbit
        self.cat = _client()
        self.post_item = self.pre_item = self.ds = None
        self.vh_post = self.vh_pre = None
        self.masks: dict = {}
        self.area: dict = {}
        self.method = ""
        self.bounds = self.view = None

    # -- acquire -------------------------------------------------------------
    def _find(self, on_or_before: str):
        q = {"sat:orbit_state": {"eq": self.orbit_state}}
        if self.rel_orbit is not None:
            q["sat:relative_orbit"] = {"eq": self.rel_orbit}
        s = self.cat.search(collections=["sentinel-1-grd"], bbox=self.bbox,
                            datetime=f"2020-01-01/{on_or_before}T23:59:59Z", query=q,
                            sortby=[{"field": "properties.datetime", "direction": "desc"}], limit=1)
        items = list(s.items())
        return items[0] if items else None

    def _load(self, item, like=None):
        kw = dict(bands=["vh"], like=like) if like is not None else dict(
            bands=["vh"], bbox=self.bbox, crs="EPSG:32645", resolution=self.res)
        ds = odc.stac.load([item], **kw).isel(time=0)
        dn = ds["vh"].values.astype("float32")
        with np.errstate(divide="ignore"):
            vh = sar.to_db(dn ** 2)
        vh[~np.isfinite(vh)] = np.nan
        return vh, ds

    def acquire(self, post_date: str, pre_date: str) -> dict:
        self.post_item = self._find(post_date)
        self.pre_item = self._find(pre_date)
        if not self.post_item or not self.pre_item:
            return {"ok": False, "reason": f"no {self.orbit_state} rel-orbit {self.rel_orbit} "
                    f"scene pair for that AOI/dates — try a different orbit or dates"}
        self.vh_post, self.ds = self._load(self.post_item)
        self.vh_pre, _ = self._load(self.pre_item, like=self.ds.odc.geobox)
        h = min(self.vh_post.shape[0], self.vh_pre.shape[0])
        w = min(self.vh_post.shape[1], self.vh_pre.shape[1])
        self.vh_post, self.vh_pre = self.vh_post[:h, :w], self.vh_pre[:h, :w]
        valid = int(np.isfinite(self.vh_post).sum())
        coverage = round(valid / self.vh_post.size, 2)
        try:
            bb = self.ds.odc.geobox.extent.to_crs("EPSG:4326").boundingbox
            self.bounds = [[bb.bottom, bb.left], [bb.top, bb.right]]
        except Exception:
            w_, s_, e_, n_ = self.bbox
            self.bounds = [[s_, w_], [n_, e_]]
        return {"ok": True, "post": self.post_item.properties["datetime"][:10],
                "pre": self.pre_item.properties["datetime"][:10],
                "coverage": coverage, "size": [h, w],
                "warning": "low scene-footprint coverage (<0.6) — result may be partial"
                if coverage < 0.6 else None}

    # -- inspect -------------------------------------------------------------
    def stats(self) -> dict:
        v = self.vh_post[np.isfinite(self.vh_post)]
        p50 = float(np.median(v))
        # scale-free dark-tail proxy: fraction >4 dB darker than the median
        return {"histogram_bimodal": bool(sar.is_bimodal(v)),
                "water_fraction_proxy": round(float(np.mean(v < p50 - 4.0)), 3),
                "vh_p50_db": round(p50, 1)}

    # -- analyse -------------------------------------------------------------
    def _slope_deg(self):
        try:
            items = list(self.cat.search(collections=["cop-dem-glo-30"], bbox=self.bbox).items())
            if not items:
                return None
            dem = odc.stac.load(items, bands=["data"], like=self.ds.odc.geobox, resampling="bilinear")
            z = (dem["data"].isel(time=0).values if "time" in dem.dims else dem["data"].values).astype("float32")
            gy, gx = np.gradient(z[:self.vh_post.shape[0], :self.vh_post.shape[1]], self.res, self.res)
            return np.degrees(np.arctan(np.hypot(gx, gy)))
        except Exception:
            return None

    def map_flood(self, threshold_method: str = "gated_otsu", mask_steep_slopes: bool = True) -> dict:
        post_s, pre_s = sar.speckle_filter(self.vh_post), sar.speckle_filter(self.vh_pre)
        v = post_s[np.isfinite(post_s)]
        if threshold_method == "gated_otsu" and sar.is_bimodal(v):
            thr, method = sar.otsu_threshold(post_s), "gated-otsu"
        elif threshold_method in ("fixed", "gated_otsu"):
            thr, method = float(np.nanpercentile(v, 12)), "p12-fallback"
        else:
            thr, method = sar.otsu_threshold(post_s), "global-otsu(naive)"
        water_post = sar.classify_water(post_s, thr)
        water_pre = sar.classify_water(pre_s, thr)
        new_flood = sar.remove_small_objects(water_post & ~water_pre, min_size=8)
        base = sar.classify_water(self.vh_post, sar.water_threshold(self.vh_post, method="global_otsu")[0])
        if mask_steep_slopes:
            slope = self._slope_deg()
            if slope is not None:
                steep = slope > 8.0
                new_flood, water_post = new_flood & ~steep, water_post & ~steep
                method += "+slope_mask"
        self.masks = {"water": water_post, "pre": water_pre, "flood": new_flood, "base": base}
        self.method = method
        px_km2 = (self.res ** 2) / 1e6
        valid = int(np.isfinite(self.vh_post).sum())
        self.area = {"surface_water_km2": round(int(water_post.sum()) * px_km2, 2),
                     "new_inundation_km2": round(int(new_flood.sum()) * px_km2, 2),
                     "area_pct": round(100 * int(water_post.sum()) / valid, 1) if valid else None}
        # zoom-to-flood view
        h, w = new_flood.shape
        ys, xs = np.where(new_flood)
        if xs.size > 50:
            x0, x1 = np.percentile(xs, [3, 97]); y0, y1 = np.percentile(ys, [3, 97])
            (s_, w_), (n_, e_) = self.bounds
            lon0, lon1 = w_ + x0 / w * (e_ - w_), w_ + x1 / w * (e_ - w_)
            latn, lats = n_ - y0 / h * (n_ - s_), n_ - y1 / h * (n_ - s_)
            px, py = (lon1 - lon0) * .3 + .006, (latn - lats) * .3 + .006
            self.view = [[max(s_, lats - py), max(w_, lon0 - px)], [min(n_, latn + py), min(e_, lon1 + px)]]
        else:
            self.view = self.bounds
        return {"threshold_method": method, **self.area, "water_fraction": round(int(water_post.sum()) / valid, 3)}

    def verify(self) -> dict:
        frac = int(self.masks["water"].sum()) / max(1, int(np.isfinite(self.vh_post).sum()))
        reasons, passed = [], True
        if frac > 0.6:
            passed = False; reasons.append(f"surface-water fraction {frac:.2f} implausibly high")
        if "fallback" in self.method and self.area["new_inundation_km2"] > 0.5 * self.area["surface_water_km2"]:
            reasons.append("note: unimodal scene; new-inundation estimate is coarse")
        if passed:
            reasons.append(f"water fraction {frac:.2f} plausible; method '{self.method}'")
        return {"passed": passed, "reasons": reasons}

    # -- render + publish ----------------------------------------------------
    def render(self, out_dir) -> dict:
        out_dir.mkdir(parents=True, exist_ok=True)
        _sar_png(self.vh_pre).save(out_dir / "before.png")
        _sar_png(self.vh_post).save(out_dir / "after.png")
        _sar_png(self.vh_post).save(out_dir / "sar.png")
        _mask_png(self.masks["water"], COL_WATER).save(out_dir / "water.png")
        _mask_png(self.masks["pre"], COL_WATER, alpha=150).save(out_dir / "water_pre.png")
        _mask_png(self.masks["flood"], COL_NEW).save(out_dir / "flood.png")
        _mask_png(self.masks["water"], COL_WATER).save(out_dir / "agent.png")
        _mask_png(self.masks["base"], COL_BASE).save(out_dir / "baseline.png")
        return {k: f"{k}.png" for k in ("before", "after", "sar", "water", "flood", "baseline")}
