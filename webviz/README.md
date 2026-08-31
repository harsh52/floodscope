# FloodScope — Results Explorer (webviz)

Interactive map to compare the **baseline** vs the **agent** flood maps over real
geography, on Sen1Floods11 ground truth, with agent-trajectory playback.

## What it shows
Two synced maps with a **draggable divider**, over an OpenStreetMap basemap, in three modes:
- **Before / After** (default) — left = satellite imagery, right = imagery + the agent's flood
  prediction. For the live Nepal scene it's true pre-flood vs post-flood imagery.
- **Baseline / Agent** — naive global-Otsu (red) vs the verification-gated agent (blue).
- **vs Ground truth** — agent (blue) vs Sen1Floods11 labels (green) — correctness check.

Plus a **flood-area card** (km² and % of scene affected), a **Metrics panel** (IoU / precision /
recall, or area for the live scene), and a **Trajectory tab** that steps through the agent's events
(prompt → tool calls → verification → human review). Live scenes are pinned first with a `LIVE` badge.

## Run (clean environment)
```bash
# 1) generate the assets the app reads (from the repo root, in the Python venv)
PYTHONPATH=. .venv/bin/python scripts/export_viz.py      # Sen1Floods11 chips (optical + masks + metrics)
PYTHONPATH=. .venv/bin/python scripts/acquire_nepal.py   # LIVE Nepal scene (Planetary Computer, no key)

# 2) run the app
cd webviz
npm ci          # or: npm install
npm run dev      # http://localhost:5173
# production build:
npm run build && npm run preview
```

Requires Node 18+ and internet (OSM basemap tiles; Planetary Computer for the live scene).
`export_viz.py` reads the cached Sen1Floods11 chips under `data/` and fetches Sentinel-2 optical;
`acquire_nepal.py` pulls fresh Sentinel-1 GRD over the Narayani (Chitwan) and preserves the entry
across `export_viz.py` re-runs.
