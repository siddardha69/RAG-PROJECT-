from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.exceptions import ArchaeologAIException
from app.database.postgres import init_db
from app.database.qdrant_client import QdrantClientManager
from app.database.neo4j_client import Neo4jClientManager
from app.services.graph.graph_builder import GraphBuilder

# Import routers
from app.api.routes.repositories import router as repositories_router
from app.api.routes.queries import router as queries_router
from app.api.routes.timeline import router as timeline_router
from app.api.routes.recommendations import router as recommendations_router
from app.api.routes.health import router as health_router

settings = get_settings()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Context manager handling startup and shutdown actions."""
    logger.info("Initializing ArchaeologAI services...")

    # 1. Initialize Postgres Database Tables
    try:
        await init_db()
        logger.info("Postgres database initialized successfully")
    except Exception as e:
        logger.critical("Postgres connection or table initialization failed", error=str(e))
        raise e

    # 2. Initialize Qdrant and Ensure Collection Exists
    try:
        qdrant_manager = QdrantClientManager()
        await qdrant_manager.ensure_collection(
            collection_name=settings.qdrant_collection_name,
            vector_size=settings.vector_dim,
        )
        logger.info("Qdrant collection setup check completed")
    except Exception as e:
        logger.critical("Qdrant connection or collection check failed", error=str(e))
        raise e

    # 3. Verify Neo4j Connectivity and Set Up Constraints
    try:
        neo4j_manager = Neo4jClientManager()
        await neo4j_manager.verify_connectivity()

        builder = GraphBuilder(neo4j_manager)
        await builder.create_indexes()
        logger.info("Neo4j database connection verified and constraints checked")
    except Exception as e:
        logger.critical("Neo4j connection or constraint check failed", error=str(e))
        raise e

    logger.info("ArchaeologAI started successfully!")
    yield

    # Shutdown operations
    logger.info("Closing database connections...")
    await QdrantClientManager.close()
    await Neo4jClientManager.close_driver()
    logger.info("Services shutdown successfully")


# Initialize FastAPI app
app = FastAPI(
    title="ArchaeologAI API",
    description="Ask your codebase why it is the way it is. Temporal GraphRAG system for architectural memory.",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Custom Exception Handler
@app.exception_handler(ArchaeologAIException)
async def archaeologai_exception_handler(request: Request, exc: ArchaeologAIException):
    logger.error("API error occurred", path=request.url.path, message=exc.message, status_code=exc.status_code)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.message, "details": exc.details},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exceptions in route", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "An internal server error occurred.",
            "details": {"message": str(exc)},
        },
    )


# Include API routers
app.include_router(repositories_router, prefix="/api")
app.include_router(queries_router, prefix="/api")
app.include_router(timeline_router, prefix="/api")
app.include_router(recommendations_router, prefix="/api")
app.include_router(health_router, prefix="/api")

# Serve frontend build in production
import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"))
if os.path.exists(frontend_dist):
    # Mount assets directory
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")

    # Catch-all route for SPA routing
    @app.get("/{fallback_path:path}")
    async def serve_spa(fallback_path: str):
        if fallback_path.startswith("api"):
            return JSONResponse(status_code=404, content={"error": "Not Found"})
        return FileResponse(os.path.join(frontend_dist, "index.html"))

