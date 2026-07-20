variable "project_id" {
  description = "GCP project ID (production)"
  type        = string
}

variable "dev_project_id" {
  description = "GCP project ID (dev) — needed for cross-project IAM grants from prod identity resources"
  type        = string
}

variable "region" {
  description = "GCP region for BigQuery datasets"
  type        = string
  default     = "asia-southeast1"
}

variable "raw_dataset_id" {
  description = "BigQuery dataset for raw ingested data (prod)"
  type        = string
  default     = "prod_raw"
}

variable "prod_staging_dataset_id" {
  description = "BigQuery dataset for dbt staging models (prod target)"
  type        = string
  default     = "prod_staging"
}

variable "prod_marts_dataset_id" {
  description = "BigQuery dataset for dbt mart models (prod target)"
  type        = string
  default     = "prod_marts"
}

variable "prod_intermediate_dataset_id" {
  description = "BigQuery dataset for dbt intermediate models (prod target)"
  type        = string
  default     = "prod_intermediate"
}

variable "prod_seed_dataset_id" {
  description = "BigQuery dataset for dbt seeds (prod target)"
  type        = string
  default     = "prod_seed"
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

variable "deploy_ssh_public_key" {
  description = "SSH public key for CI/CD deploy (GitHub Actions, forced-command restricted)"
  type        = string
}
