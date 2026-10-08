#!/usr/bin/env python3
"""Vérifie les contraintes du TP Jour 3 (Docker Compose + LLM + monitoring).

Usage :
  python scripts/check.py              # contrôles statiques (aucun conteneur requis), mode prod
  python scripts/check.py --mode dev   # idem avec compose.override.yml
  python scripts/check.py --runtime    # + contrôles sur la stack en cours d'exécution
Bibliothèque standard uniquement. Code retour 0 si tout est validé.
"""
import argparse, json, os, re, subprocess, sys, urllib.request, urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def run(args, timeout=120):
    env = dict(os.environ)
    env.setdefault("APP_VERSION", "check")
    try:
        p = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=timeout, env=env)
        return p.returncode, p.stdout, p.stderr
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return 127, "", str(exc)


def compose_cmd(mode, extra=()):
    cmd = ["docker", "compose"]
    if mode == "prod":
        cmd += ["-f", "compose.yml", "-f", "compose.prod.yml"]
    cmd += ["--profile", "monitoring"] + list(extra)
    return cmd


def load_config(mode):
    rc, out, err = run(compose_cmd(mode) + ["config", "--format", "json"])
    if rc != 0:
        return None, (err or out).strip().splitlines()[-1:] or ["erreur inconnue"]
    return json.loads(out), None


def read(p):
    f = ROOT / p
    return f.read_text(encoding="utf-8") if f.is_file() else ""


def code_only(text):
    """Texte sans les lignes de commentaire (les TODO du starter ne comptent pas)."""
    return "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))


def mem_limit(svc):
    return (svc.get("deploy", {}).get("resources", {}).get("limits", {}) or {}).get("memory") or svc.get("mem_limit")


def static_checks(mode):
    # ---- Dockerfiles -------------------------------------------------------
    df = code_only(read("api/Dockerfile"))
    froms = re.findall(r"^FROM\s+\S+(?:\s+AS\s+(\S+))?", df, re.M | re.I)
    check("API : Dockerfile multi-stage (≥ 3 stages)", len(froms) >= 3, f"{len(froms)} stage(s)")
    check("API : COPY --from=builder + stage 'runner'", "--from=" in df and re.search(r"AS\s+runner", df, re.I) is not None)
    users = re.findall(r"^USER\s+(\S+)", df, re.M)
    check("API : utilisateur non-root (USER)", bool(users) and users[-1] not in ("root", "0", "0:0"), f"USER {users[-1] if users else '—'}")
    check("API : HEALTHCHECK dans le Dockerfile", re.search(r"^HEALTHCHECK", df, re.M) is not None)
    check("API : cache BuildKit (RUN --mount=type=cache)", "--mount=type=cache" in df)
    di = [l for l in read("api/.dockerignore").splitlines() if l.strip() and not l.startswith("#")]
    check("API : .dockerignore renseigné", len(di) >= 3, f"{len(di)} règle(s)")
    wdf = code_only(read("web/Dockerfile"))
    check("WEB : image non-root (nginx-unprivileged ou USER)", "unprivileged" in wdf or re.search(r"^USER\s+(?!root)", wdf, re.M) is not None)

    # ---- Fichiers Compose --------------------------------------------------
    check("Compose : compose.yml utilise include", re.search(r"^include:", code_only(read("compose.yml")), re.M) is not None)
    check("Compose : compose.override.yml (dev) et compose.prod.yml présents", (ROOT / "compose.override.yml").is_file() and (ROOT / "compose.prod.yml").is_file())
    check("Compose : extends vers compose.common.yml", "extends:" in code_only(read("compose.yml")) and (ROOT / "compose.common.yml").is_file())

    cfg, err = load_config(mode)
    check(f"Compose : `docker compose config` valide (mode {mode})", cfg is not None, "; ".join(err) if err else "")
    if cfg is None:
        return
    svcs = cfg["services"]
    need = ["db", "llm", "llm-init", "api", "web", "prometheus", "grafana", "loki", "alloy", "cadvisor"]
    missing = [s for s in need if s not in svcs]
    check("Compose : 10 services attendus définis", not missing, "manquants : " + ", ".join(missing) if missing else "")
    if missing:
        return
    app = ["db", "llm", "api", "web"]
    # santé & ordre de démarrage
    check("Santé : healthcheck sur db, llm, api, web", all(svcs[s].get("healthcheck") for s in app))
    dep = lambda a, b, c: (svcs[a].get("depends_on", {}) or {}).get(b, {}).get("condition") == c
    check("Ordre : api attend db et llm (service_healthy), web attend api",
          dep("api", "db", "service_healthy") and dep("api", "llm", "service_healthy") and dep("web", "api", "service_healthy"))
    check("Ordre : llm attend llm-init (service_completed_successfully)", dep("llm", "llm-init", "service_completed_successfully"))
    # secrets
    leaks = []
    for n, s in svcs.items():
        for k, v in (s.get("environment") or {}).items():
            if "PASSWORD" in k.upper() and not k.upper().endswith("_FILE") and v not in (None, ""):
                leaks.append(f"{n}.{k}")
    check("Secrets : aucun mot de passe en clair dans environment", not leaks and "db_password" in cfg.get("secrets", {}), ", ".join(leaks))
    # durcissement
    def hard(s, full):
        v = svcs[s]
        ok = "ALL" in (v.get("cap_drop") or []) and any("no-new-privileges" in x for x in (v.get("security_opt") or []))
        return ok and (v.get("read_only") is True if full else True)
    check("Sécurité : api et web en read_only + cap_drop ALL + no-new-privileges", hard("api", True) and hard("web", True))
    check("Sécurité : db et llm avec cap_drop ALL + no-new-privileges", hard("db", False) and hard("llm", False))
    check("Sécurité : llm tourne en non-root (user)", bool(svcs["llm"].get("user")) and not str(svcs["llm"]["user"]).startswith(("0", "root")))
    # perfs
    nolim = [s for s in app + ["prometheus", "grafana", "loki"] if not mem_limit(svcs[s])]
    check("Performance : limite mémoire sur chaque service", not nolim, ", ".join(nolim))
    nolog = [s for s in app if not (svcs[s].get("logging", {}).get("options", {}) or {}).get("max-size")]
    check("Performance : rotation des logs (max-size) sur les services applicatifs", not nolog, ", ".join(nolog))
    # réseau
    nets = cfg.get("networks", {})
    check("Réseau : db uniquement sur un réseau dédié (backend)", list((svcs["db"].get("networks") or {}).keys()) == ["backend"])
    if mode == "prod":
        check("Réseau : backend en internal: true", nets.get("backend", {}).get("internal") is True)
        pub = [s for s in ("db", "llm", "api") if svcs[s].get("ports")]
        check("Réseau : aucun port publié pour db, llm, api (prod)", not pub, ", ".join(pub))
    check("Réseau : web publié uniquement sur 127.0.0.1", all(p.get("host_ip") == "127.0.0.1" for p in svcs["web"].get("ports", [])) and bool(svcs["web"].get("ports")))
    check("Monitoring : services du profil monitoring", all("monitoring" in (svcs[s].get("profiles") or []) for s in ("prometheus", "grafana", "loki", "alloy", "cadvisor")))
    tgt = svcs["api"].get("build", {}).get("target")
    check(f"Multi-stage : build.target de l'api = {'runner' if mode == 'prod' else 'dev'}", tgt == ("runner" if mode == "prod" else "dev"), f"target={tgt}")


