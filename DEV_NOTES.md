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

## Open decisions
- Fallback hero event: TBD (pick one Sen1Floods11 event with strong visuals for a guaranteed live-style run).
- Eval chip subset: pick 10-12 from the 90 test chips spanning biomes + include 1 hard case (urban/low-water-fraction).
