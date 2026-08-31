# Trajectory — floodscope-pipeline — Nigeria_417184

- **workflow_id:** `floodscope-pipeline:Nigeria_417184`
- **events:** 12

---

### `analyze` · System prompt
```
Deterministic flood-mapping pipeline. Classify open water in a Sentinel-1 VV/VH scene using verification-gated thresholding and terrain-aware cleanup.
```

### `analyze` · User prompt
```
Map flood water for chip Nigeria_417184 (inland flood).
```

**→ tool call** `speckle({"detail": "speckle(median5)"})`

**← tool result** ✓ `speckle`: speckle(median5)

**→ tool call** `threshold({"detail": "threshold(fixed(fallback:not-bimodal), -22.00 dB)"})`

**← tool result** ✓ `threshold`: threshold(fixed(fallback:not-bimodal), -22.00 dB)

**→ tool call** `cleanup({"detail": "cleanup(min=10, -156 px)"})`

**← tool result** ✓ `cleanup`: cleanup(min=10, -156 px)

**Verification ❌ failed**
```json
{
  "threshold_method": "fixed(fallback:not-bimodal)",
  "bimodal_histogram": false,
  "note": "Otsu trusted only on genuinely bimodal scenes; else fixed dB fallback."
}
```

**🧑‍⚖️ human review: pending** — flood map awaiting analyst sign-off before publication

**Checkpoint**
```json
{
  "metrics": {
    "iou": 0.2303,
    "precision": 0.2404,
    "recall": 0.8461,
    "f1": 0.3744,
    "tp": 1171,
    "fp": 3700,
    "fn": 213,
    "tn": 53985,
    "pred_water_px": 4871,
    "true_water_px": 1384,
    "area_km2": 0.49,
    "area_pct": 8.2,
    "threshold_method": "fixed(fallback:not-bimodal)",
    "threshold_db": -22.0
  }
}
```

_— analyze complete —_
