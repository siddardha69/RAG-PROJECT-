from typing import AsyncGenerator
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.postgres import get_db
from app.core.config import get_settings, Settings
from app.database.qdrant_client import QdrantClientManager
from app.database.neo4j_client import Neo4jClientManager
from app.services.ingestion.github_client import GitHubClient
from app.services.ingestion.artifact_normalizer import ArtifactNormalizer
from app.services.chunking.chunking_engine import ChunkingEngine
from app.services.embeddings.embedding_service import EmbeddingService
from app.services.graph.graph_builder import GraphBuilder
from app.services.graph.graph_traversal import GraphTraversal
from app.services.entity_extraction.entity_extractor import EntityExtractor
from app.services.ingestion.ingestion_service import IngestionService
from app.services.retrieval.vector_retriever import VectorRetriever
from app.services.retrieval.graph_retriever import GraphRetriever
from app.services.retrieval.hybrid_retriever import HybridRetriever
from app.services.llm.synthesis_service import SynthesisService
from app.services.timeline.timeline_service import TimelineService
from app.services.recommendations.recommendation_service import RecommendationService


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield database session."""
    async for session in get_db():
        yield session


def get_github_client(settings: Settings = Depends(get_settings)) -> GitHubClient:
    """Return authenticated GitHub client."""
    return GitHubClient(settings.github_token)


def get_qdrant_manager() -> QdrantClientManager:
    """Return QdrantClientManager singleton helper."""
    return QdrantClientManager()


def get_neo4j_manager() -> Neo4jClientManager:
    """Return Neo4jClientManager singleton helper."""
    return Neo4jClientManager()


def get_embedding_service(
    qdrant_manager: QdrantClientManager = Depends(get_qdrant_manager),
    settings: Settings = Depends(get_settings),
) -> EmbeddingService:
    """Return EmbeddingService."""
    return EmbeddingService(qdrant_manager, settings)


def get_graph_builder(
    neo4j_manager: Neo4jClientManager = Depends(get_neo4j_manager),
) -> GraphBuilder:
    """Return GraphBuilder."""
    return GraphBuilder(neo4j_manager)


def get_graph_traversal(
    neo4j_manager: Neo4jClientManager = Depends(get_neo4j_manager),
) -> GraphTraversal:
    """Return GraphTraversal."""
    return GraphTraversal(neo4j_manager)


def get_entity_extractor() -> EntityExtractor:
    """Return EntityExtractor singleton."""
    return EntityExtractor()


def get_ingestion_service(
    db: AsyncSession = Depends(get_db_session),
    github_client: GitHubClient = Depends(get_github_client),
    settings: Settings = Depends(get_settings),
) -> IngestionService:
    """Return IngestionService fully configured."""
    normalizer = ArtifactNormalizer()
    chunking_engine = ChunkingEngine()
    qdrant_manager = get_qdrant_manager()
    embedding_service = EmbeddingService(qdrant_manager, settings)
    neo4j_manager = get_neo4j_manager()
    graph_builder = GraphBuilder(neo4j_manager)
    entity_extractor = EntityExtractor()

    return IngestionService(
        github_client=github_client,
        normalizer=normalizer,
        chunking_engine=chunking_engine,
        embedding_service=embedding_service,
        graph_builder=graph_builder,
        entity_extractor=entity_extractor,
        db=db,
    )


def get_vector_retriever(
    qdrant_manager: QdrantClientManager = Depends(get_qdrant_manager),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    settings: Settings = Depends(get_settings),
) -> VectorRetriever:
    """Return VectorRetriever."""
    return VectorRetriever(qdrant_manager, embedding_service, settings)


def get_graph_retriever(
    graph_traversal: GraphTraversal = Depends(get_graph_traversal),
    entity_extractor: EntityExtractor = Depends(get_entity_extractor),
) -> GraphRetriever:
    """Return GraphRetriever."""
    return GraphRetriever(graph_traversal, entity_extractor)


def get_hybrid_retriever(
    vector_retriever: VectorRetriever = Depends(get_vector_retriever),
    graph_retriever: GraphRetriever = Depends(get_graph_retriever),
    settings: Settings = Depends(get_settings),
) -> HybridRetriever:
    """Return HybridRetriever."""
    return HybridRetriever(vector_retriever, graph_retriever, settings)


def get_synthesis_service(
    settings: Settings = Depends(get_settings),
) -> SynthesisService:
    """Return SynthesisService."""
    return SynthesisService(settings)


def get_timeline_service(
    db: AsyncSession = Depends(get_db_session),
    graph_traversal: GraphTraversal = Depends(get_graph_traversal),
) -> TimelineService:
    """Return TimelineService."""
    return TimelineService(db, graph_traversal)


def get_recommendation_service(
    db: AsyncSession = Depends(get_db_session),
    hybrid_retriever: HybridRetriever = Depends(get_hybrid_retriever),
    synthesis_service: SynthesisService = Depends(get_synthesis_service),
) -> RecommendationService:
    """Return RecommendationService."""
    return RecommendationService(db, hybrid_retriever, synthesis_service)
