# Solution video — 5-minute storyboard

Record ≤5 min. Screen-record the terminal + the web explorer; talk over it. Every number on screen is
backed by a file. Suggested cuts + narration (≈4:40). The "one realistic execution" is the **LLM
orchestrator** — the most complete run.

---

### 0:00–0:35 — Problem & user
**Show:** a headline of the 26 Aug 2026 Nepal flood, then the question *"how much is flooded, and where?"*
**Say:** "When a flood hits, response teams need a flood-extent map within hours. Optical satellites are
blocked by monsoon cloud; radar sees through it but needs expertise. And naive automation is *worse than
nothing* — it floods dry land with false positives. FloodScope is an agent that does the whole job: pull
the radar, map the flood, write the report — with a human in the loop."

### 0:35–1:15 — The baseline, and why it fails
**Show:** terminal → `python -m floodscope.eval.run_eval` (let it print); open the explorer on a **dry**
scene (Spain/Somalia), toggle Baseline.
**Say:** "Baseline is a single global-Otsu threshold — what a one-shot LLM writes. On a dry scene there's no
water mode, so Otsu splits the land and floods 40–90% of the tile. Precision collapses to 5–12%. Catching
that failure is the whole game."

### 1:15–1:45 — The measured comparison
**Show:** the `run_eval` summary table + `reports/eval_results.csv`.
**Say:** "Across 12 hand-labelled Sen1Floods11 scenes: mean IoU up 15%, **precision up 38%** — better on 11
of 12. It trades a little recall to stop crying wolf. The hard urban case goes 0.16 → 0.47. Every number is
one row in a CSV in the repo."

### 1:45–3:15 — One realistic execution: the LLM agent, end to end (the hero)
**Show:** `export OPENAI_API_KEY=…` then `python -m floodscope.agent.orchestrator`. Narrate the printed
turns. Then open the explorer → the `Live_Narayani_agent` scene → **Report** tab, then **Trajectory** tab.
**Say:** "Here's the agent running the whole job on live data. It **acquires** the pre/post Sentinel-1 pair
from Planetary Computer — no API key for the imagery — then **inspects** the scene, **decides** the
thresholding method from the evidence, **verifies** its own map, and if it had flooded a dry scene it would
**retry**. Then — and this is the part only an LLM can do — it **writes the analyst report itself**: dates,
method and why, area affected, caveats, a calibrated confidence. A human signs off, and it **publishes to
the dashboard**. Flip to the Trajectory tab: every step — acquire, inspect, map, verify, write-report,
human review — is logged. ~$0.02, start to finish."
**Show (contrast):** briefly run `python -m floodscope.agent.flood_agent USA_905409` → "same agent, a
water-rich scene: it independently picks `gated_otsu` and hits 0.91 IoU. Different scene, different
decision, same tools."

### 3:15–3:55 — Changelog: what mattered, what I removed
**Show:** the Improvement Changelog table in the README.
**Say:** "The single biggest lever was cheap: a **'is this histogram actually bimodal?'** verification check
before trusting Otsu — most of the +38% precision. Then I turned those decisions over to the LLM. And one
experiment I *removed*: mapping the flash flood directly in the Rasuwa gorge — 40 m radar can't resolve a
steep narrow valley and the scene didn't even cover it. That failure taught me to move downstream to the
flat Narayani, where the signal is real."

### 3:55–4:20 — Reproducibility & safety
**Show:** `docs/REPRODUCE.md` table; the `pending sign-off` / human-review line in a trajectory.
**Say:** "The baseline table and the dashboard reproduce from a clean environment with no key — I verified
it in a fresh venv. Consequential steps are human-gated; credentials stay out of the repo."

### 4:20–4:40 — Hot take
**Say:** "My hot take: the naive method is confidently wrong on dry scenes, and **verification — not a
bigger model — fixes it**. The most valuable thing an agent can do in flood mapping is know *when not to
claim a flood.*"

---

## Capture checklist
- [ ] Run `orchestrator` once beforehand so the live demo is warm (or accept a ~40 s wait on camera).
- [ ] Explorer already open at `localhost:5173`, on the `Live_Narayani_agent` scene.
- [ ] Show `reports/eval_results.csv`, one `trajectories/flood-orchestrator/*.md`, and the Report tab.
- [ ] Large terminal font; clear scrollback first. End under 5:00.
