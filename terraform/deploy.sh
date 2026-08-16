#!/usr/bin/env bash
set -euo pipefail

readonly DIR=/opt/dagster
readonly GCLOUD=/opt/google-cloud-sdk/bin/gcloud
readonly GCP_PROJECT_ID=project-f78a2754-498a-4582-af0
readonly GHCR_USERNAME=ryantang019

[ -f /opt/deploy/docker-compose.yml.new ] && \
  mv /opt/deploy/docker-compose.yml.new "$DIR/docker-compose.yml"
[ -f /opt/deploy/dagster-sa-key.json.new ] && \
  mv /opt/deploy/dagster-sa-key.json.new "$DIR/dagster-sa-key.json"
[ -f /opt/deploy/.env.deploy.new ] && \
  mv /opt/deploy/.env.deploy.new "$DIR/.env.deploy"

"$GCLOUD" auth activate-service-account --key-file="$DIR/dagster-sa-key.json"
"$GCLOUD" secrets versions access latest \
  --secret=dagster-env \
  --project="$GCP_PROJECT_ID" > "$DIR/.env"

# GHCR only supports classic PATs for non-Actions clients. The secret contains
# a PAT with read:packages and no repository or write scopes.
"$GCLOUD" secrets versions access latest \
  --secret=ghcr-read-token \
  --project="$GCP_PROJECT_ID" |
  docker login ghcr.io --username "$GHCR_USERNAME" --password-stdin

# Remove the client-side registry credential even if pull/up fails. Every
# deployed SHA is pulled before Dagster starts, so run containers use the
# already-present user-code image and do not need persistent registry auth.
trap 'docker logout ghcr.io >/dev/null 2>&1 || true' EXIT

cd "$DIR"

# Reclaim BEFORE pulling: a deploy adds ~3GB of images, and this runs on an
# 80GB disk that has filled up before. Containers must be pruned first — a
# stopped container pins the image it was created from, so the image-only
# prune this used to do reclaimed almost nothing (7% of image space) while
# thousands of dead Dagster run containers held the old tags alive. The
# docker-reap timer does the same sweep daily; this is the pre-pull guard.
docker container prune -f --filter "until=48h"
docker image prune -a -f --filter "until=168h"

docker compose --env-file .env --env-file .env.deploy pull
docker compose --env-file .env --env-file .env.deploy up -d
