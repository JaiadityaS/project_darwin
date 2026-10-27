# The Rieux demo service on Cloud Run (F13.1, F13.2, D-040). Apply it once, as a project owner:
#   tofu init && tofu apply -var project_id=<your project id>      (terraform works the same way)
# It makes the APIs, an Artifact Registry repository, Workload Identity Federation for this GitLab
# project, a deploy service account, a runtime service account with no roles, and the Cloud Run
# service. The service starts with a placeholder image. The deploy jobs of .gitlab-ci.yml then roll
# out the held, signed image as new revisions: no key file, only a short-lived token from the job's
# GitLab ID token. Copy the `gitlab_ci_variables` output into the variables of .gitlab-ci.yml.

terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.40"
    }
  }
}

variable "project_id" {
  type        = string
  description = "The Google Cloud project, with billing on."
}

variable "region" {
  type        = string
  default     = "northamerica-northeast1"
  description = "The lowest grid intensity in Google's region data (11.36 gCO2e/kWh), as in the SCI evidence."
}

variable "gitlab_project_id" {
  type        = string
  default     = "87296266"
  description = "Only pipelines of this GitLab project can deploy."
}

variable "gitlab_branch" {
  type        = string
  default     = "main"
  description = "Only pipelines of this branch can deploy."
}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  apis = [
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "sts.googleapis.com",
  ]
}

resource "google_project_service" "api" {
  for_each           = toset(local.apis)
  service            = each.value
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "rieux" {
  location      = var.region
  repository_id = "rieux"
  format        = "DOCKER"
  description   = "Rieux service images: the held whisper.cpp image plus the gateway"
  depends_on    = [google_project_service.api]
}

# The identity of the service. It has no roles: the service calls no Google API.
resource "google_service_account" "run" {
  account_id   = "rieux-run"
  display_name = "Rieux service (no roles)"
  depends_on   = [google_project_service.api]
}

# The identity of the deploy jobs. Only the GitLab pipelines below can act as it.
resource "google_service_account" "deploy" {
  account_id   = "rieux-deploy"
  display_name = "Rieux deploy jobs (GitLab CI, Workload Identity Federation)"
  depends_on   = [google_project_service.api]
}

resource "google_iam_workload_identity_pool" "gitlab" {
  workload_identity_pool_id = "rieux-gitlab"
  display_name              = "Rieux GitLab"
  depends_on                = [google_project_service.api]
}

# GitLab ID tokens of one project and one branch. Any other project, branch, tag or merge request is refused.
resource "google_iam_workload_identity_pool_provider" "gitlab" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.gitlab.workload_identity_pool_id
  workload_identity_pool_provider_id = "gitlab-com"
  display_name                       = "gitlab.com"
  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.project_id" = "assertion.project_id"
    "attribute.ref"        = "assertion.ref"
    "attribute.ref_type"   = "assertion.ref_type"
  }
  attribute_condition = "assertion.project_id == '${var.gitlab_project_id}' && assertion.ref_type == 'branch' && assertion.ref == '${var.gitlab_branch}'"
  oidc {
    issuer_uri = "https://gitlab.com"
  }
}

resource "google_service_account_iam_member" "deploy_from_gitlab" {
  service_account_id = google_service_account.deploy.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.gitlab.name}/attribute.project_id/${var.gitlab_project_id}"
}

resource "google_artifact_registry_repository_iam_member" "deploy_push" {
  location   = google_artifact_registry_repository.rieux.location
  repository = google_artifact_registry_repository.rieux.name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.deploy.email}"
}

resource "google_project_iam_member" "deploy_run" {
  project = var.project_id
  role    = "roles/run.developer"
  member  = "serviceAccount:${google_service_account.deploy.email}"
}

resource "google_service_account_iam_member" "deploy_acts_as_run" {
  service_account_id = google_service_account.run.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deploy.email}"
}

# F13.3: at most 1 instance, 0 when idle. The gateway caps the audio at 30 s and limits the requests.
resource "google_cloud_run_v2_service" "rieux" {
  name                = "rieux"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false

  template {
    service_account                  = google_service_account.run.email
    timeout                          = "120s"
    max_instance_request_concurrency = 8
    scaling {
      min_instance_count = 0
      max_instance_count = 1
    }
    containers {
      # A placeholder until the first deploy job. The deploy jobs set the image.
      image = "us-docker.pkg.dev/cloudrun/container/hello"
      ports {
        container_port = 8080
      }
      resources {
        limits = {
          cpu    = "1"
          memory = "2Gi"
        }
        startup_cpu_boost = true
      }
      startup_probe {
        tcp_socket {
          port = 8080
        }
        period_seconds    = 10
        timeout_seconds   = 5
        failure_threshold = 30
      }
    }
  }

  # The deploy jobs own the image and the traffic split.
  lifecycle {
    ignore_changes = [
      client,
      client_version,
      traffic,
      template[0].revision,
      template[0].labels,
      template[0].annotations,
      template[0].containers[0].image,
    ]
  }
  depends_on = [google_project_service.api]
}

resource "google_cloud_run_v2_service_iam_member" "public" {
  name     = google_cloud_run_v2_service.rieux.name
  location = google_cloud_run_v2_service.rieux.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

output "service_url" {
  value = google_cloud_run_v2_service.rieux.uri
}

# None of these values is a secret. They go into the variables of .gitlab-ci.yml.
output "gitlab_ci_variables" {
  value = {
    GCP_PROJECT_ID      = var.project_id
    GCP_REGION          = var.region
    GCP_WIF_PROVIDER    = google_iam_workload_identity_pool_provider.gitlab.name
    GCP_WIF_AUDIENCE    = "https://iam.googleapis.com/${google_iam_workload_identity_pool_provider.gitlab.name}"
    GCP_SERVICE_ACCOUNT = google_service_account.deploy.email
  }
}
