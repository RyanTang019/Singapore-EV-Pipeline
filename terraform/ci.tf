# GitHub Actions runs dbt unit tests keylessly against isolated, per-run datasets
# in the dev project. The federated identity can create BigQuery datasets, but it
# cannot read or modify dev_raw, developer schemas, or any production resource.

locals {
  github_repository    = "RyanTang019/Singapore-EV-Pipeline"
  github_repository_id = "1241332044"
  github_ci_workflow   = "RyanTang019/Singapore-EV-Pipeline/.github/workflows/ci.yml@"
}

resource "google_project_service" "dev_ci_apis" {
  for_each = toset([
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "sts.googleapis.com",
  ])

  provider           = google.dev
  project            = var.dev_project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_service_account" "ci" {
  provider     = google.dev
  project      = var.dev_project_id
  account_id   = "sgev-ci"
  display_name = "GitHub Actions CI (dbt unit tests)"

  depends_on = [google_project_service.dev_ci_apis]
}

# BigQuery User can run jobs and create datasets. A dataset creator becomes the
# owner of only that new dataset, which lets dbt build and delete ci_* schemas
# without granting CI access to existing dev or production data.
resource "google_project_iam_member" "ci_bq_user" {
  provider = google.dev
  project  = var.dev_project_id
  role     = "roles/bigquery.user"
  member   = "serviceAccount:${google_service_account.ci.email}"
}

resource "google_iam_workload_identity_pool" "github_ci" {
  provider                  = google.dev
  project                   = var.dev_project_id
  workload_identity_pool_id = "github-ci"
  display_name              = "GitHub Actions CI"

  depends_on = [google_project_service.dev_ci_apis]
}

resource "google_iam_workload_identity_pool_provider" "github_ci" {
  provider                           = google.dev
  project                            = var.dev_project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github_ci.workload_identity_pool_id
  workload_identity_pool_provider_id = "github"
  display_name                       = "GitHub OIDC"

  attribute_mapping = {
    "google.subject"          = "assertion.sub"
    "attribute.repository"    = "assertion.repository"
    "attribute.repository_id" = "assertion.repository_id"
    "attribute.workflow_ref"  = "assertion.workflow_ref"
  }

  # Bind trust to the immutable repository ID and this workflow path. Keeping
  # the human-readable repository check makes accidental configuration drift
  # visible while the numeric ID prevents rename/name-reuse attacks.
  attribute_condition = <<-EOT
    assertion.repository_id == '${local.github_repository_id}' &&
    assertion.repository == '${local.github_repository}' &&
    assertion.workflow_ref.startsWith('${local.github_ci_workflow}')
  EOT

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account_iam_member" "ci_wif" {
  provider           = google.dev
  service_account_id = google_service_account.ci.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github_ci.name}/attribute.repository_id/${local.github_repository_id}"
}

output "ci_service_account_email" {
  description = "Service account impersonated by GitHub Actions for dbt unit tests"
  value       = google_service_account.ci.email
}

output "ci_workload_identity_provider" {
  description = "Full WIF provider resource name for google-github-actions/auth"
  value       = google_iam_workload_identity_pool_provider.github_ci.name
}
