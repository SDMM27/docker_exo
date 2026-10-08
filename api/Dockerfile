# syntax=docker/dockerfile:1.7
# ============================================================
# TODO Jalon 1 — Dockerfile multi-stage de l'API (FastAPI)
#
# Contraintes (vérifiées par scripts/check.py) :
#   - au moins 3 stages : base -> builder -> dev -> test -> runner (cibles utilisées par Compose)
#   - utilisateur NON-ROOT numérique (USER 1000:1000), créé dans le stage "base"
#   - dépendances installées dans "builder" avec  pip install --prefix=/install
#     et un cache BuildKit :  RUN --mount=type=cache,target=/root/.cache/pip ...
#   - "dev"    : copie /install + requirements-dev.txt + app/ + tests/ + pytest.ini ;  CMD uvicorn ... --reload
#   - "test"   : part de "dev" et lance pytest (le build échoue si un test échoue)
#   - "runner" : image finale minimale (COPY --from=builder /install /usr/local + app/ uniquement)
#                HEALTHCHECK sans curl (python -c "import urllib.request; ...")  — CMD en forme exec
#   - ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
# Objectif de taille pour l'image finale : < 250 Mo
# ============================================================
FROM python:3.11-slim AS base
# TODO
