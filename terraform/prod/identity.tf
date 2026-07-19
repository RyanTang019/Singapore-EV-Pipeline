# Identity infrastructure — WIF pool, service accounts, cross-project IAM.
# Lives in prod (authoritative project) so dev project can be nuked without
# affecting CI or prod deployments.

locals {
  github_repository    = "RyanTang019/Singapore-EV-Pipeline"
  github_repository_id = "1241332044"
}

# Enable required APIs in prod project
resource "google_project_service" "identity_apis" {
  for_each = toset([
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "sts.googleapis.com",
  ])

  service            = each.value
  disable_on_destroy = false
}

# --- WIF pool (single pool, two providers scoped by workflow) ---

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github"
  display_name              = "GitHub Actions"

  depends_on = [google_project_service.identity_apis]
}

# Provider scoped to ci.yml — used by sgev-ci for dbt unit tests
resource "google_iam_workload_identity_pool_provider" "github_ci" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-ci"
  display_name                       = "GitHub Actions CI"

  attribute_mapping = {
    "google.subject"          = "assertion.sub"
    "attribute.repository"    = "assertion.repository"
    "attribute.repository_id" = "assertion.repository_id"
    "attribute.workflow_ref"  = "assertion.workflow_ref"
  }

  attribute_condition = <<-EOT
    assertion.repository_id == '${local.github_repository_id}' &&
    assertion.repository == '${local.github_repository}' &&
    assertion.workflow_ref.startsWith('${local.github_repository}/.github/workflows/ci.yml@')
  EOT

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# Provider scoped to terraform.yml — used by sgev-terraform for prod apply
resource "google_iam_workload_identity_pool_provider" "github_terraform" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-terraform"
  display_name                       = "GitHub Actions Terraform"

  attribute_mapping = {
    "google.subject"          = "assertion.sub"
    "attribute.repository"    = "assertion.repository"
    "attribute.repository_id" = "assertion.repository_id"
    "attribute.workflow_ref"  = "assertion.workflow_ref"
  }

  attribute_condition = <<-EOT
    assertion.repository_id == '${local.github_repository_id}' &&
    assertion.repository == '${local.github_repository}' &&
    assertion.workflow_ref.startsWith('${local.github_repository}/.github/workflows/terraform.yml@')
  EOT

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# --- sgev-ci: runs dbt unit tests in dev project ---

resource "google_service_account" "ci" {
  account_id   = "sgev-ci"
  display_name = "GitHub Actions CI (dbt unit tests)"

  depends_on = [google_project_service.identity_apis]
}

# Allow any identity authenticated through this pool to impersonate sgev-ci.
# Workflow scoping is enforced at the provider layer — github-ci provider only
# accepts tokens from ci.yml via attribute_condition, so this binding is
# effectively ci.yml-only without needing workflow_ref encoding in the member URL.
resource "google_service_account_iam_member" "ci_wif" {
  service_account_id = google_service_account.ci.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository_id/${local.github_repository_id}"
}

# Cross-project: sgev-ci gets bigquery.user on dev project.
# Dataset creator becomes owner of only that new dataset — lets dbt build and
# delete ci_* schemas without touching existing dev or prod data.
resource "google_project_iam_member" "ci_bq_user_dev" {
  project = var.dev_project_id
  role    = "roles/bigquery.user"
  member  = "serviceAccount:${google_service_account.ci.email}"
}

# --- sgev-terraform: applies prod infrastructure from CI ---

resource "google_service_account" "terraform" {
  account_id   = "sgev-terraform"
  display_name = "GitHub Actions Terraform (prod apply)"

  depends_on = [google_project_service.identity_apis]
}

# Allow any identity authenticated through this pool to impersonate sgev-terraform.
# Workflow scoping is enforced at the provider layer — github-terraform provider
# only accepts tokens from terraform.yml via attribute_condition, preventing
# ci.yml from escalating to sgev-terraform's admin privileges.
resource "google_service_account_iam_member" "terraform_wif" {
  service_account_id = google_service_account.terraform.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository_id/${local.github_repository_id}"
}

# Roles on prod project
resource "google_project_iam_member" "terraform_prod_roles" {
  for_each = toset([
    "roles/bigquery.admin",
    "roles/secretmanager.admin",
    "roles/serviceusage.serviceUsageAdmin",
    "roles/resourcemanager.projectIamAdmin",
    "roles/iam.serviceAccountAdmin",
    "roles/iam.workloadIdentityPoolAdmin",
    "roles/storage.admin",
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.terraform.email}"
}

# Cross-project: sgev-terraform needs IAM admin on dev to manage ci_bq_user_dev binding
resource "google_project_iam_member" "terraform_dev_iam_admin" {
  project = var.dev_project_id
  role    = "roles/resourcemanager.projectIamAdmin"
  member  = "serviceAccount:${google_service_account.terraform.email}"
}

# State bucket access
resource "google_storage_bucket_iam_member" "terraform_state" {
  bucket = "sgevpipeline-tfstate"
  role   = "roles/storage.admin"
  member = "serviceAccount:${google_service_account.terraform.email}"
}

# --- Outputs for GitHub Actions vars ---

output "ci_service_account_email" {
  description = "Set as GCP_CI_SA GitHub var in ci.yml"
  value       = google_service_account.ci.email
}

output "ci_wif_provider" {
  description = "Set as GCP_WIF_PROVIDER GitHub var in ci.yml"
  value       = google_iam_workload_identity_pool_provider.github_ci.name
}

output "terraform_service_account_email" {
  description = "Set as GCP_TF_SA GitHub var in terraform.yml"
  value       = google_service_account.terraform.email
}

output "terraform_wif_provider" {
  description = "Set as GCP_TF_WIF_PROVIDER GitHub var in terraform.yml"
  value       = google_iam_workload_identity_pool_provider.github_terraform.name
}
