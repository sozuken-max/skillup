# app/

One FastAPI app, organised as modules (ADR-0002). Empty until the first requirement lands.

- Layout: `app/main.py` (app factory, `/healthz`, `/readyz`), `app/core/` (config, logging,
  db, errors), `app/modules/<domain>/` (`api.py`, `service.py`, `models.py`, `schemas.py`).
- Modules talk to each other only through `service.py`; never import another module's models.
- Config comes from environment variables via one settings object; secrets from Secret Manager.
- Prompts live in `app/prompts/` as files, not inline strings, so evals can track them.
- Every LLM call goes through one client wrapper that pins the model ID, records tokens and cost
  as a trace span, and treats CV text as untrusted data (ADR-0006).
- Logs carry IDs, never CV text, names, emails or other personal data (ADR-0005).
- When you add the first code here, also add `app` to `[tool.pyright].include` and
  `[tool.coverage.run].source` in pyproject.toml.
