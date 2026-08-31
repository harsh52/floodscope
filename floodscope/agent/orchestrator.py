"""FloodScope orchestrator — an LLM that runs the whole job: acquire → analyse →
report → visualise, for any AOI, behind a human checkpoint.

Where the per-chip agent (flood_agent.py) only *chose a threshold*, this agent
drives the end-to-end workflow: it pulls live Sentinel-1 for a bounding box and
dates, decides the analysis, verifies it, **writes the analyst report itself**,
and — after a human sign-off — publishes the result to the dashboard the
`webviz/` explorer reads. The science is in floodscope/live.py; the LLM supplies
the orchestration, judgement, and the written report.

Runs on Claude or GPT-4o (same backend as flood_agent). Needs your own key.
    PYTHONPATH=. python -m floodscope.agent.orchestrator
"""
from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from floodscope.agent import flood_agent as fa
from floodscope.agent.trajectory import Trajectory
from floodscope.agent.traj_render import render_markdown
from floodscope.live import LiveScene

ROOT = Path(__file__).resolve().parent.parent.parent
WEBVIZ = ROOT / "webviz" / "public"
REPORTS = ROOT / "reports"

# Default demo AOI/dates: the Narayani plain at Chitwan (same as the verified
# Nepal live demo), so `python -m ...orchestrator` reproduces out of the box.
DEFAULT_BBOX = [84.20, 27.63, 84.46, 27.83]
DEFAULT_POST, DEFAULT_PRE = "2026-08-28", "2026-03-30"

SYSTEM = """You are FloodScope, an autonomous flood-analysis agent. You produce a decision-grade flood
report for a region from live satellite radar, end to end. Water is dark in Sentinel-1 SAR.

Run this workflow with the tools (do not skip steps, do not invent numbers):
1. acquire_scene — pull the pre/post Sentinel-1 pair for the AOI. If it fails or coverage is low, say so
   and stop; do not fabricate a flood.
2. inspect_scene — read bimodality and water-fraction evidence.
3. map_flood — choose threshold_method from the evidence (bimodal -> "gated_otsu"; unimodal/low water ->
   "fixed"), and mask_steep_slopes=true unless the terrain is flat. Read back the flood area.
4. verify_result — if it fails, change the config and map_flood again (at most 2 retries).
5. write_report — write a concise analyst report (markdown): what was mapped, pre/post dates, surface-water
   and NEW-inundation area in km², the method and why, key caveats (coverage, no ground truth, monsoon
   baseline), and a clear confidence level. This is for a human responder — be accurate and calibrated.
6. publish_to_dashboard — only after write_report. A human reviewer signs off before/at publication.

Be decisive and brief in your own messages; put the detail in the report."""

TOOLS = [
    {"name": "acquire_scene",
     "description": "Pull the pre/post Sentinel-1 GRD pair for an AOI from Planetary Computer and load it.",
     "input_schema": {"type": "object", "properties": {
         "post_date": {"type": "string", "description": "post-event date YYYY-MM-DD"},
         "pre_date": {"type": "string", "description": "pre-event/baseline date YYYY-MM-DD"}},
         "required": ["post_date", "pre_date"], "additionalProperties": False}},
    {"name": "inspect_scene",
     "description": "Histogram bimodality + water-fraction proxy for the acquired post scene.",
     "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "map_flood",
     "description": "Run pre/post change detection with the chosen config; returns surface-water and new-inundation area.",
     "input_schema": {"type": "object", "properties": {
         "threshold_method": {"type": "string", "enum": ["gated_otsu", "fixed", "global_otsu"]},
         "mask_steep_slopes": {"type": "boolean"}},
         "required": ["threshold_method"], "additionalProperties": False}},
    {"name": "verify_result",
     "description": "Plausibility-check the flood map (water fraction sane, method consistent).",
     "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "write_report",
     "description": "Save the analyst report you wrote (markdown) for this scene.",
     "input_schema": {"type": "object", "properties": {
         "title": {"type": "string"},
         "report_markdown": {"type": "string", "description": "the full report, in markdown"},
         "confidence": {"type": "string", "enum": ["low", "medium", "high"]}},
         "required": ["title", "report_markdown", "confidence"], "additionalProperties": False}},
    {"name": "publish_to_dashboard",
     "description": "After write_report and human sign-off, render tiles + add the scene to the dashboard manifest.",
     "input_schema": {"type": "object", "properties": {
         "note": {"type": "string", "description": "one-line label for the scene"}},
         "required": ["note"], "additionalProperties": False}},
]


@dataclass
class OrchestratorOutcome:
    scene_id: str
    area: dict
    published: bool
    cost_usd: float
    turns: int
    report_path: str | None
    trajectory_path: str


