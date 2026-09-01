from __future__ import annotations

import hashlib
import re
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

from .auth import AuthenticationError, authenticate, require_scope
from .database import Database, IdempotencyConflict
from .schemas import AnnotationRequest, BriefRequest
from .service import ComplianceService


_RAW_ID = re.compile(r"(?<!\d)\d{11}(?!\d)")


def create_app(db_path: str | Path = "./data/shadowspark.db", fixture_dir: str | Path = "vendor") -> FastAPI:
    app = FastAPI(title="ShadowSpark Compliance Review V1", version="1.0.0")
    service = ComplianceService(Database(db_path), fixture_dir)

    def principal_for(authorization: str | None, scope: str):
        try:
            principal = authenticate(authorization)
            require_scope(principal, scope)
            return principal
        except AuthenticationError:
            raise HTTPException(status_code=401, detail="authentication failed")
        except PermissionError:
            raise HTTPException(status_code=403, detail="scope required")

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.post("/v1/compliance-review-brief", status_code=status.HTTP_201_CREATED)
    def create_brief(body: BriefRequest, request: Request, authorization: str | None = Header(default=None), idempotency_key: str | None = Header(default=None)):
        principal = principal_for(authorization, "compliance:read")
        if not idempotency_key or len(idempotency_key) > 128:
            raise HTTPException(status_code=400, detail="Idempotency-Key required")
        if _RAW_ID.search(body.exception_id):
            raise HTTPException(status_code=422, detail="raw identifier not accepted")
        if body.exception_id.partition(":")[0].startswith("tenant_") and not body.exception_id.startswith(principal.tenant_id + ":"):
            raise HTTPException(status_code=404, detail="exception not found")
        try:
            result = service.create_brief(principal.tenant_id, body.exception_id, idempotency_key,
                                          request.headers.get("X-Request-ID", uuid4().hex), principal.key_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="exception not found")
        except IdempotencyConflict:
            raise HTTPException(status_code=409, detail="idempotency key conflict")
        if result["output"].get("status") == "blocked":
            if "LLM06:2026" in result["output"].get("brief", {}).get("risk_flags", []):
                return JSONResponse(status_code=429, content=result)
            return result
        return result

    @app.get("/v1/review-queue/{brief_id}")
    def get_review(brief_id: str, authorization: str | None = Header(default=None)):
        principal = principal_for(authorization, "compliance:read")
        review = service.get_review(principal.tenant_id, brief_id)
        if review is None:
            raise HTTPException(status_code=404, detail="review not found")
        return review

    @app.post("/v1/review-queue/{brief_id}/annotations")
    def annotate(brief_id: str, body: AnnotationRequest, request: Request, authorization: str | None = Header(default=None)):
        principal = principal_for(authorization, "compliance:review")
        review = service.annotate(principal.tenant_id, brief_id, principal.key_id, body.annotation,
                                  request.headers.get("X-Request-ID", uuid4().hex), principal.key_id)
        if review is None:
            raise HTTPException(status_code=404, detail="review not found")
        return review

    return app


app = create_app()
