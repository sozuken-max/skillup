# ADR-0004: Authentication with Firebase Auth / Identity Platform

- **Status:** Proposed
- **Date:** 2026-10-25
- **Deciders:** @sozuken-max

## Context
Users sign in to manage their CVs and career goals. Building password storage, resets and social
login ourselves is risky and slow. The existing SkillUp frontend already uses a Firebase project
(`skillup-3fc42`).

## Decision
Use **Firebase Authentication** (upgradeable to Identity Platform) for sign-in. The frontend gets
an ID token; the backend verifies it on every request and maps the Firebase UID to an internal
user ID. No passwords are stored by the backend. Built with the first user-facing requirement.

## Consequences
- Free for email and social sign-in at our scale; SMS sign-in costs money and is not used.
- Vendor lock-in on identity is limited to the UID mapping table.

## Alternatives considered
- **Own auth (FastAPI + password hashing):** more code, more risk, no benefit.
- **Auth0 / Clerk free tiers:** fine, but another vendor when Firebase is already in use.
