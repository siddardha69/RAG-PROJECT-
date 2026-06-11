from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from app.api.dependencies import get_timeline_service
from app.schemas.timeline import TimelineResponse
from app.services.timeline.timeline_service import TimelineService
from app.core.exceptions import RepositoryNotFoundError

router = APIRouter(prefix="/timeline", tags=["timeline"])


@router.get("/{artifact_id}", response_model=TimelineResponse)
async def get_timeline(
    artifact_id: UUID,
    service: TimelineService = Depends(get_timeline_service),
):
    """Retrieve decision chronological timeline and summary narrative for an artifact."""
    try:
        timeline = await service.get_timeline(artifact_id)
        return timeline
    except RepositoryNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
