# infra/

Terraform for the Google Cloud side of SkillUp. Everything here is free at idle (ADR-0007),
and CI checks that with `scripts/check_cost_guardrails.py`. Changes need the owner's review.

What it creates: required APIs, an Artifact Registry repo with cleanup policies, runtime and
deployer service accounts, Workload Identity Federation for GitHub Actions (only `main` of this
repo), three empty secrets and a billing budget alert. Cloud Run services are created by the
deploy workflow on first deploy.

## One-time bootstrap (owner)
Needs `gcloud`, Terraform ≥ 1.14 and Owner on the project plus Billing Account Administrator
(or Costs Manager) on the billing account.

```bash
PROJECT=skillup-3fc42          # confirm the project ID
gcloud auth application-default login
gcloud config set project $PROJECT

# 1. State bucket (us-central1 is inside the Cloud Storage free tier)
gcloud storage buckets create gs://$PROJECT-tfstate --location us-central1 \
  --uniform-bucket-level-access --public-access-prevention
gcloud storage buckets update gs://$PROJECT-tfstate --versioning

# 2. Apply
cp terraform.tfvars.example terraform.tfvars   # fill in billing_account_id
terraform init -backend-config="bucket=$PROJECT-tfstate"
terraform apply

# 3. Secret values (one version each; old versions count against the free 6)
printf '%s' 'postgresql://...neon.tech/skillup?sslmode=require' | \
  gcloud secrets versions add database-url-staging --data-file=-
printf '%s' 'postgresql://...neon.tech/skillup?sslmode=require' | \
  gcloud secrets versions add database-url-prod --data-file=-
printf '%s' "$OPENAI_API_KEY" | gcloud secrets versions add openai-api-key --data-file=-
```

4. Copy `terraform output` values into GitHub → Settings → Secrets and variables → Actions →
   **Variables**: `GCP_PROJECT_ID`, `GCP_REGION`, `GCP_WIF_PROVIDER`, `GCP_DEPLOY_SA`,
   `GCP_RUNTIME_SA`, `GCP_ARTIFACT_REPO`. These are identifiers, not secrets.

## Neon (outside Terraform)
Create a free Neon project in the region closest to `region`, enable `pgvector`
(`CREATE EXTENSION vector;`), and create a `staging` branch next to `main`. Their connection
strings go into the two `database-url-*` secrets above.
