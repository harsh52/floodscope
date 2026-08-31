"""Agent trajectory recording (NDJSON).

Every LLM agent in FloodScope — the one-shot baseline and the advanced
multi-phase agent — records what it did as a stream of newline-delimited JSON
events. This is the hackathon's required "agent trajectory" deliverable: it is
easy to follow from the agent instructions through to the final result, shows
what the agent did and how its tools responded, and captures the feedback that
shaped its next step plus any retries or human checkpoints.

One event per line keeps trajectories greppable, diff-able, and replayable, and
lets the React explorer step through them. Raw tool output (arrays, rasters) is
kept out of the model's context and out of the trajectory — we log compact
summaries and point at the artifact files instead (schema-separated outputs).

Usage
-----
    traj = Trajectory(agent="baseline-oneshot", case="Spain_6860600")
    traj.system_prompt(SYSTEM)
    traj.user_prompt(prompt)
    traj.assistant_text(reply)
    traj.code_emitted(code)
    traj.code_stdout(summary, ok=True)
    traj.verification(passed=False, checks={...})
    traj.retry(attempt=1, reason="water fraction implausible (0.82)")
    traj.human_review(decision="approved", note="analyst confirmed extent")
    traj.usage(input_tokens=1200, output_tokens=340, cost_usd=0.0121)
    traj.phase_complete("report")
    traj.close()
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from floodscope.config import TRAJECTORIES_DIR

# The event vocabulary. Kept small and explicit so the renderer and the React
# playback tab can rely on it.
EVENT_TYPES = (
    "system_prompt",
    "user_prompt",
    "assistant_text",
    "code_emitted",
    "tool_call",
    "tool_result",
    "code_stdout",
    "verification",
    "retry",
    "human_review",
    "checkpoint",
    "usage",
    "phase_complete",
)


class Trajectory:
    """Append-only NDJSON recorder for a single agent run over a single case."""

    def __init__(
        self,
        agent: str,
        case: str,
        *,
        base_dir: Path | None = None,
        phase: str | None = None,
        workflow_id: str | None = None,
    ) -> None:
        self.agent = agent
        self.case = case
        self.phase = phase
        # workflow_id ties every event of this run together (agent + case is
        # stable and human-readable; callers can override for batch runs).
        self.workflow_id = workflow_id or f"{agent}:{case}"
        self._seq = 0
        self.events: list[dict[str, Any]] = []

        out_dir = (base_dir or TRAJECTORIES_DIR) / agent
        out_dir.mkdir(parents=True, exist_ok=True)
        self.path = out_dir / f"{case}.ndjson"
        # Truncate any previous run for this case so a re-run is clean.
        self._fh = self.path.open("w", encoding="utf-8")

    # -- core -----------------------------------------------------------------
    def event(self, event_type: str, *, phase: str | None = None, **payload: Any) -> dict:
        """Record one event. `payload` is merged into the JSON line."""
        if event_type not in EVENT_TYPES:
            raise ValueError(f"unknown event_type {event_type!r}; add it to EVENT_TYPES")
        now = time.time()
        rec = {
            "seq": self._seq,
            "ts": now,
            "iso": datetime.fromtimestamp(now, timezone.utc).isoformat(),
            "workflow_id": self.workflow_id,
            "agent": self.agent,
            "case": self.case,
            "phase": phase if phase is not None else self.phase,
            "event_type": event_type,
            **payload,
        }
        self._seq += 1
        self.events.append(rec)
        self._fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self._fh.flush()
        return rec

    def set_phase(self, phase: str) -> None:
        self.phase = phase

    # -- convenience wrappers (one per event type) ----------------------------
    def system_prompt(self, text: str, **kw: Any) -> dict:
        return self.event("system_prompt", text=text, **kw)

    def user_prompt(self, text: str, **kw: Any) -> dict:
        return self.event("user_prompt", text=text, **kw)

    def assistant_text(self, text: str, **kw: Any) -> dict:
        return self.event("assistant_text", text=text, **kw)

    def code_emitted(self, code: str, language: str = "python", **kw: Any) -> dict:
        return self.event("code_emitted", code=code, language=language, **kw)

    def tool_call(self, name: str, args: dict | None = None, **kw: Any) -> dict:
        return self.event("tool_call", name=name, args=args or {}, **kw)

    def tool_result(self, name: str, summary: str, *, ok: bool = True, **kw: Any) -> dict:
        return self.event("tool_result", name=name, summary=summary, ok=ok, **kw)

    def code_stdout(self, stdout: str, *, ok: bool = True, **kw: Any) -> dict:
        return self.event("code_stdout", stdout=stdout, ok=ok, **kw)

    def verification(self, *, passed: bool, checks: dict, **kw: Any) -> dict:
        return self.event("verification", passed=passed, checks=checks, **kw)

    def retry(self, *, attempt: int, reason: str, **kw: Any) -> dict:
        return self.event("retry", attempt=attempt, reason=reason, **kw)

    def human_review(self, *, decision: str, note: str = "", **kw: Any) -> dict:
        return self.event("human_review", decision=decision, note=note, **kw)

    def checkpoint(self, data: dict, **kw: Any) -> dict:
        return self.event("checkpoint", data=data, **kw)

    def usage(self, *, input_tokens: int, output_tokens: int, cost_usd: float, **kw: Any) -> dict:
        return self.event(
            "usage", input_tokens=input_tokens, output_tokens=output_tokens, cost_usd=cost_usd, **kw
        )

    def phase_complete(self, phase: str, **kw: Any) -> dict:
        return self.event("phase_complete", completed_phase=phase, **kw)

    # -- lifecycle ------------------------------------------------------------
    def close(self) -> Path:
        if not self._fh.closed:
            self._fh.close()
        return self.path

    def __enter__(self) -> "Trajectory":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
