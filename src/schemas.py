from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class Route(str, Enum):
    KNOWLEDGE = "knowledge"
    ANALYSIS = "analysis"
    REPORT = "report"
    CHANGE = "change"
    BLOCKED = "blocked"


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    session_id: str = Field(default="default", min_length=1, max_length=100)


class ApprovalRequest(BaseModel):
    approval_id: str
    approved: bool
    reviewer: str = Field(default="anonymous", max_length=100)


class ContextItem(BaseModel):
    doc_id: str
    text: str
    score: float = 0.0
    source: str = ""


class TraceItem(BaseModel):
    step: str
    input: Any = None
    output: Any = None
    elapsed_ms: float = 0.0


class RouteDecision(BaseModel):
    route: Route
    reason: str
    tools: list[str] = Field(default_factory=list)


class AnswerDraft(BaseModel):
    verdict: str = Field(description="PASS, CONDITIONAL PASS, FAIL, INFO 중 하나")
    summary: str
    evidence: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    uncertainty: str = ""

    @field_validator("evidence", "recommendations", mode="before")
    @classmethod
    def _coerce_bullet_string(cls, value: Any) -> Any:
        """구조화 출력이 리스트 대신 '- 항목' 형태의 문자열로 오는 경우를 리스트로 보정한다."""
        if isinstance(value, str):
            return [
                line.strip().lstrip("-*").strip()
                for line in value.splitlines()
                if line.strip()
            ]
        return value


class QueryResponse(BaseModel):
    answer: str
    contexts: list[ContextItem] = Field(default_factory=list)
    trace: list[TraceItem] = Field(default_factory=list)
    route: Route = Route.KNOWLEDGE
    tools_used: list[str] = Field(default_factory=list)
    status: str = "completed"
    approval_id: str | None = None


class HealthResponse(BaseModel):
    status: str
    mode: str
    version: str

