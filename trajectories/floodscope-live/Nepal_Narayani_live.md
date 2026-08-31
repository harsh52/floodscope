# Trajectory — floodscope-live — Nepal_Narayani_live

- **workflow_id:** `floodscope-live:Nepal_Narayani_live`
- **events:** 13

---

### `acquire` · System prompt
```
Live flood mapping via pre/post SAR change detection (no ground truth).
```

### `acquire` · User prompt
```
Map new inundation on the Narayani plain (Chitwan) between 2026-03-30 and 2026-08-28.
```

**→ tool call** `stac_search({"collection": "sentinel-1-grd", "orbit": "descending"})`

**← tool result** ✓ `stac_search`: pre=S1A_IW_GRDH_1SDV_20260330T122218_2… post=S1D_IW_GRDH_1SDV_20260828T122141_2…

**→ tool call** `load_vh({"resolution_m": 40, "crs": "EPSG:32645", "coregistered": true})`

**← tool result** ✓ `load_vh`: arrays (569, 654), valid 99%

**→ tool call** `speckle+threshold({"method": "p12-fallback", "threshold": 38.79})`

**→ tool call** `change_detect({"rule": "water in POST and not in PRE, min_blob=8"})`

**← tool result** ✓ `change_detect`: new inundation 15.26 km² (2.6%); total post-water 21.62 km²

**Verification ❌ failed**
```json
{
  "threshold_method": "p12-fallback",
  "permanent_channel_excluded": true,
  "no_ground_truth": true,
  "note": "no labels — pre/post consistency + plausibility only"
}
```

**🧑‍⚖️ human review: pending** — live flood extent requires analyst sign-off before any use

**Checkpoint**
```json
{
  "new_flood_km2": 15.26,
  "post_water_km2": 21.62
}
```

_— analyze complete —_
