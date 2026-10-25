---
name: implement-req
description: Implement an approved requirement end to end - claim it, branch, write tagged tests first, implement, run every check, open a PR and post a handoff. Use when asked to build, implement or continue work on a REQ-NNN.
argument-hint: "REQ-NNN"
disable-model-invocation: true
---

Implement $ARGUMENTS. Follow CLAUDE.md throughout.

## 1. Check it's yours to do
- Read `docs/requirements/$ARGUMENTS-*.md`. Stop if `status` is not `approved`.
- Find its issue (front matter `issue:`) with `gh issue view`. Read every comment, especially
  the latest handoff.
- If the issue is assigned to someone other than the current user (`gh api user -q .login`),
  stop and say who holds it. Don't work around the lock.
- If it's unassigned, ask the human before assigning it to them
  (`gh issue edit <n> --add-assignee @me`).

## 2. Branch
- Branch `req-NNN/<slug>` from up-to-date `main`, or continue that branch if it exists.

## 3. Tests first
- For every AC, write tests that fail now and mark them `@pytest.mark.req("REQ-NNN.AC-n")`.
  The test must assert what the AC actually says, not just that something runs.
- `(eval)` criteria get cases in `evals/datasets/<suite>.jsonl` with `"req"`, plus a threshold.
- Integration tests use the local Postgres from `docker compose up -d db`. Never call a live LLM
  from pytest; use recorded responses.
- Run the tests and confirm they fail for the right reason.

## 4. Implement
- Smallest change that makes the tests pass, following `app/CLAUDE.md`.
- New dependency: say why in the PR description. New paid or always-on service: stop, it needs
  an ADR (ADR-0007).
- Changes to `app/core/`, the DB schema or the public API contract: post a heads-up comment on
  the other open REQ issues they affect.

## 5. Verify (all must pass)
```
uv run ruff format --check . && uv run ruff check .
uv run pyright
uv run pytest --cov --cov-report=xml
uv run python -m scripts.check_traceability --results reports/req-results.json --base origin/main --branch "$(git branch --show-current)"
uv run python -m scripts.check_cost_guardrails
```
Fix failures. Never skip, xfail or delete a test to get green.

## 6. Hand off
- Commit with messages starting `REQ-NNN: `. Ask before pushing, then open a PR with the template
  filled in. It's a draft until every AC box is ticked.
- Post a handoff comment on the issue, even if the work is unfinished:
  ```
  ## Handoff - <date>
  **Done:** ...
  **Next:** ...
  **Open questions:** ...
  **Blockers:** ...
  ```
