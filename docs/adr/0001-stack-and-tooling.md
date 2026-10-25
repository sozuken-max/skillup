# ADR-0001: Backend stack and tooling

- **Status:** Proposed
- **Date:** 2026-10-25
- **Deciders:** @sozuken-max

## Context
SkillUp needs a backend for CV parsing, job and course matching and LLM features. The team is
small (owner + 2-3 developers), mostly coding through Claude Code, and the existing
`bq-model` service is Python. The project must run for free at idle (ADR-0007).

## Decision
- **Python 3.13**, **FastAPI**, **Pydantic v2**, **SQLAlchemy 2** + **Alembic** for the database.
- **uv** for environments, dependencies and the lockfile (`uv.lock`). One project, no workspace.
- **ruff** for formatting and linting, **pyright** (strict) for type checking, **pytest** +
  **pytest-cov** for tests, **diff-cover** for coverage on changed lines, **pip-audit** for
  dependency vulnerabilities.
- **Terraform** for Google Cloud resources (`infra/`), GitHub Actions for CI/CD.
- Runtime dependencies are added with the first requirement that needs them, not up front.

## Consequences
- One language across `bq-model` and the new backend, and the best-supported ecosystem for
  LLM, embedding and data work.
- uv, ruff and pyright are fast enough to run on every edit through Claude Code hooks.
- Python is slower than Go or Node for raw request throughput; irrelevant at this scale.

## Alternatives considered
- **TypeScript (Hono/Fastify):** one language with a JS frontend, but weaker ML/embedding tooling
  and a second language next to `bq-model`.
- **Poetry / pip-tools:** slower and more moving parts than uv.
- **mypy:** fine, but slower than pyright and worse editor integration for strict mode.
