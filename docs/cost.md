# Cost register

Every resource the project uses, its free limit and how we stay inside it (ADR-0007).
Free limits change; re-check them when adding a row. Last checked: 2026-10-25.

| Resource | Free limit | How we stay inside it | Alert |
|---|---|---|---|
| Cloud Run (staging + prod) | 2M requests, 180,000 vCPU-s, 360,000 GiB-s per month; 1 GB egress from North America | `--min-instances=0`, request-based billing, `--max-instances` ≤ 3 | Billing budget |
| Artifact Registry | 0.5 GB storage | Cleanup policy keeps the 5 newest images and deletes untagged ones after 7 days | Billing budget |
| Secret Manager | 6 active secret versions, 10,000 accesses per month | About 3 secrets; destroy old versions after rotating | Billing budget |
| Cloud Storage (Terraform state) | 5 GB-months in `us-east1`, `us-west1`, `us-central1` | State bucket in `us-central1`, a few KB | Billing budget |
| Cloud Logging | 50 GiB per project per month | Structured logs, INFO level in prod | Billing budget |
| Cloud Trace | Free monthly span allowance (check the Trace pricing page) | Sample about 10% of requests in prod | Billing budget |
| Firebase Auth | Free for email and social sign-in at our scale | No SMS sign-in | Billing budget |
| Neon Postgres | 1 GB storage, 100 CU-hours per month, scale to zero | One project, `main` and `staging` branches | Neon usage emails |
| OpenAI API | Not free | Hard monthly spend limit of **$5** on the project | OpenAI alert at $3 |
| GitHub Actions | Free and unlimited minutes on a public repo | Repo stays public | n/a |
| Claude PR review | Uses the owner's Claude subscription (OAuth token) | Runs once per PR (when ready for review), or by label | n/a |
| Billing budget | Free | Email alerts at $1 and $5 | — |

A budget only sends alerts; it doesn't stop spending. If an alert fires, check
Billing → Reports and follow the runbook's "Unexpected cost" section.
