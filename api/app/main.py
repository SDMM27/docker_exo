"""API FastAPI : chat avec un petit LLM, historique en base, métriques Prometheus."""
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field

from . import config, db, llm, metrics
from .logging_conf import setup_logging

log = setup_logging(config.LOG_LEVEL)


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_pool()
    log.info("API démarrée", extra={"extra_fields": {"model": config.LLM_MODEL}})
    yield
    db.close_pool()
    log.info("API arrêtée")


app = FastAPI(title="LLM API", version="1.0.0", lifespan=lifespan)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    id: int
    answer: str
    model: str
    latency_ms: int
    tokens: int


@app.middleware("http")
async def observe(request: Request, call_next):
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        duration = time.perf_counter() - start
        route = request.scope.get("route")
        path = route.path if route else "unmatched"
        if path != "/metrics":
            metrics.HTTP_REQUESTS.labels(request.method, path, str(status)).inc()
            metrics.HTTP_LATENCY.labels(request.method, path).observe(duration)
        # Les sondes de santé et /metrics ne sont pas journalisées (bruit inutile dans Loki).
        if path not in ("/metrics", "/health/live", "/health/ready"):
            log.info(
                "request",
                extra={"extra_fields": {
                    "method": request.method, "path": path, "status": status,
                    "duration_ms": round(duration * 1000),
                }},
            )


@app.get("/health/live")
def live():
    """Liveness : le process répond."""
    return {"status": "ok"}


@app.get("/health/ready")
def ready():
    """Readiness : la base ET le LLM répondent."""
    checks = {"db": False, "llm": llm.is_ready()}
    try:
        checks["db"] = db.ping()
    except Exception:  # noqa: BLE001
        checks["db"] = False
    ok = all(checks.values())
    return JSONResponse({"status": "ok" if ok else "degraded", **checks},
                        status_code=200 if ok else 503)


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    start = time.perf_counter()
    try:
        answer, tokens = llm.chat(req.message)
    except llm.LLMError as exc:
        metrics.LLM_REQUESTS.labels(config.LLM_MODEL, "error").inc()
        log.error("LLM indisponible", extra={"extra_fields": {"error": str(exc)}})
        raise HTTPException(status_code=502, detail="LLM indisponible") from exc
    elapsed = time.perf_counter() - start
    metrics.LLM_REQUESTS.labels(config.LLM_MODEL, "ok").inc()
    metrics.LLM_LATENCY.labels(config.LLM_MODEL).observe(elapsed)
    metrics.LLM_TOKENS.labels(config.LLM_MODEL).inc(tokens)
    latency_ms = round(elapsed * 1000)
    try:
        msg_id = db.save_message(req.message, answer, config.LLM_MODEL, latency_ms, tokens)
    except Exception as exc:  # noqa: BLE001
        log.error("Écriture en base impossible", extra={"extra_fields": {"error": str(exc)}})
        raise HTTPException(status_code=503, detail="Base de données indisponible") from exc
    return ChatResponse(id=msg_id, answer=answer, model=config.LLM_MODEL,
                        latency_ms=latency_ms, tokens=tokens)


@app.get("/api/history")
def history(limit: int = 20):
    limit = max(1, min(limit, 100))
    try:
        return db.last_messages(limit)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail="Base de données indisponible") from exc


@app.get("/metrics")
def prometheus_metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
