-- Lab 08 — Seed de la base de datos de la app
-- Tablas transaccionales (distintas de la lake de Olist en S3)

CREATE TABLE IF NOT EXISTS app_users (
    id          SERIAL PRIMARY KEY,
    email       TEXT UNIQUE NOT NULL,
    full_name   TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app_sessions (
    id          SERIAL PRIMARY KEY,
    user_id     INT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    ip          TEXT,
    started_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at    TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS app_audit_log (
    id          SERIAL PRIMARY KEY,
    user_id     INT REFERENCES app_users(id) ON DELETE SET NULL,
    action      TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO app_users (email, full_name) VALUES
    ('alice@example.com',  'Alice Anderson'),
    ('bob@example.com',    'Bob Brown'),
    ('carol@example.com',  'Carol Cordero'),
    ('diego@example.com',  'Diego Domínguez'),
    ('elena@example.com',  'Elena Esquivel')
ON CONFLICT (email) DO NOTHING;

INSERT INTO app_audit_log (user_id, action) VALUES
    (1, 'user.created'),
    (2, 'user.created'),
    (3, 'user.created'),
    (4, 'user.created'),
    (5, 'user.created');
