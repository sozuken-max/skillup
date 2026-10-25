# ADR-0002: One modular app instead of microservices

- **Status:** Proposed
- **Date:** 2026-10-25
- **Deciders:** @sozuken-max

## Context
The product spans profiles/CVs, jobs, skills, courses and matching. With 3-4 people and no
load, separate services would multiply deploys, configs and failure modes without benefit.

## Decision
Build one FastAPI app in `app/`, split into domain modules under `app/modules/<domain>/`.
Modules call each other only through their `service.py`; they never import another module's
models or tables. `bq-model/` stays a separate, independently deployed service.

## Consequences
- One image, one Cloud Run service per environment, one database: cheapest and simplest.
- Clear module boundaries keep a later split possible (e.g. a heavy matching worker).
- Boundaries are enforced by review and the reviewer agent, not by the network.

## Alternatives considered
- **Microservices per domain:** premature; costs more and slows a small team.
- **No module structure:** fast at first, tangled within months.
