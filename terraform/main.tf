# BigQuery datasets

resource "google_bigquery_dataset" "raw" {
  dataset_id = var.raw_dataset_id
  location   = var.region

  description = "Raw ingested data from LTA, SingStat, data.gov.sg (prod)"

  labels = {
    environment = "production"
    pipeline    = "ev-pipeline"
  }
}

resource "google_bigquery_dataset" "prod_staging" {
  dataset_id = var.prod_staging_dataset_id
  location   = var.region

  description = "dbt staging models - cleaned and typed (prod)"

  labels = {
    environment = "production"
    pipeline    = "ev-pipeline"
  }
}

resource "google_bigquery_dataset" "prod_marts" {
  dataset_id = var.prod_marts_dataset_id
  location   = var.region

  description = "dbt mart models - facts and dimensions for Looker Studio (prod)"

  labels = {
    environment = "production"
    pipeline    = "ev-pipeline"
  }
}

# IAM - grant service account access to each dataset
# Uses implicit dependencies to ensure datasets are created before IAM bindings

resource "google_bigquery_dataset_iam_member" "raw_editor" {
  dataset_id = google_bigquery_dataset.raw.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${var.service_account_email}"
}

resource "google_bigquery_dataset_iam_member" "prod_staging_editor" {
  dataset_id = google_bigquery_dataset.prod_staging.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${var.service_account_email}"
}

resource "google_bigquery_dataset_iam_member" "prod_marts_editor" {
  dataset_id = google_bigquery_dataset.prod_marts.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${var.service_account_email}"
}

