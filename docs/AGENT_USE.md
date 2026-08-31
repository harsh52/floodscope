# Agent use & trajectories

This documents (a) the coding agents used to **build** FloodScope, and (b) the run **trajectories** the
workflow emits — the required "agent trajectories" deliverable.

---

## A. Coding agents used to build this project (disclosure)

| Tool | Role | What it did |
|---|---|---|
| **Claude Code** (Anthropic, Claude Opus) | primary coding agent | scaffolded the pipeline, wrote the eval harness, the live acquisition, the React explorer, and these docs — under human direction and review at every step |

All code was written during the hackathon with a human (the participant) directing, reviewing, and
deciding every design choice. No other AI coding tools were used. Building this submission with a coding
agent satisfies the challenge's "coding-agent use is required + disclose your tools" rule.

---

## B. Run trajectories (the workflow's decision log)

Every FloodScope run writes a **trajectory**: newline-delimited JSON (`.ndjson`), one event per line, plus
an auto-rendered human-readable transcript (`.md`). It is easy to follow from the instruction through to
the result, shows each tool call and its response, the verification signal that shaped the next step, and
the human checkpoint.

**Representative trajectories to review:**

| File | What it captures |
|---|---|
| `trajectories/floodscope-live/Nepal_Narayani_live.md` | the **live** 26 Aug 2026 Nepal run: STAC search → load VH → speckle+threshold → change detection → verification → **human review** |
| `trajectories/floodscope-live/Nepal_Narayani_live.ndjson` | the same run, machine-readable (what a judge replays) |
| `trajectories/flood-orchestrator/Live_Narayani_agent.md` | **end-to-end LLM orchestrator** (GPT-4o): acquire live Sentinel-1 → inspect → map → verify → **writes the report** → human sign-off → publish to dashboard |
| `trajectories/flood-agent/USA_905409.md` | **real LLM agent** (GPT-4o): water-rich scene → agent reasons "bimodal" → picks `gated_otsu` → IoU **0.912** |
| `trajectories/flood-agent/Spain_6860600.md` | **real LLM agent**: dry scene → agent reasons "unimodal, low water" → picks `fixed`, avoiding the naive flood |
| `trajectories/floodscope-pipeline/USA_430764.md` | a benchmark run on the hard urban case (biggest deterministic win, IoU 0.16→0.47) |

**Event vocabulary** (`floodscope/agent/trajectory.py`): `system_prompt`, `user_prompt`, `assistant_text`,
`code_emitted`, `tool_call`, `tool_result`, `code_stdout`, `verification`, `retry`, `human_review`,
`checkpoint`, `usage`, `phase_complete`.

**Example (excerpt, Nepal live):**
```
tool_call     stac_search {collection: sentinel-1-grd, orbit: ascending}
tool_result   selected S1D_..._20260828T122141_... @ 2026-08-28
tool_call     change_detect {rule: "water in POST and not in PRE, min_blob=8"}
tool_result   new inundation 15.26 km² (…); total post-water 21.62 km²
verification   PASSED  {threshold_method: …, permanent_channel_excluded: true, no_ground_truth: true}
human_review   pending — "live flood extent requires analyst sign-off before any use"
```

The **Trajectory tab** in the web explorer (`webviz/`) plays these events back visually next to the map, so
the result and *how it was produced* are shown together.

Regenerate a Markdown transcript from any `.ndjson`:
```bash
PYTHONPATH=. .venv/bin/python -m floodscope.agent.traj_render <path>.ndjson
```

---

## C. Two agent tiers

- **Deterministic pipeline** (`floodscope/pipeline.py`) — the reproducible, no-key science layer. Its
  trajectories (`floodscope-pipeline/*`, `floodscope-live/*`) are structured step logs, not LLM turns.
- **LLM agent** (`floodscope/agent/flood_agent.py`) — a **Claude (`claude-opus-4-8`) tool-use agent** that
  makes the per-scene decisions itself: it calls `inspect_scene`, chooses a `FloodConfig` from the evidence,
  calls `run_segmentation`, calls `verify_result`, and **retries with a different config when verification
  fails** (e.g. Otsu flooded a dry scene), then stops at a human-review checkpoint. Each turn — the model's
  reasoning, every tool call and result, the verification, retries, cost — is written to
  `trajectories/flood-agent/<chip>.{ndjson,md}`. This is a genuine agent trajectory. Run it with your own
  `ANTHROPIC_API_KEY`:

  ```bash
  PYTHONPATH=. python -m floodscope.agent.flood_agent Spain_6860600
  ```

The agent reuses the same primitives as the pipeline, so the science is identical — the agent supplies only
the judgement (which strategy, is the result plausible, retry or accept). It runs on **Claude
(`claude-opus-4-8`)** or **OpenAI (`gpt-4o`)** — it auto-selects by whichever key is set, or force it with
`FLOODSCOPE_PROVIDER=anthropic|openai`. Same tools, same trajectory format either way.

**Verified end-to-end (GPT-4o), ~$0.009/scene:** the agent adapts per scene — `gated_otsu` on a water-rich
bimodal scene (`USA_905409`, IoU **0.912**), `fixed` on dry scenes (`Spain_6860600`, `Somalia_699062`),
avoiding the naive dry-scene flood. Committed trajectories: `trajectories/flood-agent/*.{ndjson,md}`.
