#!/usr/bin/env sh
# Crée .env et les fichiers de secrets (ignorés par git). Linux / macOS / Git Bash / WSL.
set -e
cd "$(dirname "$0")/.."
mkdir -p secrets backups
[ -f .env ] || cp .env.example .env
gen() { head -c 32 /dev/urandom | base64 | tr -d '/+=\n' | head -c 24; }
for n in db_password grafana_admin_password; do
  [ -f "secrets/$n.txt" ] || gen > "secrets/$n.txt"
done
chmod 644 secrets/*.txt
echo "OK : .env et secrets/*.txt prêts (mot de passe Grafana : secrets/grafana_admin_password.txt)"
