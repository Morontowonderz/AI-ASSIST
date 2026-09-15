from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    detail: str = Field(..., description="Human-readable error description")


class BriefRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    exception_id: str = Field(..., min_length=1, max_length=128, description="Target exception identifier (e.g. ex_a_021)")
    tenant_id: str | None = Field(default=None, min_length=1, max_length=64, description="Optional tenant slug matching the request tenant header")


class AnnotationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    annotation: str = Field(..., min_length=1, max_length=2000, description="Operator review annotation notes")


class AnnotationItem(BaseModel):
    annotation_id: str = Field(..., description="Unique annotation identifier")
    operator_id: str = Field(..., description="Authenticated operator identity")
    annotation: str = Field(..., description="Operator annotation text")
    created_at: str = Field(..., description="ISO 8601 UTC creation timestamp")


class ReviewQueueResponse(BaseModel):
    brief_id: str = Field(..., description="Brief identifier")
    tenant_id: str = Field(..., description="Tenant owner of the review item")
    exception_id: str = Field(..., description="Associated exception identifier")
    output: dict[str, Any] = Field(..., description="Stored brief output")
    queue_state: str = Field(..., description="Current queue status (pending_review or annotated)")
    sor_status_unchanged: bool = Field(..., description="System of Record immutability flag")
    annotations: list[AnnotationItem] = Field(default_factory=list, description="Chronological operator annotations")
    created_at: str = Field(..., description="Queue entry creation timestamp")
    updated_at: str = Field(..., description="Queue entry last updated timestamp")


class BriefResponse(BaseModel):
    brief_id: str | None = Field(None, description="Generated brief identifier (None if blocked)")
    output: dict[str, Any] = Field(..., description="Deterministic compliance brief output payload")
    tool_trace: list[Any] = Field(default_factory=list, description="Tool execution trace")
    replayed: bool = Field(False, description="True if response was served from an idempotent cache")
