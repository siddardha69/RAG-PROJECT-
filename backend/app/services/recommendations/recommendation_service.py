from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import RepositoryNotFoundError
from app.models.artifact import Artifact
from app.models.recommendation import Recommendation
from app.schemas.recommendation import RecommendationResponse
from app.services.retrieval.hybrid_retriever import HybridRetriever
from app.services.llm.synthesis_service import SynthesisService
from app.core.logging import get_logger

logger = get_logger(__name__)


class RecommendationService:
    """Evaluates architectural decisions for technical debt, current risks, and suggests keeping, revisiting, or replacing."""

    def __init__(
        self,
        db: AsyncSession,
        hybrid_retriever: HybridRetriever,
        synthesis_service: SynthesisService,
    ):
        self.db = db
        self.hybrid_retriever = hybrid_retriever
        self.synthesis_service = synthesis_service

    async def get_recommendation(self, artifact_id: UUID) -> RecommendationResponse:
        """Fetch or generate recommendation for revisited risk assessment of an artifact."""
        # 1. Load artifact from database
        stmt_art = select(Artifact).where(Artifact.id == artifact_id)
        res_art = await self.db.execute(stmt_art)
        artifact = res_art.scalar_one_or_none()
        if not artifact:
            raise RepositoryNotFoundError(f"Artifact {artifact_id} not found")

        # 2. Check if recommendation exists in DB and is < 7 days old
        stmt_rec = (
            select(Recommendation)
            .where(Recommendation.artifact_id == artifact_id)
            .order_by(desc(Recommendation.created_at))
            .limit(1)
        )
        res_rec = await self.db.execute(stmt_rec)
        cached_rec = res_rec.scalar_one_or_none()

        if cached_rec:
            age = datetime.utcnow() - cached_rec.created_at
            if age < timedelta(days=7):
                logger.info("Returning cached recommendation", artifact_id=artifact_id, age_days=age.days)
                return RecommendationResponse.model_validate(cached_rec)

        # 3. Build recommendation question
        question = (
            f"Should the decision in '{artifact.title}' be revisited? "
            f"What were the original assumptions and have they changed?"
        )

        # 4. Retrieve context using HybridRetriever
        chunks = await self.hybrid_retriever.retrieve(
            query=question,
            repository_id=str(artifact.repository_id),
        )

        # 5. Call synthesis service to generate recommendation
        context_str = self.synthesis_service._build_context(chunks)
        rec_data = await self.synthesis_service.generate_recommendation(
            artifact_id=artifact_id,
            context=context_str,
        )

        # 6. Save Recommendation to PostgreSQL
        new_rec = Recommendation(
            artifact_id=artifact_id,
            original_assumption=rec_data.get("original_assumption", "N/A"),
            current_risk=rec_data.get("current_risk", "N/A"),
            recommendation=rec_data.get("recommendation", "revisit"),
            confidence=float(rec_data.get("confidence", 0.5)),
            created_at=datetime.utcnow(),
        )
        self.db.add(new_rec)
        await self.db.commit()
        await self.db.refresh(new_rec)

        logger.info("Generated and saved new recommendation", artifact_id=artifact_id)
        return RecommendationResponse.model_validate(new_rec)

    async def list_recommendations(
        self,
        repository_id: UUID,
        limit: int = 20,
    ) -> List[RecommendationResponse]:
        """List latest recommendations for a repository, sorted by confidence descending."""
        stmt = (
            select(Recommendation)
            .join(Artifact, Recommendation.artifact_id == Artifact.id)
            .where(Artifact.repository_id == repository_id)
            .order_by(desc(Recommendation.confidence), desc(Recommendation.created_at))
            .limit(limit)
        )
        res = await self.db.execute(stmt)
        recs = res.scalars().all()
        return [RecommendationResponse.model_validate(r) for r in recs]
