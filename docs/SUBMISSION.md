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

**Baseline + advanced (both required):** baseline = `FloodConfig.baseline()` (naive Otsu); advanced =
verification-gated workflow + live change detection. Compared on the same cases in
[`reports/eval_results.csv`](../reports/eval_results.csv).

**Rulebook compliance:**
- Sandbox / human approval for consequential actions → every map flagged `pending sign-off`; eval bypass is
  logged, never silent.
- Credentials out of the submission → `.env` git-ignored; flood mapping needs no key.
- Public/approved data only → Sen1Floods11 + Planetary Computer, within terms.
- Every claim tied to evidence → CSV / tiles / trajectories.
- Coding-agent use disclosed → [`docs/AGENT_USE.md`](AGENT_USE.md).

**Known scope note (stated plainly):** the analysis workflow is deterministic in this first submission;
the LLM-agent layer is the planned advanced iteration (schema/tooling already in place).

## What still needs the participant
1. **Record the 5-min video** (storyboard ready).
2. **Register + upload** on HackerEarth before **Aug 31, 18:00 UTC**.
3. Optionally `git commit` the working tree and push to a repo the judges can access (nothing is committed
   automatically — review the diff first).
