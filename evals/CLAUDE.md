# evals/

Evals measure LLM behaviour that unit tests can't (relevance, extraction quality, robustness).

- One suite = `suites/<name>.py` with `score(case) -> float` (0..1) + `datasets/<name>.jsonl` + a
  threshold in `thresholds.yaml`. Run: `uv run python -m evals.run [suite]`.
- Every case has `"req": "REQ-NNN.AC-n"` when it proves an acceptance criterion.
- Datasets use **synthetic** CVs and profiles only. Never real personal data (ADR-0005).
- Every suite that reads CV text includes adversarial cases (prompt injection inside the CV).
- Evals call the real model and cost money. They run only on the `run-evals` PR label or a
  manual dispatch, and scores are cached by suite + prompt + case hash.
- Never lower a threshold to make a PR pass without saying why in the PR description.
