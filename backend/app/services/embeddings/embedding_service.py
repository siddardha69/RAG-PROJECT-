import asyncio
import uuid
from typing import List, Optional
import google.generativeai as genai
from qdrant_client.http import models as qmodels
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.database.qdrant_client import QdrantClientManager
from app.services.chunking.chunking_engine import Chunk

logger = get_logger(__name__)


class EmbeddingService:
    """Manages text embeddings generation and storing in Qdrant using Gemini API."""

    def __init__(
        self,
        qdrant_manager: QdrantClientManager,
        settings: Optional[Settings] = None,
    ):
        self.settings = settings or get_settings()
        self.qdrant_manager = qdrant_manager
        # Configure Gemini API
        genai.configure(api_key=self.settings.gemini_api_key)

    def encode_query(self, text: str) -> List[float]:
        """Synchronously encode query text to vector using Gemini API."""
        try:
            # If default key or missing, return dummy zeros for testing/fallback
            if not self.settings.gemini_api_key or self.settings.gemini_api_key == "your_gemini_key_here":
                import numpy as np
                return np.zeros((768,)).tolist()

            result = genai.embed_content(
                model="models/text-embedding-004",
                contents=text,
                task_type="retrieval_query",
            )
            return result['embedding']
        except Exception as e:
            logger.error("Failed to generate embedding from Gemini", error=str(e))
            raise

    async def embed_text(self, text: str) -> List[float]:
        """Asynchronously encode text using asyncio.to_thread."""
        return await asyncio.to_thread(self.encode_query, text)

    async def embed_and_store_chunks(
        self,
        chunks: List[Chunk],
        repository_name: str,
    ) -> List[str]:
        """
        Batch embeds chunk texts, maps them to Qdrant PointStructs,
        and upserts them into the Qdrant index.
        """
        if not chunks:
            return []

        # 1. Batch encode texts
        texts = [chunk.text for chunk in chunks]
        logger.info(
            "Batch embedding chunks using Gemini",
            count=len(chunks),
        )

        def _batch_embed():
            if not self.settings.gemini_api_key or self.settings.gemini_api_key == "your_gemini_key_here":
                import numpy as np
                return np.zeros((len(texts), 768)).tolist()

            result = genai.embed_content(
                model="models/text-embedding-004",
                contents=texts,
                task_type="retrieval_document",
            )
            return result['embedding']

        # Run encoding in a thread pool to avoid blocking async loop
        embeddings = await asyncio.to_thread(_batch_embed)

        # 2. Build PointStruct list
        points = []
        point_ids = []
        for chunk, embedding in zip(chunks, embeddings):
            # Qdrant requires UUIDs or integers.
            # If the chunk already has a valid chunk_id UUID, we use it, otherwise generate one.
            point_id = chunk.chunk_id or str(uuid.uuid4())
            point_ids.append(point_id)

            payload = {
                "artifact_id": str(chunk.artifact_id),
                "artifact_type": chunk.artifact_type,
                "repository_id": str(chunk.metadata.get("repository_id", "")),
                "repository_name": repository_name,
                "chunk_type": chunk.chunk_type,
                "author": chunk.author,
                "created_at": chunk.created_at.isoformat(),
                "url": chunk.url,
                "text_preview": chunk.text[:200],
            }

            points.append(
                qmodels.PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload=payload,
                )
            )

        # 3. Ensure collection exists
        await self.qdrant_manager.ensure_collection(
            collection_name=self.settings.qdrant_collection_name,
            vector_size=self.settings.vector_dim,
        )

        # 4. Upsert to Qdrant
        await self.qdrant_manager.upsert_points(
            collection_name=self.settings.qdrant_collection_name,
            points=points,
        )

        return point_ids
