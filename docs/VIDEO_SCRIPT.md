# Solution video — 5-minute storyboard

Record ≤5 min. Screen-record the terminal + the web viewer; talk over it. Keep it calm and concrete —
every claim on screen is backed by a file. Suggested cuts and narration below (≈4:30 to leave margin).

---

### 0:00–0:40 — The problem & the user
**Show:** a news photo/headline of the 26 Aug 2026 Nepal flood, then the plain question *"how much is
flooded, and where?"*
**Say:** "When a flood hits, response teams need a flood-extent map within hours. Optical satellites are
blocked by monsoon cloud; radar sees through it but needs expertise. And the naive automation — just
threshold the dark pixels — is *worse than nothing*: it floods dry land with false positives. FloodScope
fixes that, on free public data, in minutes."

### 0:40–1:20 — The baseline (and why it fails)
**Show:** terminal → `python -m floodscope.eval.run_eval`; while it runs, open the viewer's *Baseline*
comparison (or a saved figure) on a **dry scene** (Spain/Somalia).
**Say:** "Baseline is a single global Otsu threshold — exactly what a one-shot LLM writes. On a scene with
lots of water it's fine. But on a *dry* scene the histogram has no water mode, so Otsu splits the land and
floods 60–90% of the tile. Precision collapses to 5–12%. That's the failure real engineering has to catch."

### 1:20–2:40 — One realistic execution, start to finish (the hero)
**Show:** `python scripts/acquire_nepal.py` running — point at the printed lines: STAC search, the pre
(Mar 30) and post (Aug 28) scene IDs, and `surface water: 21.62 km² … new inundation vs pre: 15.26 km²`.
Then `cd webviz && npm run dev`, open **http://localhost:5173**, and **drag the divider**.
**Say:** "One command pulls the imagery live from Planetary Computer — no API key — finds a pre-monsoon and
a post-flood pass on the *same orbit*, and runs the workflow: speckle filter, a **verification-gated**
threshold, cleanup, a DEM slope mask for the steep terrain, and pre/post change detection. Here's the
result on a real map: left is the dry-season river, right is the post-flood inundation — 15 km² — with the
area affected quantified. Flip to the **Trajectory** tab: every tool call, the verification, and the
**human-review checkpoint** before this map is ever published."

### 2:40–3:40 — The measured comparison
**Show:** the `run_eval` summary table (baseline vs agent) and `reports/eval_results.csv`.
**Say:** "Measured against Sen1Floods11 hand labels on 12 scenes: mean IoU up 15%, and **precision up 38%**
— it improves on 11 of 12. It trades a little recall to stop crying wolf. The hard urban case goes from
0.16 to 0.47 IoU. Every number here is one row in a CSV in the repo."

### 3:40–4:15 — Changelog: what mattered, and what I removed
**Show:** the Improvement Changelog table in the README.
**Say:** "The single biggest lever was cheap: a **'is this histogram actually bimodal?'** check before
trusting Otsu — that one gate is most of the +38% precision. And one experiment I *removed*: I first tried
to map the flash flood right in the Rasuwa gorge with change-detection. It was noise — 40 m radar can't
resolve a narrow steep valley, and the scene footprint didn't even cover it. That failure taught me to move
downstream to the flat Narayani, where the signal is real."

### 4:15–4:30 — Hot take
**Say:** "My hot take: the naive method is confidently wrong on dry scenes, and **verification — not a
bigger model — fixes it**. In flood mapping, an agent that knows *when not to claim a flood* is more
valuable than one that always finds one."

---

## Capture checklist
- [ ] Terminal font large enough to read; clear the scrollback first.
- [ ] Run `acquire_nepal.py` once beforehand so the live demo is warm (or accept a ~40 s wait on camera).
- [ ] Have the viewer already at `localhost:5173` in a second window.
- [ ] Show `reports/eval_results.csv` and one `trajectories/floodscope-live/*.md` on screen at least once.
- [ ] End under 5:00.
