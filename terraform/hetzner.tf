# Hetzner VM

resource "hcloud_primary_ip" "dagster" {
  name        = "dagster-ip"
  type        = "ipv4"
  location    = "fsn1"
  auto_delete = false
}

resource "hcloud_ssh_key" "developer_1" {
  name       = "dagster-key-1"
  public_key = var.ssh_public_key_1
}

resource "hcloud_ssh_key" "developer_2" {
  name       = "dagster-key-2"
  public_key = var.ssh_public_key_2
}

resource "hcloud_server" "dagster" {
  name        = "dagster"
  server_type = "cpx22"
  image       = "ubuntu-26.04"
  location    = "fsn1"

  ssh_keys = [hcloud_ssh_key.developer_1.id, hcloud_ssh_key.developer_2.id]

  public_net {
    ipv4_enabled = true
    ipv4         = hcloud_primary_ip.dagster.id
  }

  user_data = <<-EOF
    #cloud-config
    users:
      - default
      - name: deploy
        groups: docker
        shell: /usr/sbin/nologin
        ssh_authorized_keys:
          - 'command="/opt/deploy/deploy.sh",no-port-forwarding,no-X11-forwarding,no-agent-forwarding ${var.deploy_ssh_public_key}'

    write_files:
      - path: /opt/deploy/deploy.sh
        permissions: "0755"
        content: |
          #!/usr/bin/env bash
          set -euo pipefail
          DIR=/opt/dagster
          GCLOUD=/root/google-cloud-sdk/bin/gcloud

          [ -f /opt/deploy/docker-compose.yml.new ] && mv /opt/deploy/docker-compose.yml.new $DIR/docker-compose.yml
          [ -f /opt/deploy/dagster-sa-key.json.new ] && mv /opt/deploy/dagster-sa-key.json.new $DIR/dagster-sa-key.json
          [ -f /opt/deploy/.env.deploy.new ] && mv /opt/deploy/.env.deploy.new $DIR/.env.deploy

          $GCLOUD auth activate-service-account --key-file=$DIR/dagster-sa-key.json
          $GCLOUD secrets versions access latest --secret=dagster-env --project=${var.project_id} > $DIR/.env

          cd $DIR
          docker compose --env-file .env --env-file .env.deploy pull
          docker compose --env-file .env --env-file .env.deploy up -d
          docker image prune -f --filter "until=72h"

    runcmd:
      - mkdir -p /opt/dagster /opt/deploy
      - chown deploy:deploy /opt/deploy
      - curl -fsSL https://get.docker.com | sh
      - systemctl enable --now docker
      - curl -fsSL https://sdk.cloud.google.com | bash -s -- --disable-prompts --install-dir=/root

  EOF

  labels = {
    environment = "production"
    pipeline    = "dagster"
  }
}

output "server_ip" {
  value       = hcloud_primary_ip.dagster.ip_address
  description = "Static IP of the Dagster VM"
}
