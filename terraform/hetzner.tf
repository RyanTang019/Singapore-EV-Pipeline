# Hetzner VM

resource "hcloud_ssh_key" "developer_1" {
  name       = "ev-pipeline-key-1"
  public_key = var.ssh_public_key_1
}

resource "hcloud_ssh_key" "developer_2" {
  name       = "ev-pipeline-key-2"
  public_key = var.ssh_public_key_2
}

resource "hcloud_server" "dagster" {
  name        = "ev-pipeline-dagster"
  server_type = "cpx22"
  image       = "ubuntu-26.04"
  location    = "fsn1"

  ssh_keys = [hcloud_ssh_key.developer_1.id, hcloud_ssh_key.developer_2.id]

  # Cloud-init script to install Docker and run the Dagster deployment
  user_data = <<-EOF
    #cloud-config
    write_files:
      - path: /root/ev-pipeline/ev-pipeline-dagster-key.json
        permissions: "0600"
        content: |
          ${indent(10, file(pathexpand(var.dagster_key_path)))}
    runcmd:
      - mkdir -p /root/ev-pipeline
      - curl -fsSL https://get.docker.com | sh
      - systemctl enable --now docker
      - curl -fsSL https://sdk.cloud.google.com | bash -s -- --disable-prompts --install-dir=/root
      - /root/google-cloud-sdk/bin/gcloud auth activate-service-account --key-file=/root/ev-pipeline/ev-pipeline-dagster-key.json
      - /root/google-cloud-sdk/bin/gcloud secrets versions access latest --secret=ev-pipeline-env --project=${var.project_id} > /root/ev-pipeline/.env
      - /root/google-cloud-sdk/bin/gcloud secrets versions access latest --secret=ev-pipeline-compose --project=${var.project_id} > /root/ev-pipeline/docker-compose.yml
      - cd /root/ev-pipeline && docker compose up -d
  EOF

  labels = {
    environment = "production"
    pipeline    = "ev-pipeline"
  }
}

# IP of created server for output
output "server_ip" {
  value       = hcloud_server.dagster.ipv4_address
  description = "Public IP of the Dagster VM"
}
