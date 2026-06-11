from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel


class TimelineEvent(BaseModel):
    """Schema representing an individual event on a decision timeline."""

    event_date: datetime
    event_type: str
    title: str
    description: str
    artifact_id: UUID
    artifact_type: str
    author: str
    url: Optional[str] = None

    class Config:
        from_attributes = True


class TimelineResponse(BaseModel):
    """Schema representing a full chronological timeline with narrative summary."""

    artifact_id: UUID
    events: List[TimelineEvent]
    narrative: str
