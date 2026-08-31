import { useEffect, useState } from "react";
import type { ChipEntry, TrajEvent } from "../types";
import { asset } from "../asset";

const ICONS: Record<string, string> = {
  system_prompt: "⚙️",
  user_prompt: "💬",
  assistant_text: "🤖",
  code_emitted: "🐍",
  tool_call: "→",
  tool_result: "←",
  code_stdout: "▤",
  verification: "🔍",
  retry: "↻",
  human_review: "🧑‍⚖️",
  checkpoint: "📌",
  usage: "💲",
  phase_complete: "✔",
};

function summarize(e: TrajEvent): string {
  switch (e.event_type) {
    case "system_prompt":
    case "user_prompt":
    case "assistant_text":
      return String(e.text ?? "");
    case "code_emitted":
      return String(e.code ?? "");
    case "tool_call":
      return `${e.name}(${JSON.stringify(e.args ?? {})})`;
    case "tool_result":
      return `${e.name}: ${e.summary}`;
    case "code_stdout":
      return String(e.stdout ?? "");
    case "verification":
      return `${e.passed ? "PASSED" : "FAILED"} — ${JSON.stringify(e.checks)}`;
    case "retry":
      return `attempt #${e.attempt} — ${e.reason}`;
    case "human_review":
      return `${e.decision}${e.note ? " — " + e.note : ""}`;
    case "checkpoint":
      return JSON.stringify(e.data);
    case "usage":
      return `in ${e.input_tokens} · out ${e.output_tokens} tok · $${e.cost_usd}`;
    case "phase_complete":
      return `${e.completed_phase} complete`;
    default:
      return JSON.stringify(e);
  }
}

export default function TrajectoryTab({ chip }: { chip: ChipEntry }) {
  const [events, setEvents] = useState<TrajEvent[]>([]);
  const [cursor, setCursor] = useState(0);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setEvents([]);
    setCursor(0);
    setErr(null);
    fetch(asset(chip.trajectory))
      .then((r) => (r.ok ? r.text() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((txt) => {
        if (!alive) return;
        const evs = txt
          .split("\n")
          .filter((l) => l.trim())
          .map((l) => JSON.parse(l) as TrajEvent);
        setEvents(evs);
      })
      .catch((e) => alive && setErr(String(e)));
    return () => {
      alive = false;
    };
  }, [chip.trajectory]);

  if (err) return <div className="traj-empty">No trajectory: {err}</div>;
  if (!events.length) return <div className="traj-empty">Loading trajectory…</div>;

  const agent = events[0].agent;
  return (
    <div className="traj">
      <div className="traj-head">
        <span>
          agent <code>{agent}</code> · {events.length} events
        </span>
        <span className="traj-nav">
          <button onClick={() => setCursor((c) => Math.max(0, c - 1))} disabled={cursor === 0}>
            ‹
          </button>
          {cursor + 1}/{events.length}
          <button
            onClick={() => setCursor((c) => Math.min(events.length - 1, c + 1))}
            disabled={cursor === events.length - 1}
          >
            ›
          </button>
        </span>
      </div>
      <ol className="traj-list">
        {events.map((e, i) => {
          const isCode = e.event_type === "code_emitted" || e.event_type === "code_stdout";
          return (
            <li
              key={e.seq}
              className={`traj-item ${i === cursor ? "active" : ""} ${
                e.event_type === "retry" || (e.event_type === "verification" && !e.passed)
                  ? "warn"
                  : ""
              }`}
              onClick={() => setCursor(i)}
            >
              <span className="traj-icon">{ICONS[e.event_type] ?? "•"}</span>
              <div className="traj-body">
                <div className="traj-type">
                  {e.event_type}
                  {e.phase ? <span className="traj-phase"> · {e.phase}</span> : null}
                </div>
                <div className={`traj-text ${isCode ? "mono" : ""}`}>{summarize(e)}</div>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
