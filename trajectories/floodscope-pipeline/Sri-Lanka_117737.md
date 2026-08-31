# Trajectory — floodscope-pipeline — Sri-Lanka_117737

- **workflow_id:** `floodscope-pipeline:Sri-Lanka_117737`
- **events:** 12

---

### `analyze` · System prompt
```
Deterministic flood-mapping pipeline. Classify open water in a Sentinel-1 VV/VH scene using verification-gated thresholding and terrain-aware cleanup.
```

### `analyze` · User prompt
```
Map flood water for chip Sri-Lanka_117737 (tropical island flood).
```

**→ tool call** `speckle({"detail": "speckle(median5)"})`

**← tool result** ✓ `speckle`: speckle(median5)

**→ tool call** `threshold({"detail": "threshold(gated-otsu, -17.84 dB)"})`

**← tool result** ✓ `threshold`: threshold(gated-otsu, -17.84 dB)

**→ tool call** `cleanup({"detail": "cleanup(min=10, -700 px)"})`

**← tool result** ✓ `cleanup`: cleanup(min=10, -700 px)

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
    "iou": 0.0947,
    "precision": 0.096,
    "recall": 0.8756,
    "f1": 0.1731,
    "tp": 5894,
    "fp": 55478,
    "fn": 837,
    "tn": 199935,
    "pred_water_px": 61372,
    "true_water_px": 6731,
    "area_km2": 6.14,
    "area_pct": 23.4,
    "threshold_method": "gated-otsu",
    "threshold_db": -17.84
  }
}
```

_— analyze complete —_
