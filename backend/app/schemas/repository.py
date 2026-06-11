import re
from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator


class IngestRepositoryRequest(BaseModel):
    """Schema for repository ingestion requests."""

    github_url: str = Field(
        ...,
        description="Full URL of the GitHub repository (e.g. https://github.com/owner/repo)",
    )
    branch: str = Field(default="main", description="Target branch to ingest")

    @field_validator("github_url")
    @classmethod
    def validate_github_url(cls, v: str) -> str:
        """Validate github url matches github.com/owner/repo pattern."""
        pattern = r"^https?://(www\.)?github\.com/[\w\-\.]+/[\w\-\.]+/?$"
        if not re.match(pattern, v):
            raise ValueError(
                "Invalid GitHub repository URL. Must be in format 'https://github.com/owner/repo'"
            )
        return v


class RepositoryResponse(BaseModel):
    """Schema for repository details response."""

    id: UUID
    github_url: str
    owner: str
    name: str
    status: str
    artifact_count: int
    created_at: datetime
    last_ingested_at: Optional[datetime] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class RepositoryListResponse(BaseModel):
    """Schema for repository list response."""

    repositories: List[RepositoryResponse]
    total: int
