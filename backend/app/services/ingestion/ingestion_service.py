from datetime import datetime
from typing import Dict, List, Tuple
from uuid import UUID, uuid4
import re
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import IngestionError
from app.core.logging import get_logger
from app.models.repository import Repository
from app.models.artifact import Artifact
from app.services.ingestion.github_client import GitHubClient
from app.services.ingestion.artifact_normalizer import ArtifactNormalizer
from app.services.chunking.chunking_engine import ChunkingEngine, Chunk
from app.services.embeddings.embedding_service import EmbeddingService
from app.services.graph.graph_builder import GraphBuilder
from app.services.entity_extraction.entity_extractor import EntityExtractor, ExtractedEntities

logger = get_logger(__name__)


class IngestionService:
    """Orchestrates end-to-end repository ingestion into SQL, Neo4j, and Qdrant."""

    def __init__(
        self,
        github_client: GitHubClient,
        normalizer: ArtifactNormalizer,
        chunking_engine: ChunkingEngine,
        embedding_service: EmbeddingService,
        graph_builder: GraphBuilder,
        entity_extractor: EntityExtractor,
        db: AsyncSession,
    ):
        self.github_client = github_client
        self.normalizer = normalizer
        self.chunking_engine = chunking_engine
        self.embedding_service = embedding_service
        self.graph_builder = graph_builder
        self.entity_extractor = entity_extractor
        self.db = db

    async def ingest_repository(self, github_url: str) -> UUID:
        """
        Orchestrates full ingestion of issues, PRs, commits, and ADRs.
        """
        owner, name = await self._parse_github_url(github_url)
        logger.info("Starting repo ingestion pipeline", owner=owner, repo=name, url=github_url)

        # 1. Create or update Repository record in PostgreSQL
        stmt = select(Repository).where(Repository.github_url == github_url)
        res = await self.db.execute(stmt)
        repo = res.scalar_one_or_none()

        if not repo:
            repo = Repository(
                id=uuid4(),
                github_url=github_url,
                owner=owner,
                name=name,
                status="ingesting",
                created_at=datetime.utcnow(),
            )
            self.db.add(repo)
        else:
            repo.status = "ingesting"
            repo.error_message = None
            repo.updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(repo)

        try:
            # 2. Extract repository metadata from Github
            repo_meta = await self.github_client.get_repository(owner, name)
            repo.description = repo_meta.get("description")

            # 3. Extract issues, PRs, commits, ADRs
            logger.info("Extracting data from GitHub", repo=name)
            raw_issues = await self.github_client.extract_issues(owner, name)
            raw_prs = await self.github_client.extract_pull_requests(owner, name)
            raw_commits = await self.github_client.extract_commits(owner, name)
            raw_adrs = await self.github_client.extract_adrs(owner, name)

            # 4. Normalize raw objects to DB Artifact instances
            artifacts: List[Artifact] = []

            for raw in raw_issues:
                artifacts.append(self.normalizer.normalize_issue(raw, repo.id))
            for raw in raw_prs:
                artifacts.append(self.normalizer.normalize_pull_request(raw, repo.id))
            for raw in raw_commits:
                artifacts.append(self.normalizer.normalize_commit(raw, repo.id))
            for raw in raw_adrs:
                artifacts.append(self.normalizer.normalize_adr(raw, repo.id))

            # Bind the relationship so the chunker has repository properties
            for art in artifacts:
                art.repository = repo

            # 5. Save Artifacts to database to populate ids
            logger.info("Saving artifacts to PostgreSQL", count=len(artifacts))
            if artifacts:
                self.db.add_all(artifacts)
                await self.db.commit()
                # Refresh to get IDs
                for art in artifacts:
                    await self.db.refresh(art)

            # 6. For each artifact: chunk, extract entities, embed, upsert to Qdrant
            logger.info("Chunking, embedding, and extracting entities", count=len(artifacts))
            entities_map: Dict[UUID, ExtractedEntities] = {}

            # Ensure Qdrant and Neo4j indexes are set up
            await self.graph_builder.create_indexes()
            await self.graph_builder.upsert_repository(str(repo.id), repo.name, repo.github_url)

            for art in artifacts:
                # Process chunks and vector index
                chunks = self.chunking_engine.chunk_artifact(art)
                for c in chunks:
                    c.metadata["repository_id"] = str(repo.id)

                # Embed & store in Qdrant
                qdrant_ids = await self.embedding_service.embed_and_store_chunks(chunks, repo.name)
                art.qdrant_ids = qdrant_ids
                self.db.add(art)

                # Entity extraction
                entities = self.entity_extractor.extract(art.body)
                entities_map[art.id] = entities

                # 7. Upsert node to Neo4j
                await self.graph_builder.upsert_artifact(art)

            # Commit the updated qdrant_ids
            await self.db.commit()

            # 8. Create relationships in Neo4j Graph
            logger.info("Constructing graph edges in Neo4j")
            await self.graph_builder.create_relationships(artifacts, entities_map)

            # 9. Ingestion Completed
            repo.status = "completed"
            repo.artifact_count = len(artifacts)
            repo.last_ingested_at = datetime.utcnow()
            repo.updated_at = datetime.utcnow()
            await self.db.commit()

            logger.info("Repository ingestion completed successfully", repo=name, count=len(artifacts))
            return repo.id

        except Exception as e:
            logger.error("Repository ingestion failed", error=str(e), repo=name)
            repo.status = "failed"
            repo.error_message = str(e)
            repo.updated_at = datetime.utcnow()
            await self.db.commit()
            raise IngestionError(f"Failed to ingest repository: {str(e)}")

    async def _parse_github_url(self, url: str) -> Tuple[str, str]:
        """Parse owner and name from standard GitHub URLs."""
        # e.g., https://github.com/owner/repo
        match = re.match(r"https?://(?:www\.)?github\.com/([\w\-\.]+)/([\w\-\.]+)/?", url)
        if not match:
            raise IngestionError(f"Could not parse GitHub repository owner/name from URL: {url}")
        owner, name = match.groups()
        return owner, name.replace(".git", "")
