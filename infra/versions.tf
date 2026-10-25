terraform {
  required_version = ">= 1.14"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.8"
    }
  }

  # Bucket is created once by hand (see README.md) and passed with
  # terraform init -backend-config="bucket=<project>-tfstate".
  backend "gcs" {
    prefix = "skillup"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
  # Budgets API needs a quota project when called with user credentials.
  user_project_override = true
  billing_project       = var.project_id
}
