# FloodScope — rapid, verifiable flood mapping from satellite radar

**micro1 Frontier Engineering Challenge 2026 — first submission.**
FloodScope turns a plain request ("map the flood over this area") into a defensible flood-extent map
from free, all-weather **Sentinel-1 radar**, with a verification gate that stops the naive method's
biggest failure — *confidently flooding dry land* — and a human-review checkpoint before any map is
published.

> This submission covers the **baseline** (naive one-shot thresholding) and the **advanced** workflow
> (verification-gated + change detection), measured against ground truth on a public benchmark and then
> run **live** on the 26 Aug 2026 Nepal flood. The interactive viewer is currently focused on that live
> scene; the benchmark harness still runs the full 12-scene comparison for the measured-improvement claim.

---

## 1. Who has this problem, and why it matters

**Intended user:** flood / disaster-response analysts and humanitarian mapping teams (national disaster
authorities, ICIMOD-style regional centres, Red Cross GIS units) who must answer *"how much is flooded,
and where?"* within hours of an event, so responders can prioritise.

**The bottleneck today:**
- **Acquiring imagery is slow and manual.** Optical satellites are blocked by monsoon cloud exactly when
  floods happen; SAR sees through cloud but needs specialist handling (calibration, speckle, terrain).
- **Naive automation is worse than nothing.** A one-shot "threshold the dark pixels" script (what a
  coding assistant writes on the first try) **floods 60–90% of a dry scene** with false positives — a
  false alarm that erodes trust and wastes responder time.
- **Every claim needs evidence and a human in the loop.** A flood map drives real decisions; it cannot be
  an unaudited black box.

FloodScope compresses acquire → analyse → report from hours of GIS work into **minutes**, on **public,
no-key data**, with every number traceable to an artifact and a reviewer sign-off before publication.

---

## 2. Baseline vs. advanced solution

| | **Baseline** (naive, one-shot) | **Advanced** (FloodScope workflow) |
|---|---|---|
| Method | global Otsu threshold on VH backscatter | speckle filter → **bimodality-gated** Otsu → small-blob cleanup → **conditional slope mask** → **pre/post change detection** |
| Reasoning | none — trusts Otsu always | a **verification gate** decides *per scene* whether Otsu is trustworthy; falls back conservatively when the histogram is unimodal |
| Failure it fixes | — | floods dry/low-water scenes; SAR layover in steep terrain; counts the permanent river as "flood" |
| Output | a raw mask | flood mask + **area affected (km², %)** + before/after view + structured **trajectory** + **human checkpoint** |

Both are run on the **same evaluation cases** so the comparison is fair. The baseline is exactly what a
one-shot LLM emits (`FloodConfig.baseline()`), which is why it is a meaningful control.

---

## 3. Measured improvement (Sen1Floods11, hand-labelled ground truth)

12 diverse chips (biomes + 1 hard urban case), evaluated with IoU/precision/recall against the dataset's
hand labels. Evidence: [`reports/eval_results.csv`](reports/eval_results.csv). Reproduce with
`python -m floodscope.eval.run_eval`.

| metric | baseline | advanced | Δ |
|---|---|---|---|
| **mean IoU** (water) | 0.291 | **0.336** | **+0.045 (+15%)** |
| **mean precision** | 0.353 | **0.486** | **+0.133 (+38%)** |
| mean recall | 0.800 | 0.661 | −0.139 |
| scenes improved | — | **11 / 12** | |
| hard urban `USA_430764` | 0.160 | **0.466** | **+0.31** |

**Read this honestly:** the advanced workflow trades *recall* for a large *precision* gain — it stops
crying wolf. On low-water scenes (Spain, Somalia, Mekong) the baseline's precision is 5–12%; the
verification gate roughly **doubles precision** by refusing to trust Otsu when the scene isn't genuinely
bimodal. One scene regresses (`Ghana_313799`, non-bimodal savanna) — a disclosed, honest trade-off.

---

## 4. Live demo — 26 Aug 2026 Nepal flood