def http(url, data=None, timeout=10):
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"} if data else {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:  # noqa: BLE001
        return 0, str(e)


def runtime_checks(mode):
    rc, out, err = run(compose_cmd(mode) + ["ps", "--all", "--format", "json"])
    if rc != 0:
        check("Runtime : docker compose ps", False, err.strip()[:120]); return
    txt = out.strip()
    rows = json.loads(txt) if txt.startswith("[") else [json.loads(l) for l in txt.splitlines() if l.strip()]
    st = {r["Service"]: r for r in rows}
    for s in ("db", "llm", "api", "web"):
        r = st.get(s, {})
        check(f"Runtime : {s} healthy", r.get("Health") == "healthy" and r.get("State") == "running", f"{r.get('State','absent')}/{r.get('Health','')}")
    r = st.get("llm-init", {})
    check("Runtime : llm-init terminé avec succès (exit 0)", r.get("State") == "exited" and r.get("ExitCode") == 0, f"{r.get('State','absent')} code={r.get('ExitCode')}")
    for s in ("api", "web"):
        rc, out, _ = run(compose_cmd(mode) + ["exec", "-T", s, "id", "-u"])
        check(f"Runtime : {s} ne tourne pas en root", rc == 0 and out.strip() != "0", f"uid={out.strip()}")
    rc, out, _ = run(["docker", "image", "inspect", "--format", "{{.Size}}", f"llm-stack/api:{os.environ.get('APP_VERSION', 'dev')}"])
    size = int(out.strip()) / 1e6 if rc == 0 and out.strip().isdigit() else None
    check("Performance : image API < 250 Mo", size is not None and size < 250, f"{size:.0f} Mo" if size else "image introuvable (APP_VERSION ?)")
    port = os.environ.get("WEB_PORT", "8080")
    code, _ = http(f"http://127.0.0.1:{port}/")
    check("Web : page d'accueil (HTTP 200)", code == 200, f"HTTP {code}")
    code, body = http(f"http://127.0.0.1:{port}/api/chat", json.dumps({"message": "Dis bonjour en une phrase."}).encode(), timeout=180)
    ok = code == 200 and '"answer"' in body
    check("Chaîne complète : web → api → llm → db (POST /api/chat)", ok, f"HTTP {code}")
    code, _ = http(f"http://127.0.0.1:{port}/metrics")
    check("Sécurité : /metrics non exposé via le web (404)", code == 404, f"HTTP {code}")
    code, body = http("http://127.0.0.1:9090/api/v1/targets")
    if code == 200:
        t = json.loads(body)["data"]["activeTargets"]
        down = [x["labels"]["job"] for x in t if x["health"] != "up"]
        check("Monitoring : toutes les cibles Prometheus sont UP", not down, ", ".join(down) or f"{len(t)} cibles")
    else:
        check("Monitoring : Prometheus joignable (127.0.0.1:9090)", False, "profil monitoring démarré ?")
    code, _ = http("http://127.0.0.1:3000/api/health")
    check("Monitoring : Grafana joignable (127.0.0.1:3000)", code == 200, f"HTTP {code}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["dev", "prod"], default="prod")
    ap.add_argument("--runtime", action="store_true", help="contrôles sur la stack démarrée")
    a = ap.parse_args()
    rc, _, err = run(["docker", "compose", "version"])
    if rc != 0:
        print("Docker Compose introuvable :", err.strip()); return 2
    static_checks(a.mode)
    if a.runtime:
        runtime_checks(a.mode)
    ok = 0
    for name, good, detail in RESULTS:
        print(f"{'✔' if good else '✘'} {name}" + (f"  [{detail}]" if detail else ""))
        ok += good
    print(f"\nScore : {ok} / {len(RESULTS)} contrôles validés")
    return 0 if ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
