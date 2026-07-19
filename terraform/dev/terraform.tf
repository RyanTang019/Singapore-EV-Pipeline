terraform {
  required_version = ">= 1.5"

  backend "gcs" {
    bucket = "sgevpipeline-tfstate"
    prefix = "terraform/dev"
  }

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.dev_project_id
  region  = var.region
}