class Orchestrator:
    def __init__(self, scene_id: str, bbox, auto_approve: bool = True):
        self.scene_id = scene_id
        self.scene = LiveScene(bbox)
        self.auto_approve = auto_approve
        self.report = self.title = self.confidence = None
        self.published = False
        self.traj: Trajectory | None = None

    # -- tools (return JSON-able dicts) --------------------------------------
    def acquire_scene(self, post_date, pre_date):
        return self.scene.acquire(post_date, pre_date)

    def inspect_scene(self):
        return self.scene.stats()

    def map_flood(self, threshold_method="gated_otsu", mask_steep_slopes=True):
        return self.scene.map_flood(threshold_method, mask_steep_slopes)

    def verify_result(self):
        return self.scene.verify()

    def write_report(self, title, report_markdown, confidence):
        self.title, self.report, self.confidence = title, report_markdown, confidence
        REPORTS.mkdir(parents=True, exist_ok=True)
        p = REPORTS / f"{self.scene_id}_report.md"
        p.write_text(f"# {title}\n\n_Confidence: {confidence}_\n\n{report_markdown}\n", encoding="utf-8")
        return {"ok": True, "saved": str(p.relative_to(ROOT))}

    def publish_to_dashboard(self, note):
        if self.report is None:
            return {"ok": False, "reason": "write_report before publishing"}
        # human checkpoint
        decision = "auto_approved_agent_run" if self.auto_approve else "declined"
        if not self.auto_approve:
            try:
                decision = "approved" if input(f"Publish '{self.scene_id}' to dashboard? [y/N] ").strip().lower() == "y" else "declined"
            except EOFError:
                decision = "declined"
        if self.traj is not None:
            self.traj.human_review(decision=decision, note=note)
        if decision == "declined":
            return {"ok": False, "reason": "human declined publication"}

        tiles_dir = WEBVIZ / "tiles" / self.scene_id
        self.scene.render(tiles_dir)
        sid, sc = self.scene_id, self.scene
        entry = {
            "chip": sid, "note": note, "live": True,
            "acquired": {"pre": sc.pre_item.properties["datetime"], "post": sc.post_item.properties["datetime"]},
            "bounds": sc.bounds, "view": sc.view,
            "center": [(sc.bounds[0][0] + sc.bounds[1][0]) / 2, (sc.bounds[0][1] + sc.bounds[1][1]) / 2],
            "size": list(sc.masks["water"].shape), "pixel_m": sc.res,
            "present": {
                "before": f"tiles/{sid}/before.png", "before_mask": f"tiles/{sid}/water_pre.png",
                "after": f"tiles/{sid}/after.png", "mask": f"tiles/{sid}/water.png",
                "mask2": f"tiles/{sid}/flood.png",
                "before_label": f"Pre · {sc.pre_item.properties['datetime'][:10]}",
                "after_label": f"Post · {sc.post_item.properties['datetime'][:10]}",
                "mask_label": "Surface water", "mask2_label": "New inundation",
                "legend": [{"color": "#38bdf8", "label": "surface water"},
                           {"color": "#facc15", "label": "new inundation"}]},
            "tiles": {"sar": f"tiles/{sid}/sar.png", "optical": f"tiles/{sid}/after.png",
                      "baseline": f"tiles/{sid}/baseline.png", "agent": f"tiles/{sid}/water.png"},
            "trajectory": f"trajectories/{sid}.ndjson",
            "metrics": {"baseline": {"threshold_method": "global-otsu(naive)"},
                        "agent": {"threshold_method": sc.method, **sc.area}},
            "flood": {**sc.area, "area_km2": sc.area["surface_water_km2"], "area_pct": sc.area["area_pct"]},
            "report": {"title": self.title, "confidence": self.confidence, "markdown": self.report},
            "delta_iou": None,
        }
        mpath = WEBVIZ / "manifest.json"
        manifest = json.loads(mpath.read_text()) if mpath.exists() else []
        manifest = [c for c in manifest if c["chip"] != sid] + [entry]
        mpath.write_text(json.dumps(manifest, indent=2))
        if self.traj is not None:  # copy trajectory for the dashboard's Trajectory tab
            (WEBVIZ / "trajectories").mkdir(parents=True, exist_ok=True)
        self.published = True
        return {"ok": True, "published": sid, "area": sc.area, "human_review": decision}

    def dispatch(self, name, args):
        return getattr(self, name)(**args)


def run_orchestrator(scene_id="Live_Narayani_agent", bbox=None, post_date=DEFAULT_POST,
                     pre_date=DEFAULT_PRE, auto_approve=True) -> OrchestratorOutcome:
    provider = fa._provider()
    fa._preflight(provider)
    model = os.getenv("OPENAI_MODEL", "gpt-4o") if provider == "openai" else fa.AGENT_MODEL
    orch = Orchestrator(scene_id, bbox or DEFAULT_BBOX, auto_approve=auto_approve)
    traj = Trajectory(agent="flood-orchestrator", case=scene_id)
    orch.traj = traj
    traj.system_prompt(SYSTEM)
    user = (f"Produce a flood report for AOI {orch.scene.bbox} — post-event ~{post_date}, "
            f"pre-event baseline ~{pre_date}. Acquire, analyse, verify, write the report, then publish.")
    traj.user_prompt(user)

    runner = fa._run_openai if provider == "openai" else fa._run_anthropic
    in_tok, out_tok, turns = runner(orch, traj, model, SYSTEM, user, TOOLS)
    traj.phase_complete("report")
    pin, pout = fa.PRICING[provider]
    cost = round(in_tok * pin + out_tok * pout, 4)
    traj.usage(input_tokens=in_tok, output_tokens=out_tok, cost_usd=cost)
    traj.checkpoint({"area": orch.scene.area, "published": orch.published, "cost_usd": cost})
    path = traj.close()
    render_markdown(path)
    if orch.published:  # mirror trajectory into the dashboard
        shutil.copy(path, WEBVIZ / "trajectories" / f"{scene_id}.ndjson")
    return OrchestratorOutcome(scene_id, orch.scene.area, orch.published, cost, turns,
                               f"reports/{scene_id}_report.md" if orch.report else None, str(path))


def main():
    print(f"Running FloodScope orchestrator (provider {fa._provider()}) on the default Narayani AOI ...")
    out = run_orchestrator()
    print(f"  turns={out.turns}  cost=${out.cost_usd}  published={out.published}  area={out.area}")
    print(f"  report: {out.report_path}")
    print(f"  trajectory: {out.trajectory_path}")


if __name__ == "__main__":
    main()
