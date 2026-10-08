"""Métriques Prometheus exposées sur /metrics."""
from prometheus_client import Counter, Histogram

HTTP_REQUESTS = Counter(
    "http_requests_total", "Requêtes HTTP reçues", ["method", "path", "status"]
)
HTTP_LATENCY = Histogram(
    "http_request_duration_seconds",
    "Durée des requêtes HTTP",
    ["method", "path"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120),
)
LLM_REQUESTS = Counter(
    "llm_requests_total", "Appels au LLM", ["model", "outcome"]
)
LLM_LATENCY = Histogram(
    "llm_request_duration_seconds",
    "Durée des appels au LLM",
    ["model"],
    buckets=(0.5, 1, 2, 5, 10, 20, 40, 80, 120),
)
LLM_TOKENS = Counter(
    "llm_generated_tokens_total", "Tokens générés par le LLM", ["model"]
)
