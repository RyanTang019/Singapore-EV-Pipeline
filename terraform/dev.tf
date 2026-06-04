# Dev BigQuery datasets — provisioned in sg-pipeline-dev
# Each developer gets their own datasets prefixed with their handle (DEV_SCHEMA_PREFIX).
# Adding a new developer = add their handle to var.developers.

resource "google_bigquery_dataset" "dev_raw" {
  for_each = toset(var.developers)
  provider = google.dev

  dataset_id  = "dev_${each.key}_raw"
  location    = var.region
  description = "Raw ingestion sandbox — ${each.key}"

  labels = {
    environment = "dev"
    pipeline    = "ev-pipeline"
    developer   = each.key
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
