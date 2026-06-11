from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class RecommendationResponse(BaseModel):
    """Schema representing a decision risk recommendation response."""

    id: UUID
    artifact_id: UUID
    original_assumption: str
    current_risk: str
    recommendation: str  # keep, revisit, replace
    confidence: float
    created_at: datetime

    class Config:
        from_attributes = True
