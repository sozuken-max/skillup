# ADR-0003: Postgres with pgvector on Neon

- **Status:** Proposed
- **Date:** 2026-10-25
- **Deciders:** @sozuken-max

## Context
Core features match CVs to jobs and skills to courses, which needs both relational data and
vector similarity search. Cloud SQL has no free tier and bills by the hour even with no traffic,
which breaks the free-at-idle rule (ADR-0007).

## Decision
Use **Neon** serverless Postgres on its free plan, with the **pgvector** extension. One Neon
project with a `main` branch for prod and a `staging` branch. Locally, use the
`pgvector/pgvector` image from `docker-compose.yml`. Schema changes go through Alembic
migrations only; CI runs them against an empty database.

Neon free plan at the time of writing (check before relying on it): 1 GB storage per project,
100 CU-hours of compute per month, scale to zero after 5 minutes idle, 10 branches, 6-hour
restore window, no card required.

## Consequences
- $0 at idle; cold start of a few hundred milliseconds after the database has scaled to zero.
- Standard Postgres, so moving to Cloud SQL later is a dump, restore and connection string change.
- Short restore window: back up anything precious by export (see runbook). Revisit when real
  user data exists.
- Neon is outside Google Cloud: the connection string is a secret in Secret Manager, and Neon's
  region should match the Cloud Run region as closely as possible.

## Alternatives considered
- **Cloud SQL:** best GCP integration, but about $10+/month minimum at zero load.
- **Supabase free:** also Postgres + pgvector, but pauses projects after a week of inactivity.
- **Firestore:** free tier, but weaker for relational queries and joins this product needs.
