# Docker · Jour 3 — Stack LLM complète (Compose, sécurité, monitoring)

Projet fil rouge de la formation Docker (3 jours) : déployer **un site web, une API, une base de données et un petit LLM**,
avec **Prometheus, Grafana et Loki** pour la supervision. Tout se lance avec Docker Compose.

```
Navigateur ──► web (nginx, non-root) ──► api (FastAPI) ──► db (PostgreSQL)
                                           │
                                           └──────────► llm (llama.cpp, modèle Qwen2.5 0.5B)

Supervision (profil "monitoring") :
  api / llm /metrics ──► Prometheus ──┐
  cAdvisor (CPU, RAM par conteneur) ──┤──► Grafana ◄── Loki ◄── Alloy (logs de tous les conteneurs)
```

## Prérequis
- Docker Engine / Docker Desktop avec **Compose ≥ 2.20** (`docker compose version`) et BuildKit.
- **6 Go de RAM alloués à Docker** (Docker Desktop : Settings → Resources) et ~8 Go de disque libre.
- Python 3 sur le poste (uniquement pour `scripts/check.py`).

## Démarrage
```bash
sh scripts/init-secrets.sh          # Windows PowerShell : .\scripts\init-secrets.ps1
docker compose up -d --build        # développement (charge compose.override.yml)
docker compose --profile monitoring up -d          # + supervision
docker compose -f compose.yml -f compose.prod.yml up -d --build   # production (APP_VERSION obligatoire)
```
Interfaces : site http://localhost:8080 · Grafana http://localhost:3000 (admin, mot de passe dans `secrets/grafana_admin_password.txt`) · Prometheus http://localhost:9090

> Le premier démarrage télécharge ~500 Mo de modèle : `llm-init` puis `llm` sont longs à devenir *healthy*. Suivre : `docker compose logs -f llm-init llm`.

## Votre mission (jalons)
| # | Jalon | Fichiers à écrire |
|---|-------|-------------------|
| 1 | Images : Dockerfile multi-stage de l'API + Dockerfile du web + `.dockerignore` | `api/Dockerfile`, `api/.dockerignore`, `web/Dockerfile` |
| 2 | Stack applicative : services, réseaux, volumes, secrets, healthchecks | `compose.yml` |
| 3 | Composition de fichiers : durcissement partagé, surcouches dev et prod | `compose.common.yml`, `compose.override.yml`, `compose.prod.yml` |
| 4 | Monitoring : Prometheus, Grafana, Loki, Alloy, cAdvisor | `monitoring/compose.yml` |
| 5 | Sécurité & performance : tout passe `scripts/check.py` | — |
| 6 | Démonstration : question posée au LLM, dashboard Grafana, logs dans Loki | — |

Bonus : profil `backup` (pg_dump), scan de vulnérabilités (Trivy), règle d'alerte supplémentaire, 2 réplicas de l'API.

## Contraintes (contrôlées automatiquement)
- **Multi-stage** : API ≥ 3 stages, image finale < 250 Mo, cache BuildKit, `.dockerignore`.
- **Sécurité** : utilisateurs non-root, `read_only` + `tmpfs`, `cap_drop: [ALL]`, `no-new-privileges`, aucun mot de passe en clair (secrets fichiers), base sur réseau `internal`, `/metrics` jamais exposé, ports publiés sur `127.0.0.1` uniquement.
- **Performance / fiabilité** : limites CPU/RAM, rotation des logs, healthchecks + `depends_on` conditionnels, job `llm-init` en `service_completed_successfully`.
- **Observabilité** : cibles Prometheus UP, dashboard Grafana provisionné, logs JSON visibles dans Loki.

```bash
python scripts/check.py                 # contrôles statiques (mode prod)
python scripts/check.py --mode dev      # idem avec la surcouche dev
python scripts/check.py --runtime       # + contrôles sur la stack démarrée
```

## Fiche technique des briques
| Service | Image / source | Points clés |
|---------|----------------|-------------|
| db | `postgres:16-alpine` | env `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD_FILE=/run/secrets/db_password` ; données `/var/lib/postgresql/data` ; scripts `./db/init` → `/docker-entrypoint-initdb.d` ; `read_only` : tmpfs `/tmp` et `/run/postgresql` ; démarre en root puis bascule sur `postgres` : `cap_add` CHOWN, DAC_OVERRIDE, FOWNER, SETGID, SETUID ; healthcheck `pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}` |
| llm-init | `curlimages/curl:8.22.0` | `user: root`, `entrypoint: ["/bin/sh","-c"]` ; télécharge `$MODEL_URL` vers `/models/$MODEL_FILE` s'il n'existe pas ; volume `llm_models` ; `restart: "no"` |
| llm | `ghcr.io/ggml-org/llama.cpp:server-b11434` | arguments `--model /models/<fichier> --alias <LLM_MODEL> --ctx-size 4096 --parallel 2 --threads 4 --metrics --port 8080` ; volume `llm_models` en `:ro` ; `user: "1000:1000"` ; tmpfs `/tmp` ; healthcheck `curl -f http://localhost:8080/health` (≈ 5 min de `start_period`/retries) ; limite 2 Go |
| api | `./api` (target `runner`) | port 8000 ; env `DB_HOST=db`, `DB_NAME`, `DB_USER`, `DB_PASSWORD_FILE`, `LLM_URL=http://llm:8080`, `LLM_MODEL`, `LOG_LEVEL` ; endpoints `/health/live`, `/health/ready`, `/api/chat`, `/api/history`, `/metrics` ; tmpfs `/tmp` |
| web | `./web` | nginx non-root sur **8080** (publier `127.0.0.1:8080:8080`) ; `/api/` proxifié vers `api:8000` ; `/healthz` ; tmpfs `/tmp` |
| prometheus | `prom/prometheus:v3.13.4` | `/etc/prometheus/prometheus.yml` et `alerts.yml` ← `monitoring/prometheus/` ; `--storage.tsdb.path=/prometheus` ; santé `/-/ready` |
| loki | `grafana/loki:3.7.8` | `-config.file=/etc/loki/loki-config.yml` ; données `/loki` ; santé `/ready` |
| alloy | `grafana/alloy:v1.20.1` | `run --server.http.listen-addr=0.0.0.0:12345 --storage.path=/var/lib/alloy/data /etc/alloy/config.alloy` ; monte `/var/run/docker.sock` en lecture seule |
| cadvisor | `ghcr.io/google/cadvisor:v0.60.6` | `--docker_only=true --housekeeping_interval=15s` ; monte `/`, `/var/run`, `/sys`, `/var/lib/docker` en `:ro` |
| grafana | `grafana/grafana:12.4.12` | `GF_SECURITY_ADMIN_PASSWORD__FILE=/run/secrets/grafana_admin_password` ; `GF_LOG_MODE=console` ; provisioning → `/etc/grafana/provisioning` ; dashboards → `/etc/grafana/dashboards` ; volume `/var/lib/grafana` |

## Structure du dépôt
```
api/            application FastAPI (code et tests fournis, Dockerfile à écrire)
web/            front statique + nginx.conf (Dockerfile à écrire)
db/init/        schéma SQL
monitoring/     configs Prometheus / Loki / Alloy / Grafana (fournies) + compose.yml à écrire
scripts/        init-secrets, pull-images, check.py
compose*.yml    à écrire
```
