# Hetzner VM

resource "hcloud_primary_ip" "dagster" {
  name        = "dagster-ip"
  type        = "ipv4"
  location    = "fsn1"
  auto_delete = false
}

resource "hcloud_firewall" "dagster" {
  name = "dagster-fw"

  # SSH — needed for admin access and the CI/CD deploy job.
  # Source is open because GitHub Actions runners use dynamic IPs; key-based
  # auth (no passwords) is what protects it.
  rule {
    direction   = "in"
    protocol    = "tcp"
    port        = "22"
    source_ips  = ["0.0.0.0/0", "::/0"]
    description = "SSH"
  }

  # Ping, for basic reachability diagnostics.
  rule {
    direction   = "in"
    protocol    = "icmp"
    source_ips  = ["0.0.0.0/0", "::/0"]
    description = "ICMP"
  }

  # No rule for Dagit (3000): it binds to 127.0.0.1 and is reached via SSH
  # tunnel. No outbound rules => all outbound stays allowed.
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

  # Cloud-init only runs when the VM is created. The deploy script is refreshed
  # on existing hosts by CI, so changing its bootstrap copy must not replace a
  # running server. Force an explicit replacement when other cloud-init changes
  # genuinely need to be applied to an existing VM.
  lifecycle {
    ignore_changes = [user_data, ssh_keys]
  }

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
        shell: /bin/bash
        ssh_authorized_keys:
          - '${var.deploy_ssh_public_key}'

    write_files:
      - path: /opt/deploy/deploy.sh
        permissions: "0755"
        encoding: b64
        content: ${base64encode(file("${path.module}/../deploy.sh"))}

      # Daemon-wide log rotation. docker-compose.yml caps the four services it
      # owns, but Dagster's DockerRunLauncher spawns run containers outside
      # compose — only a daemon default caps those.
      - path: /etc/docker/daemon.json
        permissions: "0644"
        content: |
          {
            "log-driver": "json-file",
            "log-opts": { "max-size": "10m", "max-file": "3" }
          }

      # DockerRunLauncher never removes a run container when its process
      # exits, and a stopped container pins the image it was built from. Left
      # alone this filled the 80GB disk (9,147 dead containers pinning ~70
      # user-code/dagster tags), which took Postgres down with "could not
      # write lock file: No space left on device". Reap on a delay rather than
      # setting auto_remove=true, so a failed run stays inspectable via
      # `docker logs` and run monitoring can still find its container.
      - path: /etc/systemd/system/docker-reap.service
        permissions: "0644"
        content: |
          [Unit]
          Description=Reclaim Docker disk (dead run containers, unreferenced images)
          Requires=docker.service
          After=docker.service

          [Service]
          Type=oneshot
          ExecStart=/usr/bin/docker container prune -f --filter until=48h
          ExecStart=/usr/bin/docker image prune -a -f --filter until=168h
          ExecStart=/usr/bin/docker builder prune -f --filter until=168h

      - path: /etc/systemd/system/docker-reap.timer
        permissions: "0644"
        content: |
          [Unit]
          Description=Daily Docker disk reclaim

          [Timer]
          OnCalendar=daily
          Persistent=true
          RandomizedDelaySec=30m

          [Install]
          WantedBy=timers.target

    runcmd:
      - mkdir -p /opt/dagster /opt/deploy
      - curl -fsSL https://get.docker.com | sh
      - systemctl enable --now docker
      # write_files dropped the units after systemd's initial scan.
      - systemctl daemon-reload
      - systemctl enable --now docker-reap.timer
      - usermod -aG docker deploy
      - chown deploy:deploy /opt/deploy /opt/dagster
      - curl -fsSL https://sdk.cloud.google.com | bash -s -- --disable-prompts --install-dir=/opt

  EOF

  labels = {
    environment = "production"
    pipeline    = "dagster"
  }
}

# Attach the firewall via a separate resource (not `firewall_ids` on the
# server) so it can never force a server replacement.
resource "hcloud_firewall_attachment" "dagster" {
  firewall_id = hcloud_firewall.dagster.id
  server_ids  = [hcloud_server.dagster.id]
}

output "server_ip" {
  value       = hcloud_primary_ip.dagster.ip_address
  description = "Static IP of the Dagster VM"
}
