from datetime import datetime, timezone
from typing import Dict, List, Optional
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.retrieval.vector_retriever import RetrievedChunk, VectorRetriever
from app.services.retrieval.graph_retriever import GraphRetriever

logger = get_logger(__name__)


class HybridRetriever:
    """Orchestrates hybrid GraphRAG retrieval merging semantic search with graph neighborhood discovery."""

    def __init__(
        self,
        vector_retriever: VectorRetriever,
        graph_retriever: GraphRetriever,
        settings: Optional[Settings] = None,
    ):
        self.vector_retriever = vector_retriever
        self.graph_retriever = graph_retriever
        self.settings = settings or get_settings()

    async def retrieve(
        self,
        query: str,
        repository_id: Optional[str] = None,
    ) -> List[RetrievedChunk]:
        """
        Executes the 6-step GraphRAG retrieval pipeline:
        1. Vector search
        2. Graph expansion
        3. Merge
        4. Deduplicate
        5. Custom Rerank
        6. Return Top K
        """
        logger.info("Starting hybrid retrieval", query=query, repository_id=repository_id)

        # Step 1: Vector Search
        vector_chunks = await self.vector_retriever.search(
            query=query,
            repository_id=repository_id,
            limit=self.settings.retrieval_top_k,
        )
        logger.debug("Step 1: Vector search complete", count=len(vector_chunks))

        # Step 2: Graph Expansion
        anchor_ids = [str(c.artifact_id) for c in vector_chunks]
        graph_chunks = await self.graph_retriever.retrieve(
            query=query,
            anchor_artifact_ids=anchor_ids,
        )
        logger.debug("Step 2: Graph expansion complete", count=len(graph_chunks))

        # Step 3: Merge Results
        merged = vector_chunks + graph_chunks
        logger.debug("Step 3: Merged chunks", total=len(merged))

        # Step 4: Deduplicate
        # Keep the one with the highest vector score
        deduped: Dict[str, RetrievedChunk] = {}
        for chunk in merged:
            key = str(chunk.artifact_id)
            if key not in deduped:
                deduped[key] = chunk
            else:
                if chunk.score > deduped[key].score:
                    deduped[key] = chunk
        deduped_list = list(deduped.values())
        logger.debug("Step 4: Deduplicated chunks", count=len(deduped_list))

        # Step 5: Rerank
        # final_score = (0.6 * vector_score) + (0.3 * recency_score) + (0.1 * type_score)
        now = datetime.utcnow()
        scored_chunks = []
        for chunk in deduped_list:
            # Vector score
            vector_score = chunk.score

            # Recency score calculation
            # Remove timezone if present
            chunk_date = chunk.created_at
            if chunk_date.tzinfo is not None:
                chunk_date = chunk_date.replace(tzinfo=None)
            age_days = (now - chunk_date).days

            if age_days < 30:
                recency_score = 1.0
            elif age_days < 90:
                recency_score = 0.8
            elif age_days < 365:
                recency_score = 0.6
            else:
                recency_score = 0.4

            # Type score mapping
            type_lower = chunk.artifact_type.lower()
            if type_lower in ("adr", "decision"):
                type_score = 1.0
            elif type_lower in ("pull_request", "pr"):
                type_score = 0.9
            elif type_lower in ("issue", "bug"):
                type_score = 0.8
            elif type_lower in ("commit", "push"):
                type_score = 0.6
            else:
                type_score = 0.5

            final_score = (0.6 * vector_score) + (0.3 * recency_score) + (0.1 * type_score)
            chunk.score = final_score
            scored_chunks.append(chunk)

        # Sort descending by final score
        scored_chunks.sort(key=lambda x: x.score, reverse=True)

        # Step 6: Return Top K
        final_top_k = scored_chunks[: self.settings.final_top_k]
        logger.info("Step 6: Hybrid retrieval complete", returned_count=len(final_top_k))
        return final_top_k
