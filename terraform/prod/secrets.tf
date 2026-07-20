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

resource "google_secret_manager_secret_iam_member" "env_accessor" {
  secret_id = google_secret_manager_secret.env.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${var.service_account_email}"
}

# Read-only GHCR classic PAT used by the Hetzner VM during deployments. The
# secret payload is added out-of-band so it is never stored in Terraform state.
resource "google_secret_manager_secret" "ghcr_read_token" {
  secret_id = "ghcr-read-token"

  replication {
    auto {}
  }

  depends_on = [google_project_service.secretmanager]
}

resource "google_secret_manager_secret_iam_member" "ghcr_read_token_accessor" {
  secret_id = google_secret_manager_secret.ghcr_read_token.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${var.service_account_email}"
}
