# ADR-0006: LLM usage rules

- **Status:** Proposed
- **Date:** 2026-10-25
- **Deciders:** @sozuken-max

## Context
CV parsing, skill-gap explanations and matching use LLMs. They are the only part of the system
that costs money per call, CV text is untrusted input that can contain prompt injection, and
model changes can silently change quality.

## Decision
- **Provider: OpenAI API.** By default OpenAI does not train on API data. A **hard monthly
  spend limit of $5** is set on the OpenAI project (Settings -> Limits), plus an alert at $3.
- **Pinned models.** Use the cheapest model that passes the evals, referenced by a dated
  snapshot ID in config, never an alias that can change underneath us.
- **Embeddings run locally** in the container (e.g. fastembed/ONNX, as `bq-model` does), so
  matching costs nothing per call.
- **One client wrapper** for all LLM calls: sets max tokens, records model, tokens, latency and
  estimated cost on a trace span, and enforces a per-user rate limit.
- **CV text is untrusted data.** It goes into prompts only inside clearly delimited data
  sections, never as instructions. Outputs are parsed into Pydantic schemas, never executed or
  trusted as commands. Eval suites that read CVs include adversarial cases.
- **Prompts are files** in `app/prompts/`, versioned with the code, so evals detect changes.
- **Tests never call a live model** (recorded responses only). Evals do, and run only on the
  `run-evals` PR label or a manual dispatch.

## Consequences
- LLM spend is capped at $5/month; features fail closed (clear error) when the cap is hit.
- Switching provider later means changing the wrapper and re-running evals, nothing else.

## Alternatives considered
- **Free tiers of other providers:** some allow training on inputs, which conflicts with
  ADR-0005 for real CVs. Acceptable only for synthetic development data.
- **Self-hosted open models:** no per-call cost, but needs a GPU or an always-on instance.
