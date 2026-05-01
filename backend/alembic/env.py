from __future__ import annotations

import os
from logging.config import fileConfig
from urllib.parse import urlparse

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None


def _alembic_sqlalchemy_url(raw: str) -> str:
    """Build a SQLAlchemy URL Alembic can use (psycopg v3 driver)."""
    url = raw.strip("\ufeff\u200b").strip()
    if len(url) >= 2 and url[0] == url[-1] and url[0] in "\"'":
        url = url[1:-1].strip()
    if not url:
        raise ValueError("DATABASE_URL is empty.")

    parsed = urlparse(url)
    base_scheme = (parsed.scheme or "").lower().split("+", 1)[0]
    if base_scheme in ("http", "https"):
        raise ValueError(
            "DATABASE_URL looks like an HTTP(S) URL (SQLAlchemy would try dialect 'https'). "
            "Use a Postgres URI: postgresql://user:pass@host/dbname. "
            "On Supabase + Render, copy the Session or Transaction pooler string from "
            "Dashboard → Connect, not the project REST URL or direct db host if it fails."
        )
    if url.startswith("postgres://"):
        url = "postgresql://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    raise ValueError(
        "DATABASE_URL must start with postgresql:// or postgres://. "
        f"Scheme was {base_scheme!r} (first chars: {url[:24]!r}…)."
    )


database_url = os.getenv("DATABASE_URL")
if os.getenv("RENDER") == "true" and not (database_url or "").strip():
    raise ValueError("DATABASE_URL must be set for this service on Render.")
if database_url:
    config.set_main_option("sqlalchemy.url", _alembic_sqlalchemy_url(database_url))


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
