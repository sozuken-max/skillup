# Requirements

Every change to product behaviour starts here. A requirement is one Markdown file,
`REQ-NNN-short-slug.md`, made from [`_TEMPLATE.md`](_TEMPLATE.md) (or with `/new-requirement`).

## Lifecycle
| Status | Meaning | Who sets it |
|---|---|---|
| `draft` | Being written. Code may not be built against it. | Anyone |
| `approved` | Criteria agreed. CI now requires every AC to be covered by a passing test or eval. | The owner (repo owner until delegated) |
| `deprecated` | No longer wanted. Delete its tests; keep the file as history. | The owner |

"Implemented" isn't a status: CI shows it (every AC covered and passing).

## IDs
- `REQ-NNN` is never reused, even after deprecation. `AC-n` within a requirement is never
  renumbered: new criteria go at the end, removed ones are deleted.
- References look like `REQ-007.AC-3`. Tests use `@pytest.mark.req("REQ-007.AC-3")`, eval cases
  use `"req": "REQ-007.AC-3"`.

## What CI enforces (`scripts/check_traceability.py`)
- Every AC of every `approved` requirement has at least one passing test or eval case.
- Every reference in tests and evals points at an AC that exists and isn't deprecated.
- A PR that changes `app/` or `migrations/` names a REQ ID in its title or branch, unless its
  title starts with `chore`, `fix`, `deps`, `docs`, `ci` or `build`.
- When an approved AC's text changes, at least one of its tests changes in the same PR.

The matrix of criteria and tests is in each CI run's summary and in the `reports` artifact.

## Changing a requirement
Edit the file in a PR like any other change. Changing an approved AC needs the requirement
owner's approval and an updated test.

## Requirement vs issue
The REQ file is the source of truth for **what** to build. The GitHub issue is the work ticket:
who holds it (assignee = lock), discussion and handoffs. The issue links to the REQ; it does
not copy the criteria.
