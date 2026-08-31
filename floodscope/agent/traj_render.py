"""Render an NDJSON trajectory into a human-readable Markdown transcript.

The raw NDJSON is what a judge replays; this Markdown is what a judge *reads*.
Same events, formatted as a clean walk-through from the agent's instructions to
the final result, so a reviewer can follow the reasoning, the tool responses,
the verification, any retries, and the human checkpoint at a glance.

    python -m floodscope.agent.traj_render trajectories/baseline-oneshot/Spain_6860600.ndjson
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _read(ndjson_path: Path) -> list[dict]:
    events = []
    with ndjson_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def _fence(text: str, lang: str = "") -> str:
    return f"```{lang}\n{text.rstrip()}\n```"


def _render_event(e: dict) -> str:
    t = e["event_type"]
    phase = e.get("phase")
    tag = f"`{phase}` · " if phase else ""

    if t == "system_prompt":
        return f"### {tag}System prompt\n{_fence(e['text'])}"
    if t == "user_prompt":
        return f"### {tag}User prompt\n{_fence(e['text'])}"
    if t == "assistant_text":
        return f"**Agent:**\n\n{e['text']}"
    if t == "code_emitted":
        return f"**Agent wrote code:**\n{_fence(e['code'], e.get('language', 'python'))}"
    if t == "tool_call":
        args = json.dumps(e.get("args", {}), ensure_ascii=False)
        return f"**→ tool call** `{e['name']}({args})`"
    if t == "tool_result":
        mark = "✓" if e.get("ok", True) else "✗"
        return f"**← tool result** {mark} `{e['name']}`: {e['summary']}"
    if t == "code_stdout":
        mark = "✓" if e.get("ok", True) else "✗ (error)"
        return f"**← execution** {mark}\n{_fence(e['stdout'])}"
    if t == "verification":
        mark = "✅ passed" if e["passed"] else "❌ failed"
        checks = json.dumps(e["checks"], ensure_ascii=False, indent=2)
        return f"**Verification {mark}**\n{_fence(checks, 'json')}"
    if t == "retry":
        return f"**↻ retry #{e['attempt']}** — {e['reason']}"
    if t == "human_review":
        note = f" — {e['note']}" if e.get("note") else ""
        return f"**🧑‍⚖️ human review: {e['decision']}**{note}"
    if t == "checkpoint":
        data = json.dumps(e["data"], ensure_ascii=False, indent=2)
        return f"**Checkpoint**\n{_fence(data, 'json')}"
    if t == "usage":
        return (
            f"**Usage** — in {e['input_tokens']} tok · out {e['output_tokens']} tok · "
            f"${e['cost_usd']:.4f}"
        )
    if t == "phase_complete":
        return f"_— {e['completed_phase']} complete —_"
    # Fallback: dump unknown event compactly.
    return _fence(json.dumps(e, ensure_ascii=False), "json")


def render_markdown(ndjson_path: str | Path, out_path: str | Path | None = None) -> Path:
    """Render `ndjson_path` to Markdown. Returns the written .md path."""
    ndjson_path = Path(ndjson_path)
    events = _read(ndjson_path)
    if not events:
        raise ValueError(f"no events in {ndjson_path}")

    head = events[0]
    lines = [
        f"# Trajectory — {head.get('agent', '?')} — {head.get('case', '?')}",
        "",
        f"- **workflow_id:** `{head.get('workflow_id', '?')}`",
        f"- **events:** {len(events)}",
        "",
        "---",
        "",
    ]
    for e in events:
        lines.append(_render_event(e))
        lines.append("")

    out_path = Path(out_path) if out_path else ndjson_path.with_suffix(".md")
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: python -m floodscope.agent.traj_render <trajectory.ndjson> [out.md]")
        raise SystemExit(2)
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else None
    out = render_markdown(src, dst)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
