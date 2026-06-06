# ev_charger_availability raw landing table.
# Prod and dev raw datasets live in different GCP projects behind different provider
# aliases, so this is two resources sharing one schema file (the two-provider gotcha).
# No partitioning (deferred); no extra IAM (inherits dataset-level dataEditor grants).

# Prod raw table — default provider (prod project, prod_raw)
resource "google_bigquery_table" "ev_charger_availability" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.raw.dataset_id
  table_id            = "ev_charger_availability"
  schema              = file("${path.module}/schemas/ev_charger_availability.json")
  deletion_protection = false
}

# Dev raw table — google.dev provider (sg-pipeline-dev, shared dev_raw)
resource "google_bigquery_table" "dev_ev_charger_availability" {
  provider            = google.dev
  project             = var.dev_project_id
  dataset_id          = google_bigquery_dataset.dev_raw.dataset_id
  table_id            = "ev_charger_availability"
  schema              = file("${path.module}/schemas/ev_charger_availability.json")
  deletion_protection = false
}
