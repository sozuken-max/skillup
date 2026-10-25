# SkillUp

A career portal backend: match users to jobs based on their CV and goals, identify skill gaps,
and recommend courses to close them. This repo is being rebuilt from scratch; it currently holds
the **foundation** (rules, automation, infrastructure) and no product code yet.

`bq-model/` is a separate live Cloud Run service. Its deploy depends on its path. Leave it alone.

## How we work (10-minute onboarding)

**1. Set up (once)**
```bash
# needs: git, uv (https://docs.astral.sh/uv/), Docker, gh (GitHub CLI), Claude Code
git clone https://github.com/sozuken-max/skillup && cd skillup
uv sync
docker compose up -d db
cp .env.example .env
uv run pytest
```

**2. Understand the rules.** Read [`CLAUDE.md`](CLAUDE.md) (Claude reads it too) and skim the
[ADRs](docs/adr/README.md). That's the whole rulebook.

**3. The flow for any change**
```
idea ──► /new-requirement ──► REQ-NNN.md (draft) ──► owner approves ──► issue assigned to you
     ──► /implement-req REQ-NNN ──► tagged tests first ──► code ──► PR ──► CI + Claude review
     ──► human approval ──► merge ──► staging (auto) ──► prod (owner approves)
```
- **Requirements** are Markdown files with numbered, testable acceptance criteria
  ([how](docs/requirements/README.md)). Tests and evals point back to them with
  `@pytest.mark.req("REQ-007.AC-3")`, and CI fails if an approved criterion isn't covered by a
  passing test.
- **The issue assignee holds the lock.** Don't work on an issue assigned to someone else.
- **Handoffs are issue comments** (Done / Next / Open questions / Blockers), posted at the end of
  every session, so the next person or Claude session can pick up.

**4. What CI checks on every PR:** formatting, lint, types, tests, 80% coverage on changed lines,
requirement traceability, cost guardrails, dependency vulnerabilities, and that `bq-model/` is
untouched. Claude reviews the PR once when it's ready for review. Evals (real LLM calls) run only
with the `run-evals` label.

**5. Cost.** Everything runs free at idle ([ADR-0007](docs/adr/0007-free-at-idle.md),
[cost register](docs/cost.md)). LLM spend is hard-capped at $5/month.

## Layout
```
CLAUDE.md            rules for every session
.claude/             shared Claude Code settings, hooks, skills, reviewer agent
.github/             CI/CD workflows, PR and issue templates, CODEOWNERS
docs/                requirements, ADRs, cost register, runbook
app/                 the FastAPI app (empty until the first requirement)
tests/               pytest
evals/               LLM eval harness
infra/               Terraform for Google Cloud (see infra/README.md)
scripts/             CI checks
bq-model/            live BigQuery query service (separate deploy, do not touch)
```

## One-time setup still needed (owner)
- Google Cloud: follow [`infra/README.md`](infra/README.md) (state bucket, `terraform apply`,
  secret values, GitHub Actions variables). Create the free Neon project.
- GitHub → Settings:
  - Branch ruleset on `main`: require PRs, 1 approval, code owner review, and the `checks` and
    `infra` status checks; block force pushes.
  - Environments: `staging`, and `prod` with you as required reviewer.
  - Secrets: `CLAUDE_CODE_OAUTH_TOKEN` (from `claude setup-token`) and `OPENAI_API_KEY`.
  - Labels: `run-evals`, `claude-review`, `bq-model-change`, `work-item`.
  - Install the Claude GitHub App (`/install-github-app` in Claude Code).
- OpenAI: set a $5 hard monthly limit and a $3 alert on the project.
