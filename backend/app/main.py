from app.runtime_check import ensure_supported_python

ensure_supported_python()

import json
import logging
import os
import time

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from fastapi.responses import Response
from strawberry.fastapi import GraphQLRouter

from app.graphql.schema import Context, schema
from app.services.repository_factory import build_api_repository


def _cors_allow_origins() -> list[str]:
    origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    extra = os.getenv("CORS_ALLOW_ORIGINS", "")
    if extra.strip():
        origins.extend(part.strip() for part in extra.split(",") if part.strip())
    return origins


app = FastAPI(title="TrailIntel API", version="0.1.0")
logger = logging.getLogger("trailintel.graphql")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_allow_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

repo = build_api_repository()


def get_context() -> Context:
    return Context(repo=repo)


graphql_app = GraphQLRouter(schema, context_getter=get_context)
app.include_router(graphql_app, prefix="/graphql")


@app.middleware("http")
async def graphql_observability_middleware(request: Request, call_next):
    if request.url.path != "/graphql" or request.method != "POST":
        return await call_next(request)

    started = time.perf_counter()
    operation_name = "anonymous"
    try:
        payload = await request.json()
        if isinstance(payload, dict):
            operation_name = payload.get("operationName") or operation_name
    except Exception:
        operation_name = "unknown"

    error = False
    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.exception(
            "graphql.operation.failed",
            extra={
                "operation_name": operation_name,
                "duration_ms": round(elapsed_ms, 2),
                "has_errors": True,
            },
        )
        raise

    response_body = b""
    async for chunk in response.body_iterator:
        response_body += chunk

    elapsed_ms = (time.perf_counter() - started) * 1000
    if response_body:
        try:
            body_json = json.loads(response_body)
            error = bool(body_json.get("errors")) if isinstance(body_json, dict) else False
        except Exception:
            error = response.status_code >= 400
    else:
        error = response.status_code >= 400

    logger.info(
        "graphql.operation.completed",
        extra={
            "operation_name": operation_name,
            "duration_ms": round(elapsed_ms, 2),
            "has_errors": error,
        },
    )

    return Response(
        content=response_body,
        status_code=response.status_code,
        headers=dict(response.headers),
        media_type=response.media_type,
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/admin/ingestion-failures")
def list_ingestion_failures(limit: int = Query(20, ge=1, le=100)) -> dict:
    """Log-friendly listing of the last N ingestion task dead-letter rows (see Celery on_failure)."""
    rows = repo.list_ingestion_task_failures(limit=limit)
    logger.info(
        "ingestion.dlq.served",
        extra={"count": len(rows), "limit": limit},
    )
    return {
        "limit": limit,
        "count": len(rows),
        "failures": rows,
    }
