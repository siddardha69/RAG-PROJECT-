import sys
from unittest.mock import MagicMock, AsyncMock

# --- START SYS.MODULES MOCKS ---
# Mock compiled libraries that cannot compile on pre-release Python/Windows hosts.
class MockSentenceTransformer:
    def __init__(self, *args, **kwargs):
        pass
    def encode(self, sentences, *args, **kwargs):
        import numpy as np
        # Return dummy embeddings of dimension 768
        if isinstance(sentences, list):
            return np.zeros((len(sentences), 768))
        return np.zeros((768,))

class MockSpacy:
    def load(self, *args, **kwargs):
        nlp = MagicMock()
        doc = MagicMock()
        ent = MagicMock()
        ent.label_ = "PERSON"
        ent.text = "Alice"
        ent.ent_id_ = None
        doc.ents = [ent]
        nlp.return_value = doc

        ruler = MagicMock()
        nlp.add_pipe.return_value = ruler
        return nlp

    class cli:
        @staticmethod
        def download(*args, **kwargs):
            pass

sys.modules["spacy"] = MockSpacy()
sys.modules["spacy.cli"] = MockSpacy.cli
sys.modules["sentence_transformers"] = MagicMock()
sys.modules["sentence_transformers"].SentenceTransformer = MockSentenceTransformer
sys.modules["asyncpg"] = MagicMock()
sys.modules["psycopg2"] = MagicMock()
# --- END SYS.MODULES MOCKS ---

import asyncio
from datetime import datetime
import pytest
from app.tasks.celery_app import celery_app
celery_app.conf.update(task_always_eager=True)
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.database.postgres import Base
from app.main import app
from app.api.dependencies import get_db_session, get_github_client, get_qdrant_manager, get_neo4j_manager
from app.models.repository import Repository
from app.models.artifact import Artifact
from app.services.chunking.chunking_engine import Chunk

# SQLite in-memory engine for async testing
DATABASE_URL_TEST = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create session-wide event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def test_engine():
    """Setup clean database engine."""
    engine = create_async_engine(DATABASE_URL_TEST, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine) -> AsyncSession:
    """Yield a database session and clean transaction for each test."""
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


# Mocks
@pytest.fixture
def mock_github_client():
    client = MagicMock()
    client.get_repository = AsyncMock(
        return_value={
            "name": "Hello-World",
            "owner": "octocat",
            "description": "My first repo",
            "default_branch": "main",
            "url": "https://github.com/octocat/Hello-World",
        }
    )
    client.extract_issues = AsyncMock(return_value=[])
    client.extract_pull_requests = AsyncMock(return_value=[])
    client.extract_commits = AsyncMock(return_value=[])
    client.extract_adrs = AsyncMock(return_value=[])
    return client


@pytest.fixture
def mock_qdrant():
    mgr = AsyncMock()
    mgr.get_client = MagicMock()
    mgr.ensure_collection = AsyncMock()
    mgr.upsert_points = AsyncMock()
    mgr.search = AsyncMock(return_value=[])
    return mgr


@pytest.fixture
def mock_neo4j():
    mgr = AsyncMock()
    mgr.verify_connectivity = MagicMock()
    mgr.run_query = AsyncMock(return_value=[])
    return mgr


@pytest.fixture
async def async_client(db_session, mock_github_client, mock_qdrant, mock_neo4j) -> AsyncClient:
    """Return configured test client with overridden dependencies."""

    async def _override_db():
        yield db_session

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_github_client] = lambda: mock_github_client
    app.dependency_overrides[get_qdrant_manager] = lambda: mock_qdrant
    app.dependency_overrides[get_neo4j_manager] = lambda: mock_neo4j

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.clear()


# Seed data
@pytest.fixture
def sample_repository() -> Repository:
    import uuid
    return Repository(
        id=uuid.UUID("d3b07384-d113-4ec2-a5d7-e07e1e479cf8"),
        github_url="https://github.com/octocat/Sample-Repo",
        owner="octocat",
        name="Sample-Repo",
        status="completed",
        artifact_count=5,
        created_at=datetime.utcnow(),
    )


@pytest.fixture
def sample_artifacts(sample_repository) -> list[Artifact]:
    import uuid
    repo_id = sample_repository.id
    return [
        Artifact(
            id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
            repository_id=repo_id,
            artifact_type="issue",
            external_id="1",
            title="Fix login timeout bug",
            body="Users are seeing timeouts when trying to authenticate.",
            author="octocat",
            created_at=datetime.utcnow(),
            metadata_fields={"state": "closed"},
        ),
        Artifact(
            id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
            repository_id=repo_id,
            artifact_type="pull_request",
            external_id="2",
            title="Introduce Redis cache for session storage",
            body="This PR resolves authentication timeouts by introducing Redis. We considered database polling but rejected it.",
            author="coder",
            created_at=datetime.utcnow(),
            metadata_fields={"merged": True, "changed_files": ["src/redis.py"]},
        ),
    ]


@pytest.fixture
def sample_chunks(sample_artifacts) -> list[Chunk]:
    return [
        Chunk(
            chunk_id="c1",
            artifact_id=sample_artifacts[0].id,
            artifact_type="issue",
            repository="Hello-World",
            chunk_type="problem",
            text="Issue #1: Fix login timeout bug. Description: Users are seeing timeouts.",
            author="octocat",
            created_at=datetime.utcnow(),
            metadata={},
        )
    ]