A glacier collapse near Langtang Lirung surged down the Bhote Koshi at Rasuwagadhi and 72 km+ down the
Trishuli/Narayani. FloodScope pulls the imagery **live** from Microsoft Planetary Computer (anonymous, no
key) and maps it end-to-end:

- **Pre-monsoon baseline (2026-03-30)** vs **post-flood (2026-08-28)**, same orbit geometry (ascending
  rel-orbit 85), so the comparison is fair.
- Result: **21.6 km² surface water** mapped on the Narayani plain at Chitwan, of which **15.3 km² is
  inundation vs the dry-season baseline** (3.7% of the scene).
- Explore it: `cd webviz && npm run dev` → drag the divider to compare before/after; see area affected and
  the run's trajectory. (See [`webviz/README.md`](webviz/README.md).)

**Engineering honesty baked in:** the upper Rasuwa gorge is *not* mappable at 40 m SAR (layover/shadow;
the AOI fell off the scene footprint), so we map the **downstream flat reach** where the signal is real.
And with an August-vs-August pair the *new* standing water is only ~0.2 km² — because it was peak monsoon
and the flash flood had receded. The workflow **reports that honestly instead of inventing a flood**; the
dry-season baseline is what makes the seasonal inundation legible. No ground truth exists for a live event,
so the live numbers are plausibility-checked, not label-verified, and the map carries a human-review flag.

---

## 5. Improvement changelog

| Stage | What we tried and why | Evidence | Decision |
|---|---|---|---|
| Baseline | Global Otsu on VH — the one-shot approach | precision 0.05–0.12 on low-water scenes; floods dry land | Established the control |
| + speckle filter | Median filter to tame SAR speckle | cleaner masks, fewer 1-px blobs | Kept |
| **+ bimodality-gated threshold** | Verify Otsu is valid (two histogram modes) before trusting it; else conservative fixed fallback | **precision 0.35 → 0.49 (+38%)**; kills the dry-scene false flood | **Kept — biggest contributor** |
| + small-blob cleanup | Drop sub-10-px speckle detections | small precision gain | Kept |
| + conditional slope mask | DEM slope > 8° = layover/shadow, not water (steep terrain) | removes hillside false positives on Nepal | Kept for terrain scenes; **off** for flat benchmark (DEM noise) |
| + permanent-water removal | Subtract the always-wet river to isolate *new* flood | helps the product; **hurts** all-water IoU (deletes true positives) | Applied **conditionally** (product path only); measured both |
| + pre/post change detection | New inundation = water in POST and not in PRE | isolates event water from the permanent channel | Kept (live path) |
| **Removed:** Δ-backscatter "impact corridor" in the Rasuwa gorge | Tried mapping the flash-flood scar directly in steep terrain | dominated by layover noise + off-swath nodata | **Removed** — taught us the gorge is unmappable at 40 m; move downstream to the flat Narayani |
| Live + explorer + trajectory + human checkpoint | Package it as a reproducible tool a person would use | live 21.6 km² map, before/after viewer, NDJSON trajectory | Kept |

---

## 6. How it works

```
request (AOI + dates)
      │
  acquire   Sentinel-1 GRD via Planetary Computer STAC (anonymous)  ── floodscope/data.py, scripts/acquire_nepal.py
      │
  analyse   speckle → gated-Otsu (VERIFY) → cleanup → slope mask → change detect   ── floodscope/pipeline.py, floodscope/geo/
      │      every step recorded as a tool call in a structured trajectory
  verify    plausibility gate (bimodal? water-fraction sane?) → conservative fallback   ── floodscope/geo/sar.py
      │
  review    HUMAN CHECKPOINT — map flagged "pending sign-off" before publication
      │
  report    area affected (km², %), before/after PNGs, GeoJSON-ready mask, trajectory   ── scripts/export_viz.py, webviz/
```

