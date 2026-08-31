"""FloodScope agent — an LLM (Claude) that maps flood water by *deciding*, per
scene, how to threshold Sentinel-1 SAR, then verifying its own output.

This is the advanced solution's agentic core. Unlike the deterministic pipeline
(which applies one fixed config), the agent:
  1. inspects the scene through a tool (histogram bimodality, water fraction,
     terrain, available context) — it never sees raw pixels,
  2. chooses a FloodConfig from that evidence (bimodal → Otsu; unimodal → fixed
     fallback; steep terrain → slope mask; product mode → drop permanent water),
  3. runs the segmentation tool,
  4. verifies plausibility (did it flood a dry scene?) and RETRIES with a
     different config if the check fails,
  5. stops at a human-review checkpoint before the map is "published".

Every turn — the model's text, each tool call, each tool result, the
verification, retries, and the human checkpoint — is written to a trajectory
(the required deliverable). Tools wrap the existing `floodscope` primitives, so
the science is unchanged; the agent only supplies the judgement.

Run: needs your own ANTHROPIC_API_KEY (participants use their own agent setup).
    PYTHONPATH=. python -m floodscope.agent.flood_agent Spain_6860600
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

import numpy as np

from floodscope import data
from floodscope.config import AGENT_MODEL
from floodscope.agent.trajectory import Trajectory
from floodscope.agent.traj_render import render_markdown
from floodscope.eval.iou import evaluate
from floodscope.geo import sar
from floodscope.pipeline import FloodConfig, FloodResult, map_flood

# Per-provider pricing ($/token) for cost-per-report accounting.
PRICING = {
    "anthropic": (5.0 / 1e6, 25.0 / 1e6),   # claude-opus-4-8
    "openai": (2.5 / 1e6, 10.0 / 1e6),       # gpt-4o (approx)
}
MAX_TURNS = 8


def _provider() -> str:
    """Pick the LLM backend: explicit FLOODSCOPE_PROVIDER, else whichever key is set
    (Anthropic preferred). The agent logic is identical either way."""
    p = os.getenv("FLOODSCOPE_PROVIDER", "").lower()
    if p in ("anthropic", "openai"):
        return p
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    return "anthropic"

SYSTEM = """You are FloodScope, a flood-mapping analyst. Given a Sentinel-1 SAR scene, produce a
water mask by choosing HOW to threshold it, then verifying your own result. Water is dark in SAR.

Workflow (use the tools; do not guess):
1. Call inspect_scene first. Read the bimodality and water-fraction evidence.
2. Call run_segmentation with a FloodConfig you justify from that evidence:
   - histogram bimodal (a clear water mode) -> threshold_method="gated_otsu".
   - histogram unimodal / very low water -> threshold_method="fixed" (global Otsu would flood dry land).
   - steep terrain present -> mask_steep_slopes=true (SAR layover looks like water on slopes).
   - always speckle=true and cleanup_min_size=10 for tidy masks.
3. Call verify_result. If it fails (e.g. an implausibly large water fraction on a low-water scene),
   change the config and run_segmentation again. At most 2 retries.
4. When verify_result passes, stop and give a one-paragraph summary: the config you chose, why,
   the flood area, and your confidence. A human reviewer signs off after you — flag low confidence.

