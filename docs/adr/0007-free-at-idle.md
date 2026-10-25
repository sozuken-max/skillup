# ADR-0007: Free at idle

- **Status:** Proposed
- **Date:** 2026-10-25
- **Deciders:** @sozuken-max

## Context
This is a student project that should look and work like an enterprise system but must cost
$0 with no traffic. Cloud bills usually come from resources that run whether or not anyone
uses them.

## Decision
- Only services with scale-to-zero or a free tier: Cloud Run (`--min-instances=0`,
  request-based billing), Artifact Registry (with cleanup policy), Secret Manager (few secrets),
  Cloud Storage in a free US region (Terraform state only), Cloud Logging and Trace (sampled),
  Firebase Auth, Neon free plan, GitHub Actions on a public repo.
- **No always-on resources** (Cloud SQL, VMs, GKE, Memorystore, load balancers, NAT, VPC
  connectors) without a new ADR. `scripts/check_cost_guardrails.py` fails CI if they appear.
- Cloud Run `--max-instances` is at most 3, which also caps runaway cost under abuse.
- A **billing budget** with email alerts at $1 and $5 (budgets alert; they don't stop spend).
- LLM spend is capped separately at $5/month (ADR-0006).
- [`docs/cost.md`](../cost.md) lists every resource, its free limit and its alert.

## Consequences
- Cold starts of a few seconds on the first request after idle.
- Some enterprise patterns (private networking, always-warm instances, managed SQL) are out
  until there's a reason and a budget.

## Alternatives considered
- **Use GCP's $300 trial credit:** it expires; the project would start costing money later.
