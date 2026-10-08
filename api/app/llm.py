"""Client du serveur LLM (llama.cpp, API compatible OpenAI)."""
import httpx

from . import config

SYSTEM_PROMPT = (
    "Tu es un assistant pédagogique pour des étudiants en Big Data et IA. "
    "Réponds en français, de façon courte et claire."
)


class LLMError(Exception):
    pass


def is_ready() -> bool:
    try:
        r = httpx.get(f"{config.LLM_URL}/health", timeout=3)
        return r.status_code == 200
    except httpx.HTTPError:
        return False


def chat(message: str) -> tuple[str, int]:
    """Retourne (réponse, nombre de tokens générés)."""
    payload = {
        "model": config.LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": message},
        ],
        "max_tokens": config.LLM_MAX_TOKENS,
        "temperature": 0.3,
        "stream": False,
    }
    try:
        r = httpx.post(
            f"{config.LLM_URL}/v1/chat/completions",
            json=payload,
            timeout=config.LLM_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        answer = data["choices"][0]["message"]["content"].strip()
        tokens = int(data.get("usage", {}).get("completion_tokens", 0))
        return answer, tokens
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise LLMError(str(exc)) from exc
