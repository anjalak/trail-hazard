import os

from pydantic import BaseModel


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


class Settings(BaseModel):
    app_name: str = "TrailIntel API"
    graphql_path: str = "/graphql"
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    database_url: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/trailintel")
    # Default to Postgres-backed repository so runtime does not rely on synthetic in-memory records.
    use_in_memory_repository: bool = os.getenv("USE_IN_MEMORY_REPOSITORY", "false").lower() == "true"
    # GraphQL report mutations (submitReport, upvoteReport); see docs and app.services.report_rate_limit
    rate_limit_reports_enabled: bool = os.getenv("RATE_LIMIT_REPORTS_ENABLED", "true").lower() == "true"
    allow_public_report_submission: bool = os.getenv("ALLOW_PUBLIC_REPORT_SUBMISSION", "false").lower() == "true"
    rate_limit_submit_max_per_window: int = _int_env("RATE_LIMIT_SUBMIT_MAX_PER_WINDOW", 20)
    rate_limit_upvote_max_per_window: int = _int_env("RATE_LIMIT_UPVOTE_MAX_PER_WINDOW", 60)
    rate_limit_window_seconds: int = _int_env("RATE_LIMIT_WINDOW_SECONDS", 3600)


settings = Settings()
