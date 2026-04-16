# Nightly LangSmith evaluation (T087 — docs only)

This is a **design doc**, not wired into CI. It describes the nightly eval
job that scores the research agent against a hand-curated question set.
Implementation will hook into LangSmith's `evaluate` SDK once the slice is
in self-use and we have real traces to calibrate against. Research.md R-013
calls this out as the evaluation strategy; Phase 6 / T087 captures the
minimum contract.

## Dataset

A fixed set of 10 research questions stored in
`apps/api/tests/evals/datasets/nightly_research_v1.jsonl`. Each row:

```json
{"question": "...", "persona": "solo-founder", "expected_signal": "..."}
```

The set covers:

1. Well-scoped competitive analysis (`US1` happy path).
2. Temporal question needing recent sources.
3. Adjacent-market question.
4. Audience/ICP sizing.
5. Channel effectiveness.
6. Ambiguous question expected to trigger clarification.
7. Out-of-scope question (expected `out_of_scope`).
8. Follow-up on a prior brief (expected `followup_on_existing_brief`).
9. Paywalled-source scenario (expected `accessible == false` surfaced per
   FR-028).
10. Sparse-results scenario (expected `no_findings_above_threshold` per
    FR-027).

## Scoring criteria (per brief)

Every produced `IntelligenceBrief` is scored on:

| Criterion | Threshold | Source |
|---|---|---|
| Zero fabricated sources | `fabricated_count == 0` | anti-hallucination gate registry (research.md R-003) |
| At least 3 findings | `len(findings) >= 3` | SC-001, SC-004 |
| At least 1 high-confidence finding | `any(f.confidence == "high")` | SC-002 |
| Every source URL resolvable | HEAD 2xx/3xx within 5s | FR-018, intelligence-brief.md invariant 4 |
| No empty/generic failure messages | `FailureRecord.user_message` not in generic set | Constitution V |

A run **passes** when all ten questions meet every applicable criterion.
Paywalled and sparse-results scenarios are scored against their expected
failure codes, not brief content.

## Execution contract

The nightly job MUST:

- Use **recorded** LLM completions and Tavily fixtures in CI (cost + flake
  control). Live-API runs are manual, triggered from a developer machine
  with the `RUN_LIVE_EVAL=1` env gate.
- Emit results to a LangSmith project `amplify-nightly-eval` (separate
  from the dev project so regular runs don't pollute eval history).
- Persist a JSON summary at `tests/evals/reports/<date>.json` for later
  diffing.
- Never gate merges. Alerts fire on regression but do not block CI.

## Not yet wired

- No GitHub Actions workflow. Intentional — we need a week of real
  traces before committing to eval thresholds.
- No LangSmith dataset upload script. Tracked for the post-MVP polish
  pass.

Update this file and check off T087 once the dataset and scoring helpers
land in `apps/api/tests/evals/`.
