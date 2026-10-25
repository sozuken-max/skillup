# Runbook

## Roll back a bad deploy
Cloud Run keeps earlier revisions. Send all traffic back to the previous one:
```
gcloud run revisions list --service skillup-api-prod --region $REGION
gcloud run services update-traffic skillup-api-prod --region $REGION --to-revisions <REVISION>=100
```
Then revert the PR on `main` so the next deploy doesn't bring it back.

## Restore the database
Neon's free plan keeps 6 hours of history.
- **Within 6 hours:** Neon console → branch → Restore, to a timestamp before the incident.
  Restore to a new branch first, check it, then switch the `DATABASE_URL` secret to it.
- **Older:** restore from the latest export:
  `pg_restore --no-owner -d "$DATABASE_URL" skillup-YYYYMMDD.dump`.
  Until real user data exists, exports are manual:
  `pg_dump -Fc "$DATABASE_URL" -f skillup-$(date +%Y%m%d).dump`. Never commit dumps.

A migration that fails mid-way: run `alembic downgrade -1` against the same database, fix
the migration, and redeploy.

## Rotate a secret
```
printf '%s' "$NEW_VALUE" | gcloud secrets versions add <SECRET> --data-file=-
gcloud run services update skillup-api-prod --region $REGION --update-secrets <ENV>=<SECRET>:latest
gcloud secrets versions destroy <OLD_VERSION> --secret <SECRET>
```
Destroy old versions: only 6 active versions are free. For the OpenAI key, also revoke the old
key on the OpenAI dashboard.

## Unexpected cost
1. Billing → Reports, group by SKU, to see what's billing.
2. Most likely causes: something with min instances > 0, Artifact Registry over 0.5 GB, or an
   LLM loop. Fix the cause; `scripts/check_cost_guardrails.py` should get a rule so it can't
   happen again.
3. Emergency stop: make the service stop accepting public traffic while you investigate:
   `gcloud run services update <svc> --region $REGION --ingress internal`.
   For LLM spend, the OpenAI hard limit already stops calls at $5.

## bq-model
`bq-model/` is a separate live Cloud Run service with its own deploy. Nothing in this repo's
CI/CD deploys it. Don't move or change it without the owner.
