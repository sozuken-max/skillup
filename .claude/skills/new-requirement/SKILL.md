---
name: new-requirement
description: Draft a new requirement file (docs/requirements/REQ-NNN-*.md) from a rough idea or a GitHub issue, with testable acceptance criteria. Use when someone describes a feature, user need or change in behaviour that has no REQ yet.
argument-hint: "[issue number or one-line idea]"
disable-model-invocation: true
---

Draft a requirement for: $ARGUMENTS

1. If the argument is an issue number, read it with `gh issue view <n>`. Otherwise use the text.
2. Read `docs/requirements/README.md` and `docs/requirements/_TEMPLATE.md`. List existing
   `docs/requirements/REQ-*.md` files and check none already covers this. If one does, stop and
   say so: the change belongs in that file.
3. Pick the next free number: highest existing REQ number + 1, zero-padded to 3 digits. Check
   open PRs too (`gh pr list --search "REQ-" --state open`) so two people don't take the same
   number. If someone has, take the next one.
4. Write `docs/requirements/REQ-NNN-<short-slug>.md` from the template with `status: draft`.
5. Acceptance criteria rules (this is the important part):
   - Each criterion is one observable behaviour a test can check: inputs, outputs, status codes,
     limits. Rewrite vague words ("fast", "user-friendly", "secure") into numbers or concrete
     behaviour, and list the rewrites so the human can confirm them.
   - Criteria about LLM output quality are marked `(eval)` and name the measure and threshold.
   - Any criterion touching CVs or profiles states what is stored, for how long, and how it is
     deleted (ADR-0005).
   - Anything not decided goes in "Open questions", not into a guessed criterion.
6. Check it against ADRs in `docs/adr/`. If it needs a new hard-to-reverse decision (new data
   store, external data source, new paid service), add that to "Open questions" and say an ADR
   is needed.
7. Don't write code or tests. Show the file, the vague-to-testable rewrites and open questions,
   and ask the human to review it. It becomes `approved` only when a human says so.
