# Dev Notes — FloodScope

Working log of decisions, findings, and risks. (Not the submission README.)

## Environment
- Python **3.11.14** via `uv` venv (`.venv/`). Chosen over system 3.14/3.13 for geospatial wheel stability.
- Geospatial: rasterio 1.4.4 (GDAL 3.10.3), rioxarray, xarray, stackstac 0.5.1, odc-stac, geopandas, shapely, scikit-image, folium.
- Agent: anthropic 1.2.0, langgraph, langchain-core, pydantic 2.13.
- Exact versions pinned in `requirements.txt` (`uv pip freeze`).
- Reinstall: `uv venv --python 3.11 .venv && uv pip install -r requirements.txt`.

## Data paths (both verified anonymous / no-key)
- **Sen1Floods11** (scoring benchmark): public GCS bucket, accessed over **anonymous HTTPS** (gsutil needs auth; HTTPS does not).
  - Chips: `https://storage.googleapis.com/sen1floods11/v1.1/data/flood_events/HandLabeled/<KIND>/<Chip>_<KIND>.tif`
  - KINDs: `S1Hand` (VV band1, VH band2, float32 dB), `LabelHand` (-1 nodata / 0 land / 1 water), `JRCWaterHand` (permanent water), `S1OtsuLabelHand` (precomputed Otsu), `S2Hand` (13-band optical).
  - Splits: `.../v1.1/splits/flood_handlabeled/flood_{test,train,valid,bolivia}_data.csv`. **Test = 90 chips**, format `S1Hand.tif,LabelHand.tif` per row.
  - CRS EPSG:4326, 512x512, 10 m.
- **Planetary Computer STAC** (live demo): `sentinel-1-grd`, **anonymous** (`planetary_computer.sign_inplace`), assets `vv`/`vh`.

## Baseline sanity check
- Chip `Ghana_313799`: naive global-Otsu-on-VH IoU(water) = **0.112**. Weak (massive false positives). Confirms headroom for the agent.

## ⚠️ RISK: Nepal live-demo timing (tracked)
- Rasuwa flood = **26 Aug 2026**. As of today (28 Aug), PC ingestion frontier over Nepal = **24 Aug** (pre-flood only).
- Pre scenes available: 2026-08-19, 2026-08-24 (both descending, S1D).
- Next descending overpass ≈ **30 Aug** — should ingest mid-hackathon (ends 31 Aug 18:00 UTC). **Narrow window.**
- **Mitigation:** (1) build pipeline fully parameterized by AOI/date; (2) poll for the post-26-Aug scene; (3) prepare a GUARANTEED fallback hero demo on a past well-covered flood (e.g. a Sen1Floods11 event location, which also has ground truth) so the demo never depends on the race.

## LOCKED science result (Day 1) — deterministic pipeline, 12 diverse chips
Baseline = naive global Otsu on VH (what a one-shot LLM writes).
Agent = speckle + **bimodality-gated Otsu** (Otsu if histogram bimodal, else fixed -22 dB) + small-blob cleanup.

| metric | baseline | agent | Δ |
|---|---|---|---|
| mean IoU | 0.291 | 0.336 | +0.045 (+15% rel) |
| mean precision | 0.353 | 0.486 | +0.133 (+38% rel) |
| mean recall | 0.800 | 0.661 | -0.138 |
| agent wins | — | 11/12 chips | — |
| hard urban case USA_430764 | 0.160 | 0.466 | +0.307 |

**Key insight (the whole story):** the naive baseline's failure mode is *low-water scenes* — the histogram is unimodal (land only), so global Otsu splits the LAND and floods 60-90% of a dry scene as "water" (precision 0.05-0.12, recall high). The verification gate (is-it-bimodal?) catches this and switches to a conservative fixed threshold → precision nearly doubles. **"The naive method is confidently wrong on dry scenes; verification, not a bigger model, fixes it."** = hot take.

**Context-dependent corrections (agentic judgment):**
- Permanent-water removal HELPS the real product (isolate new inundation) but HURTS the all-water benchmark (labels include permanent water). Measure both; be explicit.
- Slope masking HELPS steep terrain (Nepal) but HURTS flat benchmark chips (DEM noise). Agent applies it *conditionally* on detected terrain.
- One chip regresses (Ghana_313799, -0.088): non-bimodal savanna where fixed threshold under-predicts. Honest tradeoff; 11/12 still improve.

## Open decisions
- Fallback hero event: TBD (pick one Sen1Floods11 event with strong visuals for a guaranteed live-style run).
- Eval chip subset: pick 10-12 from the 90 test chips spanning biomes + include 1 hard case (urban/low-water-fraction).
