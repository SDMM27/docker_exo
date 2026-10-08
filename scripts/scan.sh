#!/usr/bin/env sh
# Bonus : scan de vulnérabilités Trivy des images construites (HIGH/CRITICAL).
# Usage : APP_VERSION=1.0 sh scripts/scan.sh
set -e
V="${APP_VERSION:-dev}"
for img in "llm-stack/api:$V" "llm-stack/web:$V"; do
  docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
    aquasec/trivy:0.58.0 image --severity HIGH,CRITICAL --ignore-unfixed "$img"
done
