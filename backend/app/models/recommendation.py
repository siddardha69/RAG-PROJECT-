import uuid
from datetime import datetime
from sqlalchemy import Column, Text, Float, DateTime, ForeignKey, UUID
from sqlalchemy.orm import relationship
from app.database.postgres import Base


class Recommendation(Base):
    """Postgres model representing a decision risk recommendation."""

    __tablename__ = "recommendations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    artifact_id = Column(
        UUID(as_uuid=True),
        ForeignKey("artifacts.id", ondelete="CASCADE"),
        nullable=False,
    )
    original_assumption = Column(Text, nullable=False)
    current_risk = Column(Text, nullable=False)
    recommendation = Column(Text, nullable=False)  # keep, revisit, replace
    confidence = Column(Float, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    artifact = relationship("Artifact", back_populates="recommendations")
