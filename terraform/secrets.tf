# GCP Secret Manager

resource "google_project_service" "secretmanager" {
  service            = "secretmanager.googleapis.com"
  disable_on_destroy = false
}

resource "google_secret_manager_secret" "env" {
  secret_id = "dagster-env"

  replication {
    auto {}
  }

  depends_on = [google_project_service.secretmanager]
}

# Grant the Dagster service account access to read the secrets
resource "google_secret_manager_secret_iam_member" "env_accessor" {
  secret_id = google_secret_manager_secret.env.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${var.service_account_email}"
}

