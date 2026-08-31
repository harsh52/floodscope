# Trajectory — floodscope-pipeline — Paraguay_913449

- **workflow_id:** `floodscope-pipeline:Paraguay_913449`
- **events:** 12

---

### `analyze` · System prompt
```
Deterministic flood-mapping pipeline. Classify open water in a Sentinel-1 VV/VH scene using verification-gated thresholding and terrain-aware cleanup.
```

### `analyze` · User prompt
```
Map flood water for chip Paraguay_913449 (parana wetland).
```

**→ tool call** `speckle({"detail": "speckle(median5)"})`

**← tool result** ✓ `speckle`: speckle(median5)

**→ tool call** `threshold({"detail": "threshold(gated-otsu, -16.97 dB)"})`

**← tool result** ✓ `threshold`: threshold(gated-otsu, -16.97 dB)

**→ tool call** `cleanup({"detail": "cleanup(min=10, -1320 px)"})`

**← tool result** ✓ `cleanup`: cleanup(min=10, -1320 px)

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
    "iou": 0.0529,
    "precision": 0.0534,
    "recall": 0.8463,
    "f1": 0.1004,
    "tp": 4669,
    "fp": 82806,
    "fn": 848,
    "tn": 173821,
    "pred_water_px": 87475,
    "true_water_px": 5517,
    "area_km2": 8.75,
    "area_pct": 33.4,
    "threshold_method": "gated-otsu",
    "threshold_db": -16.97
  }
}
```

_— analyze complete —_
