from datetime import datetime
from typing import List, Optional
from uuid import UUID
from sqlalchemy import select
from app.database.postgres import AsyncSessionLocal
from app.models.artifact import Artifact
from app.services.entity_extraction.entity_extractor import EntityExtractor
from app.services.graph.graph_traversal import GraphTraversal
from app.services.retrieval.vector_retriever import RetrievedChunk


class GraphRetriever:
    """Handles graph-based retrieval using Neo4j traversals."""

    def __init__(
        self,
        graph_traversal: GraphTraversal,
        entity_extractor: EntityExtractor,
    ):
        self.graph_traversal = graph_traversal
        self.entity_extractor = entity_extractor

    async def retrieve(
        self,
        query: str,
        anchor_artifact_ids: List[str],
    ) -> List[RetrievedChunk]:
        """
        Traverses the graph around anchor IDs and queries technology contextualization,
        then resolves matched artifacts from Postgres.
        """
        # 1. Extract entities and technologies from query
        extracted = self.entity_extractor.extract(query)

        # 2. Get technology-related nodes
        tech_matched_refs = []
        if extracted.technologies:
            tech_matched_refs = await self.graph_traversal.find_technologies_in_context(
                extracted.technologies
            )

        # 3. Traverse neighborhood of vector-anchored nodes
        neighborhood_refs = []
        if anchor_artifact_ids:
            neighborhood_refs = await self.graph_traversal.find_decision_neighborhood(
                anchor_artifact_ids,
                depth=2,
            )

        # Collect unique artifact IDs to resolve
        all_ids = set()
        for ref in tech_matched_refs:
            all_ids.add(ref["id"])
        for ref in neighborhood_refs:
            all_ids.add(ref["id"])

        # Filter out anchors to avoid duplicate work if already retrieved in vector search
        # (Though HybridRetriever handles deduplication, we fetch them if not already resolved)
        uuid_list = []
        for aid in all_ids:
            try:
                uuid_list.append(UUID(aid))
            except ValueError:
                # Might be a technology name (e.g. "Redis") in the node list, skip
                continue

        if not uuid_list:
            return []

        # 4. Resolve artifacts and full bodies from Postgres
        results = []
        async with AsyncSessionLocal() as session:
            stmt = select(Artifact).where(Artifact.id.in_(uuid_list))
            db_res = await session.execute(stmt)
            artifacts = db_res.scalars().all()

            for art in artifacts:
                results.append(
                    RetrievedChunk(
                        artifact_id=art.id,
                        artifact_type=art.artifact_type,
                        chunk_type="full",
                        text=art.body,
                        score=0.8,  # Default graph match relevance score
                        author=art.author,
                        created_at=art.created_at,
                        url=art.url,
                        metadata=art.metadata_fields,
                    )
                )

        return results
