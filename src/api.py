from __future__ import annotations

from fastapi import FastAPI

from . import __version__
from .agent import build_agent
from .config import settings
from .schemas import ApprovalRequest, HealthResponse, QueryRequest, QueryResponse

app = FastAPI(
    title="Performance Station AI",
    description="성능검증 Agentic RAG Assistant",
    version=__version__,
)
agent = build_agent()


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        mode="bedrock" if settings.use_bedrock else "offline-demo",
        version=__version__,
    )


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse:
    return agent.query(request.question, request.session_id)


@app.post("/approve", response_model=QueryResponse)
def approve(request: ApprovalRequest) -> QueryResponse:
    return agent.approve(request.approval_id, request.approved, request.reviewer)

