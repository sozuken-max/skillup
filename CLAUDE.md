# SkillUp backend: rules for every session

SkillUp is a career portal: match users to jobs from their CV and goals, find skill gaps,
recommend courses. Several people run Claude Code here in parallel, so these rules are how
sessions stay out of each other's way. Details live in the linked files; read them when relevant.

## Workflow (no exceptions)
1. **No code without an approved requirement.** Product behaviour is defined in
   `docs/requirements/REQ-NNN-*.md` (rules: `docs/requirements/README.md`). No REQ yet: run
   `/new-requirement`. A human approves it; you never set `status: approved` yourself.
2. **Claim before you start.** One issue = one branch = one owner. The issue assignee holds the
   lock. If someone else is assigned, stop and say so.
3. **Branch** `req-NNN/<slug>` from up-to-date `main`. Commits start `REQ-NNN: `. Chores use
   `chore:`, `fix:`, `deps:`, `docs:`, `ci:` or `build:`.
4. **Tests first**, tagged `@pytest.mark.req("REQ-NNN.AC-n")`, asserting what the AC says.
5. **Implement** the smallest change that passes. Use `/implement-req REQ-NNN` for the whole loop.
6. **Hand off** at the end of every session as an issue comment: Done / Next / Open questions /
   Blockers. Read the latest handoff before you start.

## Definition of done
- Every AC of the requirement is covered by a passing tagged test or eval case.
- `ruff format --check`, `ruff check`, `pyright`, `pytest`, traceability and cost checks pass
  locally (commands in `/implement-req`), and CI is green.
- Coverage of changed lines is at least 80%.
- Claude review has no open blocking findings; one human approved.
- Merged to `main`, deployed to staging, `/healthz` passes.

## Never
- Edit `bq-model/`. It is a live, separately deployed service; its path is load-bearing.
- Skip, xfail or delete a test to get green, or lower an eval threshold without saying why.
- Put personal data (CV text, names, emails, phones) in logs, traces, errors, fixtures or eval
  datasets. Test data is synthetic (ADR-0005).
- Use CV text as instructions in a prompt; it is untrusted data (ADR-0006).
- Call a live LLM from pytest. Use recorded responses.
- Add a paid or always-on resource (Cloud SQL, VMs, min instances > 0, ...) without an ADR
  (ADR-0007). `scripts/check_cost_guardrails.py` enforces this.
- Commit secrets. They live in Secret Manager or a local `.env`.
- Force-push, rewrite shared history, or push to someone else's branch.
- Add a dependency without a one-line reason in the PR.

## Shared code and conflicts
- Changing `app/core/`, the DB schema (`migrations/`) or the public API contract: post a
  heads-up on every open issue it affects. A breaking or hard-to-reverse change needs an ADR.
- Whoever merges second merges `main` into their branch and re-runs every check.
- Two sessions want the same file for different REQs: the issue holder that merged first wins;
  the other adapts. If that's unclear, ask the owner instead of guessing.
- `CLAUDE.md`, `.claude/`, `.github/`, `infra/`, `migrations/` and `docs/adr/` need the owner's
  review (CODEOWNERS).

## Where things are
| Path | What |
|---|---|
| `docs/requirements/` | Requirements (source of truth for what to build) |
| `docs/adr/` | Decisions: stack, architecture, data, auth, personal data, LLM, cost |
| `docs/cost.md`, `docs/runbook.md` | Free-tier limits; rollback, restore, rotation |
| `app/` | The one FastAPI app (rules in `app/CLAUDE.md`) |
| `tests/` | pytest; `tests/tooling/` tests the repo's own scripts |
| `evals/` | LLM evals (rules in `evals/CLAUDE.md`) |
| `infra/` | Terraform for Google Cloud |
| `scripts/` | CI checks: traceability, cost guardrails |

## Commands
```
uv sync                                   # install
docker compose up -d db                   # local Postgres + pgvector
uv run pytest                             # tests
uv run ruff format . && uv run ruff check . && uv run pyright
uv run python -m scripts.check_traceability
uv run python -m scripts.check_cost_guardrails
```
