# ADR-0005: Handling personal data and CVs

- **Status:** Proposed
- **Date:** 2026-10-25
- **Deciders:** @sozuken-max

## Context
CVs contain names, contact details, work history and sometimes sensitive data. Depending on
where users are, GDPR (EU) or the PDPA (Thailand) applies. Retrofitting deletion and logging
rules later is a rewrite.

## Decision
- **Store only what a requirement needs.** Every requirement touching personal data fills in
  its "Personal data" section: what, where, how long, how deleted.
- **One region** for stored personal data (the Cloud Run region and the matching Neon region).
- **Account deletion** removes the user's CVs, derived data (embeddings, extracted skills) and
  profile. It is built with the first requirement that stores a CV.
- **Uploaded CV files** are kept only as long as a requirement says; extracted text is the
  default store.
- **Logs, traces and errors carry IDs only**, never CV text, names, emails or phone numbers.
- **Test fixtures and eval datasets use synthetic CVs only.**
- **LLM provider:** CV text only goes to providers whose terms exclude training on API data
  (see ADR-0006).

## Consequences
- Slightly more work per feature; much less risk and no retrofit.
- Debugging is harder without content in logs; use IDs and reproduce with synthetic data.

## Alternatives considered
- **Decide later:** cheapest now, most expensive later.
