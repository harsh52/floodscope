"""Physical-prior masks that separate *flood* water from artifacts.

Two corrections the naive baseline skips:
  1. Permanent water — rivers/lakes that are always wet are not *flood*. Remove
     them (JRC Global Surface Water) so we measure new inundation.
  2. Terrain shadow / layover — steep slopes produce SAR shadow that reads as
     dark = false 'water'. Mask slopes above a threshold using a DEM.
"""
from __future__ import annotations

import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling

from floodscope.config import MAX_SLOPE_DEG, PERMANENT_WATER_OCCURRENCE


def permanent_water_mask(jrc: np.ndarray, occurrence_pct: int = PERMANENT_WATER_OCCURRENCE) -> np.ndarray:
    """Boolean mask of permanently-wet pixels from a JRC occurrence layer.

    Sen1Floods11's JRCWaterHand encodes permanent-water presence; values >0 mark
    permanent water. We treat any positive occurrence at/above the threshold as
    permanent. (For the Sen1Floods11 layer the values are already 0/1-ish, so
    >0 is the effective rule; the threshold matters for raw JRC occurrence.)
    """
    j = np.asarray(jrc)
    if j.dtype.kind == "f":
        j = np.nan_to_num(j, nan=0.0)
    # Sen1Floods11 JRCWaterHand: >0 => permanent water. Raw JRC occurrence: %.
    if j.max() > 1:
        return j >= occurrence_pct
    return j > 0


def _read_profile(ref_tif) -> dict:
    with rasterio.open(ref_tif) as ds:
        return {"crs": ds.crs, "transform": ds.transform, "width": ds.width,
                "height": ds.height, "bounds": ds.bounds, "res": ds.res}


def fetch_dem_aligned(ref_tif, bounds) -> np.ndarray | None:
    """Fetch Copernicus DEM GLO-30 from Planetary Computer and reproject it onto
    the reference raster's exact grid. Returns None on any failure (caller then
    simply skips slope masking — graceful degradation)."""
    try:
        import planetary_computer as pc
        from pystac_client import Client
        import odc.stac

        prof = _read_profile(ref_tif)
        client = Client.open(
            "https://planetarycomputer.microsoft.com/api/stac/v1",
            modifier=pc.sign_inplace,
        )
        search = client.search(collections=["cop-dem-glo-30"], bbox=list(bounds))
        items = list(search.items())
        if not items:
            return None
        ds = odc.stac.load(items, bbox=list(bounds), bands=["data"], chunks={})
        dem_src = ds["data"].isel(time=0).values.astype("float32")
        src_transform = ds.odc.transform
        src_crs = ds.odc.crs

        dst = np.full((prof["height"], prof["width"]), np.nan, dtype="float32")
        reproject(
            source=dem_src,
            destination=dst,
            src_transform=src_transform,
            src_crs=str(src_crs),
            dst_transform=prof["transform"],
            dst_crs=prof["crs"],
            resampling=Resampling.bilinear,
        )
        return dst
    except Exception as e:  # pragma: no cover - network/optional path
        print(f"    [masks] DEM fetch failed ({type(e).__name__}: {e}); skipping slope mask")
        return None


def slope_degrees(dem: np.ndarray, ref_tif) -> np.ndarray:
    """Compute slope (degrees) from a DEM aligned to the reference grid.

    Approximates ground pixel spacing from the raster resolution (converting
    degrees->metres when the CRS is geographic).
    """
    prof = _read_profile(ref_tif)
    xres, yres = abs(prof["res"][0]), abs(prof["res"][1])
    if prof["crs"] and prof["crs"].is_geographic:
        # rough metres-per-degree at the chip's latitude
        lat = (prof["bounds"].top + prof["bounds"].bottom) / 2.0
        m_per_deg_lat = 111_320.0
        m_per_deg_lon = 111_320.0 * np.cos(np.radians(lat))
        xres *= m_per_deg_lon
        yres *= m_per_deg_lat
    gy, gx = np.gradient(np.nan_to_num(dem, nan=np.nanmedian(dem)), yres, xres)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    return slope


def slope_mask(dem: np.ndarray, ref_tif, max_slope_deg: float = MAX_SLOPE_DEG) -> np.ndarray:
    """Boolean mask of pixels too steep to be standing water (to be excluded)."""
    slope = slope_degrees(dem, ref_tif)
    return slope > max_slope_deg
