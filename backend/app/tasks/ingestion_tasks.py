import asyncio
from uuid import UUID
from celery.utils.log import get_task_logger
from app.tasks.celery_app import celery_app
from app.database.postgres import AsyncSessionLocal
from app.database.qdrant_client import QdrantClientManager
from app.database.neo4j_client import Neo4jClientManager
from app.services.ingestion.github_client import GitHubClient
from app.services.ingestion.artifact_normalizer import ArtifactNormalizer
from app.services.chunking.chunking_engine import ChunkingEngine
from app.services.embeddings.embedding_service import EmbeddingService
from app.services.graph.graph_builder import GraphBuilder
from app.services.entity_extraction.entity_extractor import EntityExtractor
from app.services.ingestion.ingestion_service import IngestionService
from app.core.config import get_settings
from app.models.repository import Repository
from sqlalchemy import select

logger = get_task_logger(__name__)


@celery_app.task(bind=True, max_retries=3, name="ingest_repository")
def ingest_repository_task(self, github_url: str, repository_id: str) -> dict:
    """
    Celery background task running the full repository ingestion pipeline.
    Instantiates services and executes async ingestion inside asyncio.run().
    """
    logger.info(f"Starting ingestion task for repository ID {repository_id}, URL: {github_url}")

    async def _run_ingestion():
        settings = get_settings()
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
        from app.database.postgres import UniqueNameConnection
        local_engine = create_async_engine(
            settings.database_url,
            echo=False,
            future=True,
            connect_args={
                "connection_class": UniqueNameConnection,
            }
        )
        local_sessionmaker = async_sessionmaker(
            bind=local_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
        db = local_sessionmaker()
        
        # Ensure we close any stale connections that might have been created in a previous task/loop
        await QdrantClientManager.close()
        await Neo4jClientManager.close_driver()
        
        try:
            github_client = GitHubClient(settings.github_token)
            normalizer = ArtifactNormalizer()
            chunking_engine = ChunkingEngine()
            qdrant_manager = QdrantClientManager()
            embedding_service = EmbeddingService(qdrant_manager, settings)
            neo4j_manager = Neo4jClientManager()
            graph_builder = GraphBuilder(neo4j_manager)
            entity_extractor = EntityExtractor()

            service = IngestionService(
                github_client=github_client,
                normalizer=normalizer,
                chunking_engine=chunking_engine,
                embedding_service=embedding_service,
                graph_builder=graph_builder,
                entity_extractor=entity_extractor,
                db=db,
            )

            await service.ingest_repository(github_url)

            # Retrieve final artifact count
            stmt = select(Repository).where(Repository.id == UUID(repository_id))
            res = await db.execute(stmt)
            repo = res.scalar_one_or_none()
            count = repo.artifact_count if repo else 0

            return {"status": "completed", "artifact_count": count}
        except Exception as e:
            logger.error(f"Error executing ingestion inside task: {str(e)}")
            raise e
        finally:
            await db.close()
            await local_engine.dispose()
            # Clean up current clients as well to prevent next task in this process from getting closed/stale client
            await QdrantClientManager.close()
            await Neo4jClientManager.close_driver()

    try:
        return asyncio.run(_run_ingestion())
    except Exception as exc:
        countdown = 2**self.request.retries
        logger.warning(f"Ingestion task failed. Retrying in {countdown}s... Error: {str(exc)}")
        raise self.retry(exc=exc, countdown=countdown)
