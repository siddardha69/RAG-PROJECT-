from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Schema for query requests."""

    question: str = Field(..., min_length=5, max_length=1000)
    repository_id: Optional[UUID] = None
    include_recommendations: bool = True


class ArtifactCitation(BaseModel):
    """Schema representing an artifact citation/reference in query answers."""

    artifact_id: UUID
    artifact_type: str
    title: str
    url: Optional[str] = None
    author: str
    created_at: datetime
    relevance_score: float

    class Config:
        from_attributes = True


class QueryResponse(BaseModel):
    """Schema representing query results response."""

    question: str
    answer: str
    citations: List[ArtifactCitation]
    timeline_summary: List[dict]
    recommendation: Optional[str] = None
    confidence: float
    latency_ms: int
    query_log_id: UUID
