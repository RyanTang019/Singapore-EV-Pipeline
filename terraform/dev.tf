# Dev BigQuery datasets — provisioned in sg-pipeline-dev
# Raw is a single SHARED landing zone; staging/marts are per-developer (DEV_SCHEMA_PREFIX).
# Adding a new developer = add their handle to var.developers (gets staging + marts).

# Shared dev raw landing zone — ALL developers ingest here (replaces per-dev raw).
# Both dev_<handle>_staging layers read from this single dataset.
resource "google_bigquery_dataset" "dev_raw" {
  provider = google.dev

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
  provider = google.dev

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
  provider = google.dev

  dataset_id  = "dev_${each.key}_marts"
  location    = var.region
  description = "dbt mart models — ${each.key} (dev)"

  labels = {
    environment = "dev"
    pipeline    = "ev-pipeline"
    developer   = each.key
  }
}

# Grant the SA project-level dataEditor on the dev project.
# Dev is a sandbox with no sensitive data — project-level is acceptable here
# and avoids per-dataset bindings every time a new developer is added.
resource "google_project_iam_member" "dev_bq_editor" {
  provider = google.dev
  project  = var.dev_project_id
  role     = "roles/bigquery.dataEditor"
  member   = "serviceAccount:${var.service_account_email}"
}
