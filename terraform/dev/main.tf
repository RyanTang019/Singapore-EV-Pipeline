# Dev BigQuery datasets — provisioned in sg-pipeline-dev
# Raw is a single SHARED landing zone; staging/marts are per-developer (DEV_SCHEMA_PREFIX).
# Adding a new developer = add their handle to var.developers (gets staging + marts).

resource "google_bigquery_dataset" "dev_raw" {
  dataset_id  = "dev_raw"
  location    = var.region
  description = "Shared dev raw landing zone — all developers ingest here"

  labels = {
    environment = "dev"
    pipeline    = "ev-pipeline"
    shared      = "true"
  }
}

resource "google_bigquery_dataset" "dev_staging" {
  for_each = toset(var.developers)

  dataset_id  = "dev_${each.key}_staging"
  location    = var.region
  description = "dbt staging models — ${each.key} (dev)"

  labels = {
    environment = "dev"
    pipeline    = "ev-pipeline"
    developer   = each.key
  }
}

resource "google_bigquery_dataset" "dev_marts" {
  for_each = toset(var.developers)

  dataset_id  = "dev_${each.key}_marts"
  location    = var.region
  description = "dbt mart models — ${each.key} (dev)"

  labels = {
    environment = "dev"
    pipeline    = "ev-pipeline"
    developer   = each.key
  }
}

# Grant the Dagster SA project-level dataEditor on dev.
# Dev is a sandbox with no sensitive data — project-level avoids per-dataset
# bindings every time a new developer is added.
resource "google_project_iam_member" "dev_bq_editor" {
  project = var.dev_project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${var.service_account_email}"
}
