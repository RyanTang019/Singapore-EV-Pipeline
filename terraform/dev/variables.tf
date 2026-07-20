variable "dev_project_id" {
  description = "GCP project ID (dev)"
  type        = string
}

variable "region" {
  description = "GCP region for BigQuery datasets"
  type        = string
  default     = "asia-southeast1"
}

variable "developers" {
  description = "Developer handles — each gets dev_<handle>_staging and _marts (raw is shared: dev_raw)"
  type        = list(string)
  default     = ["ryan", "oliver"]
}

variable "service_account_email" {
  description = "Email of the Dagster service account (lives in prod project)"
  type        = string
}
