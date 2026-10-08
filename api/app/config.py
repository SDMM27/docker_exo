"""Configuration 12-factor : tout vient des variables d'environnement."""
import os
from pathlib import Path


def _read_secret(name: str, default: str = "") -> str:
    """Lit <NAME>_FILE (Docker secret) en priorité, sinon <NAME>."""
    file_path = os.getenv(f"{name}_FILE")
    if file_path and Path(file_path).is_file():
        return Path(file_path).read_text().strip()
    return os.getenv(name, default)


DB_HOST = os.getenv("DB_HOST", "db")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "llmapp")
DB_USER = os.getenv("DB_USER", "llmapp")
DB_PASSWORD = _read_secret("DB_PASSWORD")

LLM_URL = os.getenv("LLM_URL", "http://llm:8080")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5-0.5b-instruct")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "120"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "256"))

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
