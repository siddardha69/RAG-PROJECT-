import time
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_db_session,
    get_hybrid_retriever,
    get_synthesis_service,
    get_recommendation_service,
)
from app.models.artifact import Artifact
from app.models.query_log import QueryLog
from app.schemas.query import QueryRequest, QueryResponse, ArtifactCitation
from app.services.retrieval.hybrid_retriever import HybridRetriever
from app.services.llm.synthesis_service import SynthesisService
from app.services.recommendations.recommendation_service import RecommendationService
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/query", tags=["queries"])


@router.post("", response_model=QueryResponse)
async def submit_query(
    request: QueryRequest,
    db: AsyncSession = Depends(get_db_session),
    hybrid_retriever: HybridRetriever = Depends(get_hybrid_retriever),
    synthesis_service: SynthesisService = Depends(get_synthesis_service),
    recommendation_service: RecommendationService = Depends(get_recommendation_service),
):
    """
    Submit a natural language question about the codebase decisions.
    Retrieves decision context using Hybrid GraphRAG and synthesizes an answer.
    """
    start_time = time.time()
    question = request.question
    repo_id_str = str(request.repository_id) if request.repository_id else None

    # 1. Retrieve hybrid chunks
    chunks = await hybrid_retriever.retrieve(
        query=question,
        repository_id=repo_id_str,
    )

    if not chunks:
        latency = int((time.time() - start_time) * 1000)
        query_log = QueryLog(
            id=uuid4(),
            question=question,
            repository_id=request.repository_id,
            answer="Not enough evidence found in the ingested repository to answer this question.",
            artifacts_used=[],
            retrieval_strategy="hybrid",
            latency_ms=latency,
        )
        db.add(query_log)
        await db.commit()

        return QueryResponse(
            question=question,
            answer=query_log.answer,
            citations=[],
            timeline_summary=[],
            recommendation=None,
            confidence=0.0,
            latency_ms=latency,
            query_log_id=query_log.id,
        )

    # 2. Resolve full Artifact database records for citations metadata
    artifact_ids = list(set(chunk.artifact_id for chunk in chunks))
    stmt_art = select(Artifact).where(Artifact.id.in_(artifact_ids))
    res_art = await db.execute(stmt_art)
    db_artifacts = {art.id: art for art in res_art.scalars().all()}

    # 3. Generate answer explanation
    answer, confidence = await synthesis_service.explain_decision(question, chunks)

    # 4. Generate recommendation for the top artifact if requested
    rec_text = None
    if request.include_recommendations and chunks:
        top_artifact_id = chunks[0].artifact_id
        try:
            rec_response = await recommendation_service.get_recommendation(top_artifact_id)
            rec_text = (
                f"Recommendation [{rec_response.recommendation.upper()}]:\n"
                f"- Original Assumptions: {rec_response.original_assumption}\n"
                f"- Current Risks: {rec_response.current_risk}"
            )
        except Exception as e:
            logger.error("Failed to generate recommendation during query", error=str(e))

    # 5. Build citations list
    citations = []
    # Map scores from chunks
    chunk_scores = {c.artifact_id: c.score for c in chunks}

    for art_id, art in db_artifacts.items():
        citations.append(
            ArtifactCitation(
                artifact_id=art.id,
                artifact_type=art.artifact_type,
                title=art.title,
                url=art.url,
                author=art.author,
                created_at=art.created_at,
                relevance_score=chunk_scores.get(art_id, 0.5),
            )
        )
    # Sort citations by relevance score descending
    citations.sort(key=lambda x: x.relevance_score, reverse=True)

    # 6. Build timeline summary from chunks
    timeline_summary = []
    sorted_chunks = sorted(chunks, key=lambda x: x.created_at)
    for c in sorted_chunks:
        art = db_artifacts.get(c.artifact_id)
        if art:
            timeline_summary.append({
                "date": c.created_at.isoformat(),
                "artifact_id": str(c.artifact_id),
                "artifact_type": c.artifact_type,
                "title": art.title,
                "author": c.author,
                "url": c.url,
                "chunk_type": c.chunk_type,
            })

    # 7. Save QueryLog to Postgres
    latency = int((time.time() - start_time) * 1000)
    query_log = QueryLog(
        id=uuid4(),
        question=question,
        repository_id=request.repository_id,
        answer=answer,
        artifacts_used=[str(aid) for aid in artifact_ids],
        retrieval_strategy="hybrid",
        latency_ms=latency,
    )
    db.add(query_log)
    await db.commit()
    await db.refresh(query_log)

    return QueryResponse(
        question=question,
        answer=answer,
        citations=citations,
        timeline_summary=timeline_summary,
        recommendation=rec_text,
        confidence=confidence,
        latency_ms=latency,
        query_log_id=query_log.id,
    )
