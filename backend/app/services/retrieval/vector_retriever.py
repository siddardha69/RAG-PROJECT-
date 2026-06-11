from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel
from qdrant_client.http import models as qmodels
from app.core.config import Settings, get_settings
from app.database.qdrant_client import QdrantClientManager
from app.services.embeddings.embedding_service import EmbeddingService


class RetrievedChunk(BaseModel):
    """Data class for a chunk returned by retrievers with semantic and custom score properties."""

    artifact_id: UUID
    artifact_type: str
    chunk_type: str
    text: str
    score: float
    author: str
    created_at: datetime
    url: Optional[str] = None
    metadata: Optional[dict] = None


class VectorRetriever:
    """Handles vector similarity search in Qdrant database."""

    def __init__(
        self,
        qdrant_manager: QdrantClientManager,
        embedding_service: EmbeddingService,
        settings: Optional[Settings] = None,
    ):
        self.qdrant_manager = qdrant_manager
        self.embedding_service = embedding_service
        self.settings = settings or get_settings()

    async def search(
        self,
        query: str,
        repository_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[RetrievedChunk]:
        """Encode query, create filters, search Qdrant and return mapping to RetrievedChunk."""
        # 1. Encode query
        query_vector = await self.embedding_service.embed_text(query)

        # 2. Build filter condition
        filter_cond = None
        if repository_id:
            filter_cond = qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="repository_id",
                        match=qmodels.MatchValue(value=str(repository_id)),
                    )
                ]
            )

        # 3. Search Qdrant
        points = await self.qdrant_manager.search(
            collection_name=self.settings.qdrant_collection_name,
            query_vector=query_vector,
            limit=limit,
            filter_conditions=filter_cond,
        )

        # 4. Map results
        results = []
        for point in points:
            payload = point.payload or {}
            # Fallback to current time if created_at is missing or invalid
            created_at_val = datetime.utcnow()
            if payload.get("created_at"):
                try:
                    created_at_val = datetime.fromisoformat(payload["created_at"])
                except ValueError:
                    pass

            results.append(
                RetrievedChunk(
                    artifact_id=UUID(payload["artifact_id"]),
                    artifact_type=payload.get("artifact_type", "issue"),
                    chunk_type=payload.get("chunk_type", "full"),
                    text=payload.get("text_preview", ""),  # Fallback to preview, or search text
                    score=point.score,
                    author=payload.get("author", "unknown"),
                    created_at=created_at_val,
                    url=payload.get("url"),
                    metadata=payload,
                )
            )
        return results
