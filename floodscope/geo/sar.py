"""SAR (Sentinel-1) flood-water detection primitives.

Water appears dark in SAR (specular reflection away from the sensor), so open
water = low backscatter. These are the deterministic building blocks the agent's
coder/verifier steps call; keeping them here makes the science testable without
the LLM in the loop.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage
from skimage.filters import threshold_otsu

from floodscope.config import FALLBACK_DB_THRESHOLD


def to_db(power: np.ndarray, eps: float = 1e-10) -> np.ndarray:
    """Convert linear backscatter (amplitude^2 / sigma0 power) to decibels."""
    return 10.0 * np.log10(np.maximum(power, eps))


def speckle_filter(db: np.ndarray, size: int = 5) -> np.ndarray:
    """Reduce SAR speckle. Median filter is simple, edge-preserving and robust.

    NaNs are handled by temporarily filling with the finite median.
    """
    arr = db.astype("float32")
    finite = np.isfinite(arr)
    if not finite.all():
        fill = np.nanmedian(arr[finite]) if finite.any() else 0.0
        arr = np.where(finite, arr, fill)
    smoothed = ndimage.median_filter(arr, size=size)
    return np.where(finite, smoothed, np.nan)


def is_bimodal(values: np.ndarray, bins: int = 128, min_valley_ratio: float = 0.75) -> bool:
    """Heuristic bimodality test for a backscatter histogram.

    Otsu only gives a meaningful water/land split when the histogram has two
    modes with a valley between them. If the scene is almost all land (tiny
    flood fraction) the histogram is unimodal and a global Otsu threshold is
    unreliable — the verifier uses this to fall back to a fixed dB threshold.
    """
    v = values[np.isfinite(values)]
    if v.size < 100:
        return False
    hist, edges = np.histogram(v, bins=bins)
    hist = ndimage.gaussian_filter1d(hist.astype("float32"), sigma=2)
    # find peaks
    peaks = [i for i in range(1, len(hist) - 1) if hist[i] > hist[i - 1] and hist[i] >= hist[i + 1]]
    peaks = sorted(peaks, key=lambda i: hist[i], reverse=True)
    if len(peaks) < 2:
        return False
    p1, p2 = sorted(peaks[:2])
    valley = hist[p1:p2 + 1].min()
    lower_peak = min(hist[p1], hist[p2])
    # a real valley sits clearly below the smaller of the two peaks
    return valley < min_valley_ratio * lower_peak


def otsu_threshold(db: np.ndarray) -> float:
    v = db[np.isfinite(db)]
    return float(threshold_otsu(v))


def tile_otsu_threshold(db: np.ndarray, tiles: int = 4) -> float:
    """Otsu computed on the tile with the strongest bimodality, then applied
    globally. Localises the water/land boundary when water covers only part of
    the scene (a common Sen1Floods11 failure mode for global Otsu)."""
    h, w = db.shape
    best_thr, best_sep = None, -np.inf
    th, tw = max(h // tiles, 1), max(w // tiles, 1)
    for i in range(0, h, th):
        for j in range(0, w, tw):
            block = db[i:i + th, j:j + tw]
            v = block[np.isfinite(block)]
            if v.size < 200:
                continue
            if not is_bimodal(v):
                continue
            try:
                thr = float(threshold_otsu(v))
            except Exception:
                continue
            below = v[v < thr]; above = v[v >= thr]
            if below.size == 0 or above.size == 0:
                continue
            sep = abs(above.mean() - below.mean())  # class separation
            if sep > best_sep:
                best_sep, best_thr = sep, thr
    if best_thr is None:
        # no bimodal tile found -> caller should use fallback
        return float("nan")
    return best_thr


def water_threshold(db: np.ndarray, method: str = "gated_otsu") -> tuple[float, str]:
    """Pick a dB threshold below which pixels are classified as water.

    Returns (threshold, method_used).

    Methods
    -------
    global_otsu : plain global Otsu, always. The NAIVE baseline — trusts Otsu
                  even when the histogram is unimodal (its key failure mode).
    gated_otsu  : Otsu only when the histogram is genuinely bimodal, else a
                  conservative fixed dB threshold. The verification correction.
    tile        : Otsu from the most-bimodal tile, else fixed fallback.
    fixed       : always the fixed dB threshold.
    """
    valid = db[np.isfinite(db)]
    if method == "fixed":
        return FALLBACK_DB_THRESHOLD, "fixed"
    if method == "global_otsu":
        return otsu_threshold(db), "global-otsu(naive)"
    if method == "tile":
        thr = tile_otsu_threshold(db)
        if np.isfinite(thr):
            return thr, "tile-otsu"
        return FALLBACK_DB_THRESHOLD, "fixed(fallback:not-bimodal)"
    # gated_otsu (default): guard Otsu on bimodality
    if is_bimodal(valid):
        return otsu_threshold(db), "gated-otsu"
    return FALLBACK_DB_THRESHOLD, "fixed(fallback:not-bimodal)"


def classify_water(db: np.ndarray, threshold: float) -> np.ndarray:
    """Boolean water mask: finite pixels below the dB threshold."""
    return np.isfinite(db) & (db < threshold)


def remove_small_objects(mask: np.ndarray, min_size: int = 10) -> np.ndarray:
    """Drop tiny speckle blobs from a boolean mask."""
    lbl, n = ndimage.label(mask)
    if n == 0:
        return mask
    sizes = ndimage.sum(np.ones_like(lbl), lbl, index=np.arange(1, n + 1))
    keep = np.isin(lbl, np.nonzero(sizes >= min_size)[0] + 1)
    return keep & mask
