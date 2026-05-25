terraform {
  required_version = ">= 1.5"

  backend "gcs" {
    bucket = "sgevpipeline-tfstate"
    prefix = "terraform/state"
  }

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "hcloud" {
  token = var.hcloud_token
}