Be decisive and brief. The naive failure mode is trusting Otsu on a dry scene and flooding it."""

TOOLS = [
    {
        "name": "inspect_scene",
        "description": "Return scene statistics (VH histogram bimodality, water-fraction proxy, "
        "backscatter percentiles, whether permanent-water and terrain context are available). "
        "Call this before segmenting.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "run_segmentation",
        "description": "Classify flood water with the chosen FloodConfig and return metrics "
        "(water area, water fraction, threshold used) plus IoU vs ground truth when available.",
        "input_schema": {
            "type": "object",
            "properties": {
                "threshold_method": {"type": "string", "enum": ["gated_otsu", "global_otsu", "tile", "fixed"]},
                "speckle": {"type": "boolean"},
                "mask_steep_slopes": {"type": "boolean"},
                "remove_permanent_water": {"type": "boolean"},
                "cleanup_min_size": {"type": "integer"},
            },
            "required": ["threshold_method"],
            "additionalProperties": False,
        },
    },
    {
        "name": "verify_result",
        "description": "Plausibility-check the most recent segmentation (water fraction in a sane band, "
        "method consistent with scene bimodality). Returns passed=true/false with reasons.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
]


@dataclass
class AgentOutcome:
    result: FloodResult | None
    metrics: dict
    cost_usd: float
    turns: int
    trajectory_path: str


class FloodAgent:
    """Holds the loaded scene and executes the tools the model calls."""

    def __init__(self, chip: str):
        data.download_chip(chip)
        self.chip = chip
        self.vv, self.vh = data.read_s1(chip)
        try:
            self.label = data.read_label(chip)
        except Exception:
            self.label = None
        try:
            self.jrc = data.read_jrc_permanent(chip)
        except Exception:
            self.jrc = None
        self.ref = data.chip_path(chip, "S1Hand")
        self.bounds = data.chip_bounds(chip)
        self.last: FloodResult | None = None
        self._bimodal: bool | None = None

    # -- tools ---------------------------------------------------------------
    def inspect_scene(self) -> dict:
        v = self.vh[np.isfinite(self.vh)]
        self._bimodal = bool(sar.is_bimodal(v))
        lo, mid, hi = (float(x) for x in np.percentile(v, [5, 50, 95]))
        # water proxy: fraction darker than a conservative fixed threshold
        water_frac = float(np.mean(v < -20.0))
        return {
            "band": "VH (dB)",
            "histogram_bimodal": self._bimodal,
            "water_fraction_proxy": round(water_frac, 3),
            "vh_percentiles_db": {"p5": round(lo, 1), "p50": round(mid, 1), "p95": round(hi, 1)},
            "permanent_water_available": self.jrc is not None,
            "terrain_masking_available": True,
            "hint": "bimodal -> gated_otsu; unimodal or tiny water_fraction -> fixed",
        }

    def run_segmentation(self, **kw) -> dict:
        cfg = FloodConfig(
            band="vh",
            speckle=bool(kw.get("speckle", True)),
            threshold_method=kw.get("threshold_method", "gated_otsu"),
            remove_permanent_water=bool(kw.get("remove_permanent_water", False)),
            mask_steep_slopes=bool(kw.get("mask_steep_slopes", False)),
            cleanup_min_size=int(kw.get("cleanup_min_size", 10)),
        )
        res = map_flood(self.vv, self.vh, cfg, jrc=self.jrc, ref_tif=self.ref, bounds=self.bounds)
        self.last = res
        valid = int(np.isfinite(self.vh).sum())
        frac = float(res.water.sum()) / valid if valid else 0.0
        out = {
            "threshold_method": res.threshold_method,
            "threshold_db": round(float(res.threshold_db), 2),
            "water_fraction": round(frac, 3),
            "water_area_km2": round(int(res.water.sum()) * 1e-4, 2),  # 10 m px
            "steps": res.provenance.get("steps", []),
        }
        if self.label is not None:
            m = evaluate(res.water, self.label)
            out["iou_vs_truth"] = None if np.isnan(m.iou) else round(float(m.iou), 3)
            out["precision"] = None if np.isnan(m.precision) else round(float(m.precision), 3)
        return out

    def verify_result(self) -> dict:
        if self.last is None:
            return {"passed": False, "reasons": ["no segmentation run yet"]}
        valid = int(np.isfinite(self.vh).sum())
        frac = float(self.last.water.sum()) / valid if valid else 0.0
        method = self.last.threshold_method
        reasons, passed = [], True
        # the naive failure: Otsu floods a non-bimodal (dry) scene
        if frac > 0.6:
            passed = False
            reasons.append(f"water fraction {frac:.2f} implausibly high — likely flooded a dry scene")
        if self._bimodal is False and "otsu" in method and "fallback" not in method:
            passed = False
            reasons.append("Otsu used on a non-bimodal histogram — switch to fixed fallback")
        if passed:
            reasons.append(f"water fraction {frac:.2f} plausible; method '{method}' consistent with scene")
        return {"passed": passed, "reasons": reasons}

    def dispatch(self, name: str, args: dict) -> dict:
        return {"inspect_scene": self.inspect_scene,
                "run_segmentation": lambda: self.run_segmentation(**args),
                "verify_result": self.verify_result}[name]()


def _log_tool(traj: Trajectory, agent: FloodAgent, name: str, args: dict) -> str:
    """Run one tool call, log it (verification events are special), return the JSON summary."""
    traj.tool_call(name, args)
    out = agent.dispatch(name, args)
    summary = json.dumps(out)
    if name == "verify_result":
        traj.verification(passed=out["passed"], checks=out)
    else:
        traj.tool_result(name, summary=summary, ok=True)
    return summary


def _run_anthropic(agent, traj, model, system, user):
    import anthropic
    client = anthropic.Anthropic()  # resolves ANTHROPIC_API_KEY / ant profile
    messages: list[dict] = [{"role": "user", "content": user}]
    in_tok = out_tok = turn = 0
    for turn in range(MAX_TURNS):
        resp = client.messages.create(
            model=model, max_tokens=8000, system=system, tools=TOOLS,
            thinking={"type": "adaptive"}, messages=messages,
        )
        in_tok += resp.usage.input_tokens
        out_tok += resp.usage.output_tokens
        for block in resp.content:
            if block.type == "text" and block.text.strip():
                traj.assistant_text(block.text)
        if resp.stop_reason == "end_turn":
            break
        messages.append({"role": "assistant", "content": resp.content})
        results = [
            {"type": "tool_result", "tool_use_id": b.id,
             "content": _log_tool(traj, agent, b.name, dict(b.input))}
            for b in resp.content if b.type == "tool_use"
        ]
        messages.append({"role": "user", "content": results})
    return in_tok, out_tok, turn + 1


def _run_openai(agent, traj, model, system, user):
    from openai import OpenAI
    client = OpenAI()  # resolves OPENAI_API_KEY
    oai_tools = [{"type": "function", "function": {
        "name": t["name"], "description": t["description"], "parameters": t["input_schema"]}}
        for t in TOOLS]
    messages: list[dict] = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    in_tok = out_tok = turn = 0
    for turn in range(MAX_TURNS):
        resp = client.chat.completions.create(
            model=model, messages=messages, tools=oai_tools, tool_choice="auto",
        )
        if resp.usage:
            in_tok += resp.usage.prompt_tokens
            out_tok += resp.usage.completion_tokens
        msg = resp.choices[0].message
        if msg.content and msg.content.strip():
            traj.assistant_text(msg.content)
        if not msg.tool_calls:
            break
        messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": [
            {"id": tc.id, "type": "function",
             "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in msg.tool_calls]})
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments or "{}")
            summary = _log_tool(traj, agent, tc.function.name, args)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": summary})
    return in_tok, out_tok, turn + 1


def _preflight(provider: str) -> None:
    """Fail with a clear, actionable message (not a raw traceback) if the chosen
    provider's SDK or key is missing."""
    if provider == "openai":
        try:
            import openai  # noqa: F401
        except ImportError:
            raise SystemExit("OpenAI backend needs the SDK:  uv pip install openai")
        if not os.getenv("OPENAI_API_KEY"):
            raise SystemExit("Set OPENAI_API_KEY (your own key) to run the OpenAI agent. "
                             "See docs/REPRODUCE.md §4b.")
    else:  # anthropic
        try:
            import anthropic  # noqa: F401
        except ImportError:
            raise SystemExit("Anthropic backend needs the SDK:  uv pip install anthropic")
        if not (os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")):
            raise SystemExit("Set ANTHROPIC_API_KEY, or FLOODSCOPE_PROVIDER=openai to use GPT-4o. "
                             "See docs/REPRODUCE.md §4b.")


def run_agent(chip: str, model: str | None = None) -> AgentOutcome:
    provider = _provider()
    _preflight(provider)
    if model is None:
        model = os.getenv("OPENAI_MODEL", "gpt-4o") if provider == "openai" else AGENT_MODEL
    agent = FloodAgent(chip)
    traj = Trajectory(agent="flood-agent", case=chip)
    traj.system_prompt(SYSTEM)
    traj.event("assistant_text", text=f"[provider={provider} model={model}]")
    user = f"Map the flood water in Sentinel-1 scene '{chip}'. Decide the thresholding strategy, verify it, and report."
    traj.user_prompt(user)

    runner = _run_openai if provider == "openai" else _run_anthropic
    in_tok, out_tok, turns = runner(agent, traj, model, SYSTEM, user)
    traj.phase_complete("report")

    price_in, price_out = PRICING[provider]
    cost = in_tok * price_in + out_tok * price_out
    traj.usage(input_tokens=in_tok, output_tokens=out_tok, cost_usd=round(cost, 4))
    traj.human_review(decision="pending", note="flood map awaiting analyst sign-off before publication")

    metrics = {}
    if agent.last is not None and agent.label is not None:
        m = evaluate(agent.last.water, agent.label)
        metrics = {"iou": None if np.isnan(m.iou) else round(float(m.iou), 3),
                   "precision": None if np.isnan(m.precision) else round(float(m.precision), 3),
                   "recall": None if np.isnan(m.recall) else round(float(m.recall), 3),
                   "threshold_method": agent.last.threshold_method}
    traj.checkpoint({"metrics": metrics, "cost_usd": round(cost, 4)})
    path = traj.close()
    render_markdown(path)
    return AgentOutcome(agent.last, metrics, round(cost, 4), turns, str(path))


def main() -> None:
    import sys
    chip = sys.argv[1] if len(sys.argv) > 1 else "Spain_6860600"
    print(f"Running FloodScope agent on {chip} (provider {_provider()}) ...")
    out = run_agent(chip)
    print(f"  turns={out.turns}  cost=${out.cost_usd}  metrics={out.metrics}")
    print(f"  trajectory: {out.trajectory_path}")


if __name__ == "__main__":
    main()
