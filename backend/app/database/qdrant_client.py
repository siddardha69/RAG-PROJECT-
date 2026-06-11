from typing import Any, Dict, List, Optional
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models
from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


class QdrantClientManager:
    """Manages connection and operations with Qdrant vector database."""

    _instance: Optional[AsyncQdrantClient] = None

    @classmethod
    def get_client(cls) -> AsyncQdrantClient:
        """Get or initialize singleton AsyncQdrantClient."""
        if cls._instance is None:
            cls._instance = AsyncQdrantClient(
                host=settings.qdrant_host,
                port=settings.qdrant_port,
            )
        return cls._instance

    @classmethod
    async def close(cls) -> None:
        """Close client connection."""
        if cls._instance is not None:
            await cls._instance.close()
            cls._instance = None

    def __init__(self) -> None:
        self.client = self.get_client()

    async def ensure_collection(self, collection_name: str, vector_size: int) -> None:
        """Ensure that the target collection exists in Qdrant."""
        try:
            collections_response = await self.client.get_collections()
            existing = [c.name for c in collections_response.collections]
            if collection_name not in existing:
                logger.info(
                    "Creating Qdrant collection",
                    collection=collection_name,
                    size=vector_size,
                )
                await self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=models.VectorParams(
                        size=vector_size,
                        distance=models.Distance.COSINE,
                    ),
                )
            else:
                logger.debug("Qdrant collection already exists", collection=collection_name)
        except Exception as e:
            logger.error("Failed to ensure Qdrant collection", error=str(e))
            raise

    async def upsert_points(
        self,
        collection_name: str,
        points: List[models.PointStruct],
    ) -> None:
        """Upsert a list of point vectors into the collection."""
        try:
            await self.client.upsert(
                collection_name=collection_name,
                points=points,
            )
            logger.debug(
                "Upserted vectors to Qdrant",
                collection=collection_name,
                count=len(points),
            )
        except Exception as e:
            logger.error("Failed to upsert points to Qdrant", error=str(e))
            raise

    async def search(
        self,
        collection_name: str,
        query_vector: List[float],
        limit: int = 10,
        filter_conditions: Optional[models.Filter] = None,
    ) -> List[models.ScoredPoint]:
        """Perform semantic search on the Qdrant collection."""
        try:
            results = await self.client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                query_filter=filter_conditions,
                limit=limit,
            )
            return results
        except Exception as e:
            logger.error("Failed to search Qdrant", error=str(e))
            raise
