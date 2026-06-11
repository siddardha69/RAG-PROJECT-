import uuid
from datetime import datetime
from sqlalchemy import Column, Text, Integer, DateTime, ForeignKey, String, UUID, JSON
from sqlalchemy.dialects.postgresql import JSONB
from app.database.postgres import Base


class QueryLog(Base):
    """Postgres model representing a log of user queries and the generated answers."""

    __tablename__ = "query_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question = Column(Text, nullable=False)
    repository_id = Column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="SET NULL"),
        nullable=True,
    )
    answer = Column(Text, nullable=False)
    artifacts_used = Column(JSONB().with_variant(JSON, "sqlite"), nullable=False, default=list)  # list of artifact_id dicts
    retrieval_strategy = Column(String, nullable=False, default="hybrid")
    latency_ms = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
