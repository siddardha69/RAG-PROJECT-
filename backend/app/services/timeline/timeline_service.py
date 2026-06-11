from datetime import datetime
from typing import List, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import RepositoryNotFoundError
from app.models.artifact import Artifact
from app.schemas.timeline import TimelineEvent, TimelineResponse
from app.services.graph.graph_traversal import GraphTraversal
from app.services.llm.synthesis_service import SynthesisService
from app.core.logging import get_logger

logger = get_logger(__name__)


class TimelineService:
    """Generates chronological decision narratives and events from graph-traversed artifacts."""

    def __init__(self, db: AsyncSession, graph_traversal: GraphTraversal):
        self.db = db
        self.graph_traversal = graph_traversal
        self.synthesis_service = SynthesisService()

    async def get_timeline(self, artifact_id: UUID) -> TimelineResponse:
        """Resolve full chronological decision timeline for a given anchor artifact."""
        # 1. Load the anchor artifact from Postgres
        stmt = select(Artifact).where(Artifact.id == artifact_id)
        res = await self.db.execute(stmt)
        anchor = res.scalar_one_or_none()
        if not anchor:
            raise RepositoryNotFoundError(f"Anchor artifact with ID {artifact_id} not found")

        # 2. Get the decision chain (list of dicts representing related nodes)
        chain_refs = await self.graph_traversal.get_decision_chain(str(artifact_id))

        # 3. Load full artifacts for each node in decision chain
        ref_ids = []
        for ref in chain_refs:
            try:
                ref_ids.append(UUID(ref["artifact_id"]))
            except ValueError:
                continue

        events: List[TimelineEvent] = []
        if ref_ids:
            stmt_chain = select(Artifact).where(Artifact.id.in_(ref_ids))
            res_chain = await self.db.execute(stmt_chain)
            chain_artifacts = res_chain.scalars().all()

            # 4 & 5. Build TimelineEvent list for each artifact
            for art in chain_artifacts:
                art_events = self._build_events_from_artifact(art)
                events.extend(art_events)

        # Sort all events chronologically
        events.sort(key=lambda x: x.event_date)

        # 6. Generate narrative summary
        narrative = await self._generate_narrative(events)

        return TimelineResponse(
            artifact_id=artifact_id,
            events=events,
            narrative=narrative,
        )

    def _build_events_from_artifact(self, artifact: Artifact) -> List[TimelineEvent]:
        """Extract individual events from a single artifact's life cycle."""
        events = []
        art_id = artifact.id
        art_type = artifact.artifact_type
        author = artifact.author
        url = artifact.url
        title = artifact.title

        if art_type == "issue":
            # Issue Created
            events.append(
                TimelineEvent(
                    event_date=artifact.created_at,
                    event_type="issue_created",
                    title=f"Issue #{artifact.external_id} Created",
                    description=f"Issue created by {author}: '{title}'",
                    artifact_id=art_id,
                    artifact_type=art_type,
                    author=author,
                    url=url,
                )
            )

            # Issue Closed (if applicable)
            if artifact.closed_at:
                events.append(
                    TimelineEvent(
                        event_date=artifact.closed_at,
                        event_type="issue_closed",
                        title=f"Issue #{artifact.external_id} Closed",
                        description=f"Issue closed: '{title}'",
                        artifact_id=art_id,
                        artifact_type=art_type,
                        author=author,
                        url=url,
                    )
                )

        elif art_type == "pull_request":
            # PR Opened
            events.append(
                TimelineEvent(
                    event_date=artifact.created_at,
                    event_type="pr_opened",
                    title=f"PR #{artifact.external_id} Opened",
                    description=f"Pull request opened by {author}: '{title}'",
                    artifact_id=art_id,
                    artifact_type=art_type,
                    author=author,
                    url=url,
                )
            )

            # PR Merged
            if artifact.merged_at:
                events.append(
                    TimelineEvent(
                        event_date=artifact.merged_at,
                        event_type="pr_merged",
                        title=f"PR #{artifact.external_id} Merged",
                        description=f"Pull request merged: '{title}'",
                        artifact_id=art_id,
                        artifact_type=art_type,
                        author="system",
                        url=url,
                    )
                )
            # PR Closed (unmerged)
            elif artifact.closed_at:
                events.append(
                    TimelineEvent(
                        event_date=artifact.closed_at,
                        event_type="pr_closed",
                        title=f"PR #{artifact.external_id} Closed (Unmerged)",
                        description=f"Pull request closed without merging: '{title}'",
                        artifact_id=art_id,
                        artifact_type=art_type,
                        author=author,
                        url=url,
                    )
                )

        elif art_type == "commit":
            events.append(
                TimelineEvent(
                    event_date=artifact.created_at,
                    event_type="commit_made",
                    title=f"Commit {artifact.external_id[:8]}",
                    description=f"Commit by {author}: '{title}'",
                    artifact_id=art_id,
                    artifact_type=art_type,
                    author=author,
                    url=url,
                )
            )

        elif art_type == "adr":
            events.append(
                TimelineEvent(
                    event_date=artifact.created_at,
                    event_type="adr_created",
                    title=f"ADR Created: {title}",
                    description=f"Architecture Decision Record created in path: {artifact.external_id}",
                    artifact_id=art_id,
                    artifact_type=art_type,
                    author=author,
                    url=url,
                )
            )

        return events

    async def _generate_narrative(self, events: List[TimelineEvent]) -> str:
        """Call LLM to write a 2-3 sentence paragraph summarizing the decision timeline."""
        if not events:
            return "No chronological events recorded for this decision timeline."

        event_summaries = []
        for e in events:
            date_str = e.event_date.strftime("%Y-%m-%d")
            event_summaries.append(f"[{date_str}] {e.event_type.upper()}: {e.title} - {e.description}")

        events_context = "\n".join(event_summaries)

        prompt = (
            "You are an engineering historian summarizing the chronological chain of events that led to a decision.\n"
            "Summarize the following timeline in a brief, cohesive, narrative paragraph of 2-3 sentences. "
            "Explain what started the thread, what actions were taken, and the final decision/outcome.\n\n"
            f"Timeline Events:\n{events_context}"
        )

        try:
            client = self.synthesis_service._get_llm_client()
            response = await client.generate(
                system_prompt="You write concise, highly technical engineering narratives.",
                user_message=prompt,
                max_tokens=256,
            )
            return response.strip()
        except Exception as e:
            logger.error("Failed to generate timeline narrative, using fallback", error=str(e))
            # Fallback narrative
            if len(events) >= 2:
                return f"Decision started with {events[0].title} on {events[0].event_date.strftime('%Y-%m-%d')} and concluded with {events[-1].title} on {events[-1].event_date.strftime('%Y-%m-%d')}."
            return f"Timeline contains {len(events)} events tracing decision context starting on {events[0].event_date.strftime('%Y-%m-%d')}."
