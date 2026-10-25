variable "project_id" {
  description = "Google Cloud project ID."
  type        = string
}

variable "region" {
  description = "Region for Cloud Run, Artifact Registry and secrets. Personal data stays here (ADR-0005)."
  type        = string
  default     = "us-central1"
}

variable "billing_account_id" {
  description = "Billing account ID (XXXXXX-XXXXXX-XXXXXX) for the budget alert."
  type        = string
}

variable "budget_currency" {
  description = "Currency of the billing account."
  type        = string
  default     = "USD"
}

variable "budget_amount" {
  description = "Monthly budget in budget_currency. Alerts fire at 20% (about 1) and 100%."
  type        = number
  default     = 5
}

variable "github_repository" {
  description = "owner/repo allowed to deploy through Workload Identity Federation."
  type        = string
  default     = "sozuken-max/skillup"
}
