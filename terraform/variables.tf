variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region for BigQuery datasets"
  type        = string
  default     = "asia-southeast1"
}

variable "raw_dataset_id" {
  description = "BigQuery dataset for raw ingested data"
  type        = string
  default     = "raw"
}

variable "staging_dataset_id" {
  description = "BigQuery dataset for dbt staging models"
  type        = string
  default     = "staging"
}

variable "marts_dataset_id" {
  description = "BigQuery dataset for dbt mart models"
  type        = string
  default     = "marts"
}

variable "service_account_email" {
  description = "Email of the Dagster service account"
  type        = string
}