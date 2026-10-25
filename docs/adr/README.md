# Architecture decision records

One file per decision that is hard to reverse. Copy [`0000-template.md`](0000-template.md),
take the next number, open a PR. Small, reversible choices don't need an ADR.

| ADR | Decision | Status |
|---|---|---|
| [0001](0001-stack-and-tooling.md) | Python 3.13, FastAPI, uv, ruff, pyright, pytest, Terraform | Proposed |
| [0002](0002-modular-monolith.md) | One modular app instead of microservices | Proposed |
| [0003](0003-database-neon-postgres.md) | Postgres + pgvector on Neon (free plan) | Proposed |
| [0004](0004-auth-identity-platform.md) | Firebase Auth / Identity Platform | Proposed |
| [0005](0005-personal-data-and-cvs.md) | Personal data and CV handling | Proposed |
| [0006](0006-llm-usage.md) | LLM usage: OpenAI, $5 hard cap, pinned models, untrusted CV input | Proposed |
| [0007](0007-free-at-idle.md) | Free at idle: scale-to-zero only, cost guardrails in CI | Proposed |

**Open decisions** (take an ADR when the first requirement needs them):
- Where job and course data come from: job board APIs, partner feeds or scraping (check each
  site's terms first).
- Frontend hosting and how it talks to the API.
