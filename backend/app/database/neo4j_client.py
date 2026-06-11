from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional
from neo4j import AsyncGraphDatabase, AsyncDriver
from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


class Neo4jClientManager:
    """Manages connection and operations with Neo4j graph database."""

    _driver: Optional[AsyncDriver] = None

    @classmethod
    def get_driver(cls) -> AsyncDriver:
        """Get or initialize the singleton AsyncDriver."""
        if cls._driver is None:
            logger.info(
                "Initializing Neo4j driver",
                uri=settings.neo4j_uri,
                user=settings.neo4j_user,
                password_length=len(settings.neo4j_password) if settings.neo4j_password else 0,
            )
            cls._driver = AsyncGraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
            )
        return cls._driver

    @classmethod
    async def close_driver(cls) -> None:
        """Close driver connection."""
        if cls._driver is not None:
            await cls._driver.close()
            cls._driver = None

    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
    ):
        # Allow custom parameters or fall back to settings
        self.uri = uri or settings.neo4j_uri
        self.user = user or settings.neo4j_user
        self.password = password or settings.neo4j_password
        self.driver = self.get_driver()

    @asynccontextmanager
    async def get_session(self):
        """Async context manager yielding a Neo4j session."""
        session = self.driver.session()
        try:
            yield session
        finally:
            await session.close()

    async def run_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Run Cypher query and return results as list of dictionaries."""
        params = parameters or {}
        async with self.get_session() as session:
            try:
                result = await session.run(query, params)
                records = await result.data()
                return records
            except Exception as e:
                logger.error(
                    "Neo4j query execution failed",
                    query=query,
                    error=str(e),
                )
                raise

    async def verify_connectivity(self) -> None:
        """Verify connection to Neo4j database."""
        try:
            await self.driver.verify_connectivity()
            logger.info("Connected to Neo4j successfully")
        except Exception as e:
            logger.error("Failed to connect to Neo4j", error=str(e))
            raise

    async def close(self) -> None:
        """Close Neo4j connection."""
        # Typically handled by class-level close_driver, but kept for compatibility
        await self.close_driver()
