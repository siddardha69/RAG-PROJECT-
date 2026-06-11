import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, UUID, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.database.postgres import Base


class Artifact(Base):
    """Postgres model representing a singular ingested GitHub artifact (Commit, PR, Issue, ADR)."""

    __tablename__ = "artifacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
    )
    artifact_type = Column(
        String,
        nullable=False,
    )  # enum: issue, pull_request, commit, adr
    external_id = Column(String, nullable=False)
    title = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    author = Column(String, nullable=False)
    url = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False)
    merged_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    labels = Column(JSONB().with_variant(JSON, "sqlite"), nullable=False, default=list)
    metadata_fields = Column(
        JSONB().with_variant(JSON, "sqlite"),
        name="metadata",
        nullable=False,
        default=dict,
    )  # Name it metadata_fields to avoid conflict with Base.metadata
    qdrant_ids = Column(JSONB().with_variant(JSON, "sqlite"), nullable=False, default=list)
    ingested_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    repository = relationship("Repository", back_populates="artifacts")
    recommendations = relationship(
        "Recommendation",
        back_populates="artifact",
        cascade="all, delete-orphan",
    )
