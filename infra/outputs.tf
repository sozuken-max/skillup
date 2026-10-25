# Copy these into the GitHub repo's Actions variables (Settings -> Secrets and variables -> Actions).

output "GCP_WIF_PROVIDER" {
  value = google_iam_workload_identity_pool_provider.github.name
}

output "GCP_DEPLOY_SA" {
  value = google_service_account.deployer.email
}

output "GCP_RUNTIME_SA" {
  value = google_service_account.runtime.email
}

output "GCP_ARTIFACT_REPO" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.app.repository_id}"
}
