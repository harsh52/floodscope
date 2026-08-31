# Trajectory — floodscope-pipeline — Pakistan_849790

- **workflow_id:** `floodscope-pipeline:Pakistan_849790`
- **events:** 12

---

### `analyze` · System prompt
```
Deterministic flood-mapping pipeline. Classify open water in a Sentinel-1 VV/VH scene using verification-gated thresholding and terrain-aware cleanup.
```

### `analyze` · User prompt
```
Map flood water for chip Pakistan_849790 (2022 indus-type flood).
```

**→ tool call** `speckle({"detail": "speckle(median5)"})`

**← tool result** ✓ `speckle`: speckle(median5)

**→ tool call** `threshold({"detail": "threshold(gated-otsu, -19.30 dB)"})`

**← tool result** ✓ `threshold`: threshold(gated-otsu, -19.30 dB)

**→ tool call** `cleanup({"detail": "cleanup(min=10, -640 px)"})`

**← tool result** ✓ `cleanup`: cleanup(min=10, -640 px)

**Verification ✅ passed**
```json
{
  "threshold_method": "gated-otsu",
  "bimodal_histogram": true,
  "note": "Otsu trusted only on genuinely bimodal scenes; else fixed dB fallback."
}
```

**🧑‍⚖️ human review: pending** — flood map awaiting analyst sign-off before publication

**Checkpoint**
```json
{
  "metrics": {
    "iou": 0.4141,
    "precision": 0.849,
    "recall": 0.447,
    "f1": 0.5857,
    "tp": 76848,
    "fp": 13671,
    "fn": 95060,
    "tn": 71660,
    "pred_water_px": 90519,
    "true_water_px": 171908,
    "area_km2": 9.05,
    "area_pct": 35.2,
    "threshold_method": "gated-otsu",
    "threshold_db": -19.3
  }
}
```

_— analyze complete —_
