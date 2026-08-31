# Reproduction guide — FloodScope

Written for someone starting from a **clean clone**. Every command is copy-pasteable from the repo root.

## 0. What you need

| | |
|---|---|
| **OS** | macOS or Linux (developed on macOS 14, Darwin 24.6) |
| **Python** | 3.11 (3.11.14 used). Chosen for geospatial wheel stability. |
| **Node** | 18+ (v22.22.3 used) — only for the web viewer |
| **[uv](https://github.com/astral-sh/uv)** | 0.9+ (0.9.15 used) — fast Python env/installer. Or use plain `python -m venv` + `pip`. |
| **Network** | required — data is fetched live from public sources |
| **API keys** | **none** for flood mapping or the benchmark (all data is public / anonymous) |
| **Disk** | ~500 MB (cached Sen1Floods11 chips + node_modules) |
| **Cost** | **$0** — no paid APIs are called |

**Data used (all public, no credentials):**
- **Sen1Floods11** hand-labelled chips — public Google Cloud bucket over anonymous HTTPS (auto-downloaded, cached in `data/sen1floods11/`).
- **Microsoft Planetary Computer** — Sentinel-1 GRD + Copernicus DEM, anonymous access (live acquisition).

### What reproduces *exactly* vs what may drift

| Result | Command | Determinism |
|---|---|---|
| **Baseline vs advanced table** (the headline measured improvement) | §2 `run_eval` | **Exact** — static Sen1Floods11 dataset, no key. |
| **Interactive dashboard** (Nepal before/after) | §4 `npm run dev` | **Exact** — reads committed assets (`webviz/public/`), no key, no script run needed. |
| Live Nepal *re-acquisition* | §3 `acquire_nepal.py` | **May drift** — pulls live Planetary Computer scenes; numbers move if newer scenes ingest, and needs those dates to be available. The dashboard above already ships the result. |
| LLM agent | §4b `flood_agent` | **Needs your own key** (Anthropic or OpenAI). Committed trajectories are the evidence; a live run reproduces the *behaviour*, not identical tokens. |

**Start with §2 and §4** — they are the main results and need no key or live data.

---

## 1. Set up the environment (~2 min)

```bash
uv venv --python 3.11 .venv
uv pip install -r requirements.txt
```

<details><summary>No uv? Use venv + pip</summary>

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
```
</details>

Exact pinned versions are in [`requirements.txt`](../requirements.txt) (key: rasterio 1.4.4 / GDAL 3.10,
odc-stac 0.5.3, planetary-computer 1.0.0, pystac-client 0.9.0, scikit-image 0.26, numpy 2.4).

---

## 2. Baseline vs. advanced comparison (the measured result) — ~1–2 min

```bash
PYTHONPATH=. .venv/bin/python -m floodscope.eval.run_eval
```

- **What it does:** runs the **baseline** (`FloodConfig.baseline()`, naive global Otsu) and the **advanced**
  workflow (`FloodConfig.full_benchmark()`) on the same 12 Sen1Floods11 chips, scoring IoU/precision/recall
  against ground-truth labels.
- **Data:** downloads ~12 chips on first run (cached afterwards; re-runs are seconds).
- **Expected output:** a per-chip table + a summary. You should see approximately:

  | metric | baseline | agent | Δ |
  |---|---|---|---|
  | mean_iou | 0.291 | 0.336 | +0.045 |
  | mean_precision | 0.353 | 0.486 | +0.133 |
  | mean_recall | 0.800 | 0.661 | −0.139 |

- **Evidence file:** writes [`reports/eval_results.csv`](../reports/eval_results.csv) (one row per chip per mode).

Per-correction ablation (which toggle bought which IoU): `PYTHONPATH=. .venv/bin/python scripts/ablation.py`.

---

## 3. Live flood map — the 26 Aug 2026 Nepal flood — ~30–60 s

```bash
PYTHONPATH=. .venv/bin/python scripts/acquire_nepal.py
```

- **What it does:** finds the pre-monsoon (2026-03-30) and post-flood (2026-08-28) Sentinel-1 passes over
  the Narayani plain (Chitwan) on the **same orbit**, runs speckle → gated-Otsu → cleanup → slope mask →
  pre/post change detection, and writes the viewer assets + a trajectory.
- **Expected output (printed):**
  ```
  post: S1D_..._20260828T122141_...   (2026-08-28T...)
  pre : S1A_..._20260330T122218_...   (2026-03-30T...)
  surface water: 21.62 km² (3.7% of scene) · new inundation vs pre: 15.26 km²
  added Nepal_Narayani_live to webviz/public/manifest.json
  ```
- **Artifacts written:** `webviz/public/manifest.json`, `webviz/public/tiles/Nepal_Narayani_live/*.png`,
  `webviz/public/trajectories/Nepal_Narayani_live.ndjson`, and
  `trajectories/floodscope-live/Nepal_Narayani_live.{ndjson,md}`.
- Numbers can differ by a little if Planetary Computer ingests a newer pass; override the dates with
  `--date YYYY-MM-DD --pre YYYY-MM-DD`.

---

## 4. Interactive before/after viewer — ~1 min

```bash
cd webviz
npm ci            # or: npm install
npm run dev       # → http://localhost:5173
# production build (proves clean-env reproducibility):
npm run build && npm run preview
```

- **What you see:** two synced maps over an OpenStreetMap basemap with a draggable divider — **left =
  pre-monsoon imagery, right = post-flood imagery + flood overlay** — plus the flood-area card (km², %) and
  a **Trajectory** tab that steps through the run. Requires internet for basemap tiles.
- The viewer reads only the static files from step 3. To regenerate the benchmark scenes too, run
  `PYTHONPATH=. .venv/bin/python scripts/export_viz.py` (optional; the viewer is Nepal-focused for this
  submission).

---

## 4b. Run the LLM agent (advanced solution) — needs your own key

Runs on **Claude or GPT-4o** — set whichever key you have (Anthropic is the default; the agent auto-selects,
or force it with `FLOODSCOPE_PROVIDER=openai|anthropic`).

```bash
# Claude (default):
export ANTHROPIC_API_KEY=sk-ant-...
PYTHONPATH=. .venv/bin/python -m floodscope.agent.flood_agent Spain_6860600

# or GPT-4o:
uv pip install openai
export OPENAI_API_KEY=sk-...    # OPENAI_MODEL defaults to gpt-4o
PYTHONPATH=. .venv/bin/python -m floodscope.agent.flood_agent Spain_6860600
```

**End-to-end orchestrator** (acquire → analyse → report → publish, LLM-written report):
```bash
PYTHONPATH=. .venv/bin/python -m floodscope.agent.orchestrator   # default AOI = Narayani/Chitwan
```
Pulls live Sentinel-1, maps the flood, writes the report, and (after a human checkpoint) publishes to the
dashboard — the result shows up in `webviz/` with a **Report** tab. ~$0.02/run; needs a key + internet.

- **What it does:** a Claude (`claude-opus-4-8`) tool-use agent inspects the scene, chooses a `FloodConfig`,
  runs segmentation, verifies plausibility, retries if it flooded a dry scene, and stops at a human
  checkpoint. Try a dry scene (`Spain_6860600`, `Somalia_699062`) to see the verify-and-retry behaviour.
- **Output:** prints turns / cost / IoU and writes `trajectories/flood-agent/<chip>.{ndjson,md}`.
- **Cost:** a few cents per scene (Opus pricing; one short tool-use loop).

## 5. Read a trajectory

```bash
# raw machine-readable events:
cat trajectories/floodscope-live/Nepal_Narayani_live.ndjson
# human-readable transcript (auto-rendered; regenerate with):
PYTHONPATH=. .venv/bin/python -m floodscope.agent.traj_render trajectories/floodscope-live/Nepal_Narayani_live.ndjson
```

---

## Approximate runtime & cost summary

| Step | Time | Cost |
|---|---|---|
| Install deps | ~2 min | $0 |
| Benchmark eval (first run downloads chips) | ~1–2 min | $0 |
| Live Nepal acquisition | ~30–60 s | $0 |
| Web viewer (`npm ci` + build) | ~30 s | $0 |

Everything reproduces with **no API keys and no paid services**. (An optional `ANTHROPIC_API_KEY` in `.env`
is only for the *planned* LLM-agent iteration; it is not used by anything in this submission.)

## Troubleshooting

- **`ModuleNotFoundError: floodscope`** running a script in `scripts/` → prefix with `PYTHONPATH=.`.
- **Planetary Computer timeout / DNS blip** → transient; re-run `scripts/acquire_nepal.py` (it's idempotent).
- **Blank map tiles** → the OSM basemap needs internet; overlays still render offline.
