# Trajectory — floodscope-pipeline — Somalia_699062

- **workflow_id:** `floodscope-pipeline:Somalia_699062`
- **events:** 12

---

### `analyze` · System prompt
```
Deterministic flood-mapping pipeline. Classify open water in a Sentinel-1 VV/VH scene using verification-gated thresholding and terrain-aware cleanup.
```

### `analyze` · User prompt
```
Map flood water for chip Somalia_699062 (arid flash flood).
```

**→ tool call** `speckle({"detail": "speckle(median5)"})`

**← tool result** ✓ `speckle`: speckle(median5)

**→ tool call** `threshold({"detail": "threshold(fixed(fallback:not-bimodal), -22.00 dB)"})`

**← tool result** ✓ `threshold`: threshold(fixed(fallback:not-bimodal), -22.00 dB)

**→ tool call** `cleanup({"detail": "cleanup(min=10, -201 px)"})`

**← tool result** ✓ `cleanup`: cleanup(min=10, -201 px)

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
    "iou": 0.1284,
    "precision": 0.1761,
    "recall": 0.3213,
    "f1": 0.2275,
    "tp": 1057,
    "fp": 4945,
    "fn": 2233,
    "tn": 194974,
    "pred_water_px": 6002,
    "true_water_px": 3290,
    "area_km2": 0.6,
    "area_pct": 3.0,
    "threshold_method": "fixed(fallback:not-bimodal)",
    "threshold_db": -22.0
  }
}
```

_— analyze complete —_
