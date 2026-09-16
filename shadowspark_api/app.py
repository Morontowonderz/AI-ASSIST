from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

from .auth import AuthenticationError, authenticate, require_scope
from .database import Database, IdempotencyConflict
from .schemas import (
    AnnotationRequest,
    BriefRequest,
    BriefResponse,
    ErrorResponse,
    ReviewQueueResponse,
)
from .service import ComplianceService


_RAW_ID = re.compile(r"(?<!\d)\d{11}(?!\d)")
_TENANT_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def create_app(db_path: str | Path | None = None, fixture_dir: str | Path = "vendor") -> FastAPI:
    resolved_db_path = (
        db_path
        if db_path is not None
        else os.environ.get("SHADOWSPARK_DB_PATH", "./data/shadowspark.db")
    )
    app = FastAPI(
        title="ShadowSpark Compliance Review V1",
        version="1.1.0",
        description=(
            "ShadowSpark AI-ASSIST multi-tenant compliance review and brief generation API.\n\n"
            "### Authentication\n"
            "All endpoints require an HTTP Bearer capability token (`Authorization: Bearer <token>`).\n"
            "In production (`SHADOWSPARK_ENV=production`), authentication requires `SHADOWSPARK_API_TOKEN`.\n\n"
            "### Multi-Tenancy\n"
            "Requests are tenant-scoped via the `X-Tenant-Slug` or `X-Tenant-ID` header.\n"
            "Tenant context isolates all briefs, reviews, annotations, audit logs, and idempotency.\n\n"
            "### Idempotency\n"
            "Mutating endpoints (`POST /v1/compliance-review-brief` and `POST /v1/review-queue/{brief_id}/annotations`)\n"
            "strictly require the `Idempotency-Key` header (max 128 characters).\n\n"
            "### Tracing\n"
            "Every response echoes a stable `X-Request-ID` header for distributed tracing and audit logs."
        ),
        openapi_tags=[
            {"name": "System", "description": "Liveness and readiness checks"},
            {"name": "Compliance Briefs", "description": "Tenant-scoped brief generation with deterministic risk evaluation"},
            {"name": "Review Queue", "description": "Operator review queue inspection and immutable audit annotation"},
        ],
    )
    service = ComplianceService(Database(resolved_db_path), fixture_dir)

    @app.middleware("http")
    async def trace_request_id(request: Request, call_next):
        req_id = request.headers.get("X-Request-ID") or uuid4().hex
        request.state.request_id = req_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response

    def resolve_tenant(x_tenant_slug: str | None, x_tenant_id: str | None) -> str | None:
        raw = x_tenant_slug or x_tenant_id
        if raw is not None:
            val = raw.strip()
            if not val or not _TENANT_SLUG_RE.match(val):
                raise HTTPException(status_code=400, detail="invalid tenant identifier")
            return val
        return None

    def principal_for(authorization: str | None, tenant_id: str | None, scope: str):
        try:
            principal = authenticate(authorization, tenant_id=tenant_id)
            require_scope(principal, scope)
            return principal
        except AuthenticationError:
            raise HTTPException(status_code=401, detail="authentication failed")
        except PermissionError:
            raise HTTPException(status_code=403, detail="scope required")

    def require_idempotency_key(idempotency_key: str | None) -> str:
        if not idempotency_key or len(idempotency_key) > 128:
            raise HTTPException(status_code=400, detail="Idempotency-Key required")
        return idempotency_key

    @app.get(
        "/healthz",
        tags=["System"],
        summary="Service Health Check",
        description="Returns 200 with status ok when service is operational.",
        responses={200: {"description": "Service operational"}},
    )
    def healthz():
        return {"status": "ok"}

    @app.post(
        "/v1/compliance-review-brief",
        tags=["Compliance Briefs"],
        summary="Create Compliance Review Brief",
        description="Generates or replays a deterministic compliance brief for a given exception under the tenant's scope.",
        status_code=status.HTTP_201_CREATED,
        response_model=BriefResponse,
        responses={
            400: {"model": ErrorResponse, "description": "Validation error, invalid tenant identifier, or missing Idempotency-Key"},
            401: {"model": ErrorResponse, "description": "Authentication failure (invalid or missing capability token)"},
            403: {"model": ErrorResponse, "description": "Insufficient scope for requested action"},
            404: {"model": ErrorResponse, "description": "Exception not found (or cross-tenant access attempt)"},
            409: {"model": ErrorResponse, "description": "Idempotency conflict (key reused with mismatched payload)"},
            422: {"model": ErrorResponse, "description": "Unprocessable entity (e.g. raw personal identifiers)"},
            429: {"description": "Blocked by policy rate limit / budget trip"},
        },
    )
    def create_brief(
        body: BriefRequest,
        request: Request,
        authorization: str | None = Header(default=None, description="Bearer capability token"),
        x_tenant_slug: str | None = Header(default=None, alias="X-Tenant-Slug", description="Tenant slug context"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID", description="Alternative tenant identifier"),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", description="Unique idempotency key"),
        x_request_id: str | None = Header(default=None, alias="X-Request-ID", description="Request tracing identifier"),
    ):
        tenant_context = resolve_tenant(x_tenant_slug, x_tenant_id)
        principal = principal_for(authorization, tenant_context, "compliance:read")
        idempotency_key = require_idempotency_key(idempotency_key)

        if body.tenant_id is not None and body.tenant_id != principal.tenant_id:
            raise HTTPException(status_code=400, detail="tenant mismatch between header and body")
        if _RAW_ID.search(body.exception_id):
            raise HTTPException(status_code=422, detail="raw identifier not accepted")
        if body.exception_id.partition(":")[0].startswith("tenant_") and not body.exception_id.startswith(principal.tenant_id + ":"):
            raise HTTPException(status_code=404, detail="exception not found")

        req_id = x_request_id or getattr(request.state, "request_id", uuid4().hex)
        try:
            result = service.create_brief(
                principal.tenant_id,
                body.exception_id,
                idempotency_key,
                req_id,
                principal.key_id,
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="exception not found")
        except IdempotencyConflict:
            raise HTTPException(status_code=409, detail="idempotency key conflict")

        if result["output"].get("status") == "blocked":
            if "LLM06:2026" in result["output"].get("brief", {}).get("risk_flags", []):
                return JSONResponse(status_code=429, content=result)
            return result
        return result

    @app.get(
        "/v1/review-queue/{brief_id}",
        tags=["Review Queue"],
        summary="Inspect Review Queue Item",
        description="Retrieves the review status, brief output, and annotations for a tenant-scoped brief.",
        response_model=ReviewQueueResponse,
        responses={
            400: {"model": ErrorResponse, "description": "Invalid tenant identifier"},
            401: {"model": ErrorResponse, "description": "Authentication failure"},
            403: {"model": ErrorResponse, "description": "Insufficient scope"},
            404: {"model": ErrorResponse, "description": "Review item not found (or foreign tenant access)"},
        },
    )
    def get_review(
        brief_id: str,
        authorization: str | None = Header(default=None, description="Bearer capability token"),
        x_tenant_slug: str | None = Header(default=None, alias="X-Tenant-Slug", description="Tenant slug context"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID", description="Alternative tenant identifier"),
    ):
        tenant_context = resolve_tenant(x_tenant_slug, x_tenant_id)
        principal = principal_for(authorization, tenant_context, "compliance:read")
        review = service.get_review(principal.tenant_id, brief_id)
        if review is None:
            raise HTTPException(status_code=404, detail="review not found")
        return review

    @app.post(
        "/v1/review-queue/{brief_id}/annotations",
        tags=["Review Queue"],
        summary="Append Operator Annotation",
        description="Appends an immutable audit annotation to the tenant-scoped review queue entry.",
        response_model=ReviewQueueResponse,
        responses={
            400: {"model": ErrorResponse, "description": "Validation error or missing Idempotency-Key"},
            401: {"model": ErrorResponse, "description": "Authentication failure"},
            403: {"model": ErrorResponse, "description": "Insufficient scope (requires compliance:review)"},
            404: {"model": ErrorResponse, "description": "Review item not found (or foreign tenant access)"},
            409: {"model": ErrorResponse, "description": "Idempotency conflict (key reused with different annotation)"},
        },
    )
    def annotate(
        brief_id: str,
        body: AnnotationRequest,
        request: Request,
        authorization: str | None = Header(default=None, description="Bearer capability token"),
        x_tenant_slug: str | None = Header(default=None, alias="X-Tenant-Slug", description="Tenant slug context"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID", description="Alternative tenant identifier"),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", description="Idempotency key"),
        x_request_id: str | None = Header(default=None, alias="X-Request-ID", description="Request tracing identifier"),
    ):
        tenant_context = resolve_tenant(x_tenant_slug, x_tenant_id)
        principal = principal_for(authorization, tenant_context, "compliance:review")
        idempotency_key = require_idempotency_key(idempotency_key)
        req_id = x_request_id or getattr(request.state, "request_id", uuid4().hex)

        try:
            review = service.annotate(
                principal.tenant_id,
                brief_id,
                principal.key_id,
                body.annotation,
                req_id,
                principal.key_id,
                idempotency_key=idempotency_key,
            )
        except IdempotencyConflict:
            raise HTTPException(status_code=409, detail="idempotency key conflict")

        if review is None:
            raise HTTPException(status_code=404, detail="review not found")
        return review

    return app


app = create_app()
