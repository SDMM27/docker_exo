"""Accès PostgreSQL via un pool de connexions."""
from contextlib import contextmanager

from psycopg2.pool import ThreadedConnectionPool

from . import config

_pool: ThreadedConnectionPool | None = None


def init_pool() -> None:
    global _pool
    _pool = ThreadedConnectionPool(
        minconn=1,
        maxconn=5,
        host=config.DB_HOST,
        port=config.DB_PORT,
        dbname=config.DB_NAME,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        connect_timeout=5,
    )


def close_pool() -> None:
    if _pool is not None:
        _pool.closeall()


@contextmanager
def connection():
    if _pool is None:
        raise RuntimeError("Pool PostgreSQL non initialisé")
    conn = _pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)


def ping() -> bool:
    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1")
        return cur.fetchone() == (1,)


def save_message(prompt: str, answer: str, model: str, latency_ms: int, tokens: int) -> int:
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO messages (prompt, answer, model, latency_ms, tokens)
               VALUES (%s, %s, %s, %s, %s) RETURNING id""",
            (prompt, answer, model, latency_ms, tokens),
        )
        return cur.fetchone()[0]


def last_messages(limit: int = 20) -> list[dict]:
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT id, created_at, prompt, answer, model, latency_ms, tokens
               FROM messages ORDER BY id DESC LIMIT %s""",
            (limit,),
        )
        rows = cur.fetchall()
    return [
        {
            "id": r[0],
            "created_at": r[1].isoformat(),
            "prompt": r[2],
            "answer": r[3],
            "model": r[4],
            "latency_ms": r[5],
            "tokens": r[6],
        }
        for r in rows
    ]
