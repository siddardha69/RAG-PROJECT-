from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_db_session,
    get_recommendation_service,
    get_graph_traversal,
)
from app.schemas.recommendation import RecommendationResponse
from app.services.recommendations.recommendation_service import RecommendationService
from app.services.graph.graph_traversal import GraphTraversal
from app.models.recommendation import Recommendation
from app.core.exceptions import RepositoryNotFoundError

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("", response_model=List[RecommendationResponse])
async def list_recommendations(
    repository_id: Optional[UUID] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
    service: RecommendationService = Depends(get_recommendation_service),
):
    """List recent recommendations, optionally filtered by repository."""
    if repository_id:
        return await service.list_recommendations(repository_id, limit=limit)

    # General list
    stmt = select(Recommendation).order_by(desc(Recommendation.created_at)).limit(limit)
    res = await db.execute(stmt)
    recs = res.scalars().all()
    return [RecommendationResponse.model_validate(r) for r in recs]


@router.get("/graph")
async def get_graph_data(
    repository_name: str = Query(..., description="Name of the repository to fetch graph for"),
    graph_traversal: GraphTraversal = Depends(get_graph_traversal),
):
    """Fetch all nodes and edges for React Flow visualization of a repository."""
    try:
        data = await graph_traversal.get_all_nodes_and_edges(repository_name)
        return data
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load graph data: {str(e)}",
        )


@router.get("/{artifact_id}", response_model=RecommendationResponse)
async def get_recommendation(
    artifact_id: UUID,
    service: RecommendationService = Depends(get_recommendation_service),
):
    """Generate or retrieve cached recommendation for a single artifact decision."""
    try:
        recommendation = await service.get_recommendation(artifact_id)
        return recommendation
    except RepositoryNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
