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
  server_type = "cpx11"
  image       = "ubuntu-26.04"
  location    = "hil"

  ssh_keys = [hcloud_ssh_key.developer_1.id, hcloud_ssh_key.developer_2.id]
  
  # Cloud-init script to install Docker and run the Dagster deployment
  user_data = <<-EOF
    #cloud-config
    runcmd:
      - curl -fsSL https://get.docker.com | sh
      - systemctl enable docker
      - systemctl start docker
      - curl -fsSL https://sdk.cloud.google.com | bash -s -- --disable-prompts --install-dir=/root
      - /root/google-cloud-sdk/bin/gcloud components install beta --quiet
      - git clone https://github.com/RyanTang019/Singapore-EV-Pipeline.git /root/ev-pipeline
      - /root/google-cloud-sdk/bin/gcloud secrets versions access latest --secret=ev-pipeline-env > /root/ev-pipeline/.env
      - /root/google-cloud-sdk/bin/gcloud secrets versions access latest --secret=ev-pipeline-dagster-key > /root/ev-pipeline/ev-pipeline-dagster-key.json
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
