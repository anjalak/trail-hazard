from __future__ import annotations

from app.runtime_check import ensure_supported_python

ensure_supported_python()

import argparse
import os
from pathlib import Path

import psycopg
from psycopg.errors import UniqueViolation


def read_sql(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"SQL file not found: {path}")
    return path.read_text(encoding="utf-8")


def run_sql_file(conn: psycopg.Connection, path: Path, label: str) -> None:
    sql = read_sql(path)
    print(f"Applying {label}: {path}")
    with conn.cursor() as cur:
        cur.execute(sql)


def bootstrap(database_url: str, seed: bool = True) -> None:
    root = Path(__file__).resolve().parents[1]
    schema_path = root / "app" / "models" / "schema.sql"
    seed_path = root / "app" / "models" / "seed.sql"

    try:
        with psycopg.connect(database_url) as conn:
            run_sql_file(conn, schema_path, "schema")
            if seed:
                run_sql_file(conn, seed_path, "seed")
            conn.commit()
    except UniqueViolation as exc:
        raise RuntimeError(
            "Database bootstrap failed because seed data violated a uniqueness constraint. "
            "This usually means part of seed.sql is not idempotent for existing rows. "
            "Use --skip-seed or make the relevant INSERT conflict-safe."
        ) from exc
    except Exception as exc:
        raise RuntimeError(
            "Database bootstrap failed. Ensure DATABASE_URL points to a reachable Postgres/PostGIS "
            "database and re-run once the data issue is resolved."
        ) from exc

    print("Bootstrap complete.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply schema.sql and seed.sql to DATABASE_URL in one command."
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL"),
        help="Postgres connection string. Defaults to DATABASE_URL env var.",
    )
    parser.add_argument(
        "--skip-seed",
        action="store_true",
        help="Apply schema only.",
    )
    args = parser.parse_args()

    if not args.database_url:
        raise SystemExit("DATABASE_URL is required (set env var or pass --database-url).")

    bootstrap(database_url=args.database_url, seed=not args.skip_seed)


if __name__ == "__main__":
    main()
