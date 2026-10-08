-- Exécuté une seule fois, à la première initialisation du volume PostgreSQL.
CREATE TABLE IF NOT EXISTS messages (
    id          BIGSERIAL PRIMARY KEY,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    prompt      TEXT        NOT NULL,
    answer      TEXT        NOT NULL,
    model       TEXT        NOT NULL,
    latency_ms  INTEGER     NOT NULL,
    tokens      INTEGER     NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages (created_at DESC);
