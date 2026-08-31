# Submission package — checklist

micro1 Frontier Engineering Challenge 2026 · **first submission** (revisions allowed until the deadline).

| # | Required deliverable | Where it is | Status |
|---|---|---|---|
| 1 | **Complete solution code + Improvement Changelog** | whole repo; changelog in [`README.md` §5](../README.md) | ✅ |
| 1a | README: intended user, bottleneck, why valuable | [`README.md` §1](../README.md) | ✅ |
| 1b | Instructions that shape each agent | [`docs/AGENT_USE.md`](AGENT_USE.md), `floodscope/agent/` | ✅ |
| 1c | Main failure mode + hot take | [`README.md` §10](../README.md) | ✅ |
| 2 | **Reproduction guide** (clean env, commands, data, output, versions, runtime, cost) | [`docs/REPRODUCE.md`](REPRODUCE.md) | ✅ |
| 3 | **Solution video (≤5 min)** | storyboard in [`docs/VIDEO_SCRIPT.md`](VIDEO_SCRIPT.md) — **participant records this** | ⏺ to record |
| 4 | **Agent trajectories** (every agent, instructions→result, tool responses, retries, human checkpoints) | `trajectories/` + [`docs/AGENT_USE.md`](AGENT_USE.md) | ✅ |

**Baseline + advanced (both required):** baseline = `FloodConfig.baseline()` (naive one-shot Otsu);
advanced = an **LLM agent** (`floodscope/agent/flood_agent.py`) that chooses the verification-gated method
per scene, plus the **orchestrator** (`floodscope/agent/orchestrator.py`) that runs acquire→analyse→**write
report**→publish end-to-end. Compared on the same cases in [`reports/eval_results.csv`](../reports/eval_results.csv);
agent evidence in `trajectories/flood-agent/` and `trajectories/flood-orchestrator/`.

**Rulebook compliance:**
- Sandbox / human approval for consequential actions → every map flagged `pending sign-off`; eval bypass is
  logged, never silent.
- Credentials out of the submission → `.env` git-ignored; flood mapping needs no key.
- Public/approved data only → Sen1Floods11 + Planetary Computer, within terms.
- Every claim tied to evidence → CSV / tiles / trajectories.
- Coding-agent use disclosed → [`docs/AGENT_USE.md`](AGENT_USE.md).

**Two tiers (stated plainly):** deterministic pipeline (reproducible, **no key**) for the benchmark + live
demos; LLM agents (`flood_agent.py` per-scene; `orchestrator.py` end-to-end) that decide, verify, retry,
write the report, and publish behind a human checkpoint — run with your own `ANTHROPIC_API_KEY` or
`OPENAI_API_KEY`. Both verified live on GPT-4o.

**Repo:** pushed to **https://github.com/harsh52/floodscope** (`main`). Currently **PRIVATE**.

## What still needs the participant
1. **Make the repo accessible to judges** — flip `harsh52/floodscope` to **public**, or add the judges /
   `yeison@micro1.ai` as collaborators. *(Qualification gate — a judge must be able to clone + run it.)*
2. **Record the 5-min video** (storyboard in `VIDEO_SCRIPT.md`).
3. **Register + upload** on HackerEarth before **Aug 31, 18:00 UTC** (Video + source + traces).
4. **Rotate any keys** used locally — the repo `.env` (git-ignored) is not part of the submission.
