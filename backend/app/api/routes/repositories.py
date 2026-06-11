from typing import List, Optional
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db_session
from app.models.repository import Repository
from app.schemas.repository import (
    IngestRepositoryRequest,
    RepositoryResponse,
    RepositoryListResponse,
)
from app.tasks.ingestion_tasks import ingest_repository_task
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/repositories", tags=["repositories"])


@router.post(
    "/ingest",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=dict,
)
async def ingest_repository(
    request: IngestRepositoryRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Ingest a GitHub repository. If it is already completed, return existing,
    otherwise trigger background worker task.
    """
    github_url = request.github_url

    # Check if repo already exists
    stmt = select(Repository).where(Repository.github_url == github_url)
    res = await db.execute(stmt)
    existing = res.scalar_one_or_none()

    if existing:
        if existing.status == "completed":
            return {
                "repository_id": existing.id,
                "status": existing.status,
                "message": "Repository has already been ingested.",
                "task_id": "",
            }
        elif existing.status in ("pending", "ingesting"):
            return {
                "repository_id": existing.id,
                "status": existing.status,
                "message": "Ingestion is already in progress for this repository.",
                "task_id": "",
            }
        elif existing.status == "failed":
            # Reuse the existing record and reset state
            existing.status = "pending"
            existing.error_message = None
            await db.commit()
            
            try:
                task = ingest_repository_task.delay(github_url, str(existing.id))
                task_id = task.id
            except Exception as e:
                logger.error("Failed to enqueue Celery task", error=str(e))
                existing.status = "failed"
                existing.error_message = f"Failed to enqueue task: {str(e)}"
                await db.commit()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to queue ingestion: {str(e)}",
                )

            return {
                "repository_id": existing.id,
                "status": "pending",
                "message": "Ingestion task re-enqueued successfully.",
                "task_id": task_id,
            }

    # Repository needs ingestion
    repo_id = uuid4()
    # Create database placeholder
    # Parse owner/name from URL
    parts = github_url.rstrip("/").split("/")
    name = parts[-1].replace(".git", "")
    owner = parts[-2]

    repo = Repository(
        id=repo_id,
        github_url=github_url,
        owner=owner,
        name=name,
        status="pending",
    )
    db.add(repo)
    await db.commit()
    await db.refresh(repo)

    # Dispatch celery task
    try:
        task = ingest_repository_task.delay(github_url, str(repo_id))
        task_id = task.id
    except Exception as e:
        logger.error("Failed to enqueue Celery task", error=str(e))
        # Update status to failed
        repo.status = "failed"
        repo.error_message = f"Failed to enqueue task: {str(e)}"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue ingestion: {str(e)}",
        )

    return {
        "repository_id": repo_id,
        "status": "pending",
        "message": "Ingestion task enqueued successfully.",
        "task_id": task_id,
    }


@router.get("", response_model=RepositoryListResponse)
async def list_repositories(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
):
    """List all ingested repositories."""
    # Query count
    count_stmt = select(func.count()).select_from(Repository)
    count_res = await db.execute(count_stmt)
    total = count_res.scalar() or 0

    # Query repos
    stmt = select(Repository).order_by(desc(Repository.created_at)).offset(skip).limit(limit)
    res = await db.execute(stmt)
    repos = res.scalars().all()

    return RepositoryListResponse(
        repositories=[RepositoryResponse.model_validate(r) for r in repos],
        total=total,
    )


@router.get("/{repository_id}", response_model=RepositoryResponse)
async def get_repository(
    repository_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    """Get details of a single repository."""
    stmt = select(Repository).where(Repository.id == repository_id)
    res = await db.execute(stmt)
    repo = res.scalar_one_or_none()

    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found",
        )
    return RepositoryResponse.model_validate(repo)


@router.get("/{repository_id}/status")
async def get_repository_status(
    repository_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    """Get the polling ingestion status of a repository."""
    stmt = select(Repository).where(Repository.id == repository_id)
    res = await db.execute(stmt)
    repo = res.scalar_one_or_none()

    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found",
        )

    progress_messages = {
        "pending": "Queued for ingestion...",
        "ingesting": "Extracting artifacts, building vector embeddings and knowledge graph...",
        "completed": "Ingestion completed successfully.",
        "failed": f"Ingestion failed: {repo.error_message or 'Unknown error'}",
    }

    return {
        "status": repo.status,
        "artifact_count": repo.artifact_count,
        "progress_message": progress_messages.get(repo.status, "Processing..."),
        "error_message": repo.error_message,
    }
