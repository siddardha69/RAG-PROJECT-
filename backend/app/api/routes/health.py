from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import redis.asyncio as aris
from app.api.dependencies import get_db_session, get_qdrant_manager, get_neo4j_manager
from app.database.qdrant_client import QdrantClientManager
from app.database.neo4j_client import Neo4jClientManager
from app.core.config import get_settings

router = APIRouter(prefix="/health", tags=["health"])
settings = get_settings()


@router.get("", status_code=status.HTTP_200_OK)
async def health_check(
    db: AsyncSession = Depends(get_db_session),
    qdrant_mgr: QdrantClientManager = Depends(get_qdrant_manager),
    neo4j_mgr: Neo4jClientManager = Depends(get_neo4j_manager),
):
    """Perform health checks on all dependent services (PostgreSQL, Redis, Qdrant, Neo4j)."""
    services = {
        "postgres": "failed",
        "redis": "failed",
        "qdrant": "failed",
        "neo4j": "failed",
    }
    status_overall = "ok"

    # 1. Check PostgreSQL
    try:
        await db.execute(text("SELECT 1"))
        services["postgres"] = "ok"
    except Exception as e:
        status_overall = "error"
        services["postgres"] = f"error: {str(e)}"

    # 2. Check Redis
    try:
        r = aris.from_url(settings.redis_url)
        await r.ping()
        await r.close()
        services["redis"] = "ok"
    except Exception as e:
        status_overall = "error"
        services["redis"] = f"error: {str(e)}"

    # 3. Check Qdrant
    try:
        client = qdrant_mgr.get_client()
        await client.get_collections()
        services["qdrant"] = "ok"
    except Exception as e:
        status_overall = "error"
        services["qdrant"] = f"error: {str(e)}"

    # 4. Check Neo4j
    try:
        await neo4j_mgr.verify_connectivity()
        services["neo4j"] = "ok"
    except Exception as e:
        status_overall = "error"
        services["neo4j"] = f"error: {str(e)}"

    return {
        "status": status_overall,
        "services": services,
    }
