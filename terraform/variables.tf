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

variable "hcloud_token" {
  description = "Hetzner Cloud API token"
  type        = string
  sensitive   = true
}

variable "ssh_public_key_1" {
  description = "SSH public key for VM access (developer 1)"
  type        = string
}

variable "ssh_public_key_2" {
  description = "SSH public key for VM access (developer 2)"
  type        = string
}
