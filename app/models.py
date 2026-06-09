from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


SourceKind = Literal["document", "readme", "course_note", "product_note", "report"]


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:10]}"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SourceInput(BaseModel):
    source_id: str | None = Field(default=None, description="Stable source id. Generated when omitted.")
    title: str
    kind: SourceKind = "document"
    body: str = Field(min_length=20)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourceRecord(SourceInput):
    source_id: str
    created_at: str = Field(default_factory=utc_now)


class SourceIngestResponse(BaseModel):
    source_id: str
    title: str
    kind: SourceKind
    char_count: int


class RunRequest(BaseModel):
    objective: str = Field(
        default="Create source-grounded content artifacts for a compact portfolio workflow."
    )
    audience: str = "AI product and engineering reviewers"
    tone: str = "concise, evidence-first"
    source_ids: list[str] | None = None
    sources: list[SourceInput] | None = None


class ArtifactManifest(BaseModel):
    run_id: str
    status: Literal["ok", "fallback"]
    artifact_paths: dict[str, str]
    validation_errors: list[str]
    source_count: int


class RunResponse(BaseModel):
    run_id: str
    status: Literal["ok", "fallback"]
    artifacts: dict[str, str]
    validation_errors: list[str]
    source_registry: list[dict[str, Any]]


class RetrievalHit(BaseModel):
    source_id: str
    title: str
    score: float
    reasons: dict[str, float]
    excerpt: str

