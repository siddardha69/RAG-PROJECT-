import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, UUID
from sqlalchemy.orm import relationship
from app.database.postgres import Base


class Repository(Base):
    """Postgres model representing an ingested GitHub repository."""

    __tablename__ = "repositories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    github_url = Column(String, unique=True, nullable=False)
    owner = Column(String, nullable=False)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    status = Column(
        String,
        nullable=False,
        default="pending",
    )  # enum: pending, ingesting, completed, failed
    artifact_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    last_ingested_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)

    # Relationships
    artifacts = relationship(
        "Artifact",
        back_populates="repository",
        cascade="all, delete-orphan",
    )
