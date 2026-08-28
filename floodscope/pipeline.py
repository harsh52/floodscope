"""Deterministic flood-mapping pipeline.

This is the *science* the agent orchestrates. Each correction is a toggle so we
can measure its individual IoU contribution (the improvement changelog). The
naive baseline = all corrections off; the full solution = all on.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from floodscope.geo import sar, masks


@dataclass
class FloodConfig:
    band: str = "vh"                 # VH preferred for open water
    speckle: bool = False            # median speckle filter
    threshold_method: str = "gated_otsu"  # 'global_otsu' | 'gated_otsu' | 'tile' | 'fixed'
    remove_permanent_water: bool = False
    mask_steep_slopes: bool = False
    cleanup_min_size: int = 0        # drop blobs smaller than this (0 = off)

    @classmethod
    def baseline(cls) -> "FloodConfig":
        # Naive: plain global Otsu on VH, no speckle, no gating, no corrections.
        return cls(threshold_method="global_otsu")

    @classmethod
    def full_benchmark(cls) -> "FloodConfig":
        """Best config for the Sen1Floods11 *all-water* IoU benchmark.

        NOTE: permanent-water removal is intentionally OFF here — the benchmark
        labels ALL surface water, so removing permanent water deletes true
        positives and lowers IoU. It belongs to the product path below.

        Slope masking is also OFF by default here: the benchmark chips are
        mostly flat, where DEM-noise slope masking removes real water. The agent
        turns it on *conditionally* when it detects steep terrain (see Nepal).
        """
        return cls(speckle=True, threshold_method="gated_otsu",
                   mask_steep_slopes=False, cleanup_min_size=10)

    @classmethod
    def full_product(cls) -> "FloodConfig":
        """Best config for a real flood *product* (isolate NEW inundation).

        Removes permanent water so the analyst sees flood water, not rivers that
        are always wet. Used on the live Nepal demo (with pre/post change
        detection), not on the all-water benchmark.
        """
        return cls(speckle=True, threshold_method="tile",
                   remove_permanent_water=True, mask_steep_slopes=True,
                   cleanup_min_size=10)


@dataclass
class FloodResult:
    water: np.ndarray                       # boolean flood-water mask
    threshold_db: float
    threshold_method: str
    provenance: dict = field(default_factory=dict)


def map_flood(
    vv: np.ndarray,
    vh: np.ndarray,
    cfg: FloodConfig,
    *,
    jrc: np.ndarray | None = None,
    ref_tif=None,
    bounds=None,
) -> FloodResult:
    """Run the flood-water classification for a given config.

    jrc/ref_tif/bounds are optional context enabling the permanent-water and
    slope corrections. If absent, those corrections are silently skipped.
    """
    db = vh if cfg.band == "vh" else vv
    prov: dict = {"band": cfg.band, "steps": []}

    if cfg.speckle:
        db = sar.speckle_filter(db, size=5)
        prov["steps"].append("speckle(median5)")

    thr, method = sar.water_threshold(db, method=cfg.threshold_method)
    water = sar.classify_water(db, thr)
    prov["steps"].append(f"threshold({method}, {thr:.2f} dB)")

    if cfg.remove_permanent_water and jrc is not None:
        perm = masks.permanent_water_mask(jrc)
        before = int(water.sum())
        water = water & ~perm
        prov["steps"].append(f"remove_permanent_water(-{before - int(water.sum())} px)")

    if cfg.mask_steep_slopes and ref_tif is not None and bounds is not None:
        dem = masks.fetch_dem_aligned(ref_tif, bounds)
        if dem is not None:
            steep = masks.slope_mask(dem, ref_tif)
            before = int(water.sum())
            water = water & ~steep
            prov["steps"].append(f"mask_steep_slopes(-{before - int(water.sum())} px)")
        else:
            prov["steps"].append("mask_steep_slopes(skipped: no DEM)")

    if cfg.cleanup_min_size:
        before = int(water.sum())
        water = sar.remove_small_objects(water, min_size=cfg.cleanup_min_size)
        prov["steps"].append(f"cleanup(min={cfg.cleanup_min_size}, -{before - int(water.sum())} px)")

    return FloodResult(water=water, threshold_db=thr, threshold_method=method, provenance=prov)