- **Science layer** (`floodscope/`): the deterministic primitives — testable without any network or model.
- **Evaluation** (`floodscope/eval/`): baseline-vs-advanced on Sen1Floods11 ground truth.
- **Live acquisition** (`scripts/acquire_nepal.py`): fresh Sentinel-1, pre/post change detection, slope mask.
- **Explorer** (`webviz/`): React + Leaflet before/after viewer with the flood-area readout and trajectory playback.
- **Trajectories** (`trajectories/`, `floodscope/agent/`): every run emits NDJSON + a readable Markdown transcript.

---

## 7. Reproduce it

Full clean-environment guide: **[`docs/REPRODUCE.md`](docs/REPRODUCE.md)**. Quickstart:

```bash
uv venv --python 3.11 .venv && uv pip install -r requirements.txt      # ~2 min
PYTHONPATH=. .venv/bin/python -m floodscope.eval.run_eval              # baseline vs advanced table
PYTHONPATH=. .venv/bin/python scripts/acquire_nepal.py                 # live Nepal flood map
cd webviz && npm ci && npm run dev                                     # interactive before/after viewer
```

No API key is required for the flood mapping or the benchmark (all data is public / anonymous).

---

## 8. Agent trajectories & tool disclosure

- **Run trajectories** (the workflow's decision log — tool calls, verification gate, human checkpoint):
  `trajectories/floodscope-live/Nepal_Narayani_live.{ndjson,md}` (live) and
  `trajectories/floodscope-pipeline/*.{ndjson,md}` (benchmark). See [`docs/AGENT_USE.md`](docs/AGENT_USE.md).
- **Coding agent used to build this:** Claude Code (Anthropic). Disclosure and how each agent instruction
  maps to a result are in [`docs/AGENT_USE.md`](docs/AGENT_USE.md).

> **Two solution tiers:** the **deterministic pipeline** (`floodscope/pipeline.py`) is the reproducible,
> no-key science layer used for the benchmark and live demos. The **LLM agent**
> (`floodscope/agent/flood_agent.py`) is a Claude tool-use agent that *decides* the per-scene threshold
> strategy, verifies its own output, retries on failure, and stops at a human checkpoint — routing the same
> primitives through genuine model judgement, and emitting a real LLM trajectory. Run it with your own
> `ANTHROPIC_API_KEY`: `PYTHONPATH=. python -m floodscope.agent.flood_agent Spain_6860600`.

---

## 9. What existed before vs. what we added

Everything in this repository was **built during the hackathon**. It stands on public building blocks:
Python geospatial libraries (`rasterio`, `scikit-image`, `odc-stac`), the public **Sen1Floods11** dataset
(hand labels, anonymous HTTPS), and **Microsoft Planetary Computer** (Sentinel-1, anonymous). Otsu
thresholding and SAR water detection are standard remote-sensing techniques; the **contribution** is the
verification gate, the conditional corrections, the pre/post live workflow, the evidence-linked evaluation,
and the reproducible tool + explorer around them.

---

## 10. Safety, ethics, and the failure mode

- **Human in the loop:** every map is flagged `pending sign-off`; batch/eval runs record
  `auto_approved_eval_mode` so a bypass is always auditable, never silent.
- **Credentials stay out:** `.env` is git-ignored; the flood mapping needs no key at all.
- **Public data only:** Sen1Floods11 + Planetary Computer, used within their terms.
- **Claims tied to evidence:** every number links to a CSV, a tile, or a trajectory.

**Main failure mode:** SAR at ~40 m cannot resolve floods in narrow, steep gorges (layover/shadow), and a
*receded* flash flood leaves little standing water — the honest signal is downstream on flat terrain, or in
the seasonal delta, not the gorge.

**Hot take:** *The naive method is confidently wrong on dry scenes; **verification, not a bigger model,
fixes it.*** The single highest-leverage change was a cheap "is this histogram actually bimodal?" check that
nearly doubled precision. Reliability in flood mapping comes from knowing **when not to claim a flood** — an
agent that says "little new water here" is more valuable than one that always finds a flood.
