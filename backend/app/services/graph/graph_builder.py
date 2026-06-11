from typing import Any, Dict, List
from uuid import UUID
from app.models.artifact import Artifact
from app.database.neo4j_client import Neo4jClientManager
from app.services.entity_extraction.entity_extractor import ExtractedEntities
from app.core.logging import get_logger

logger = get_logger(__name__)


class GraphBuilder:
    """Builds Neo4j knowledge graph from ingested repository artifacts."""

    def __init__(self, neo4j_manager: Neo4jClientManager):
        self.neo4j_manager = neo4j_manager

    async def create_indexes(self) -> None:
        """Create Neo4j indexes for fast lookup."""
        queries = [
            "CREATE CONSTRAINT unique_repository_id IF NOT EXISTS FOR (r:Repository) REQUIRE r.id IS UNIQUE",
            "CREATE CONSTRAINT unique_issue_id IF NOT EXISTS FOR (i:Issue) REQUIRE i.id IS UNIQUE",
            "CREATE CONSTRAINT unique_pr_id IF NOT EXISTS FOR (p:PR) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT unique_commit_id IF NOT EXISTS FOR (c:Commit) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT unique_adr_id IF NOT EXISTS FOR (a:ADR) REQUIRE a.id IS UNIQUE",
            "CREATE CONSTRAINT unique_tech_name IF NOT EXISTS FOR (t:Technology) REQUIRE t.name IS UNIQUE",
            "CREATE INDEX repository_name_idx IF NOT EXISTS FOR (r:Repository) ON (r.name)",
        ]
        for q in queries:
            try:
                await self.neo4j_manager.run_query(q)
            except Exception as e:
                # In some neo4j versions or setups constraints might throw warnings, just log and proceed
                logger.warning("Constraint/index creation query status", query=q, error=str(e))

    async def upsert_repository(self, repo_id: str, name: str, url: str) -> None:
        """Create or update a Repository node."""
        query = """
        MERGE (r:Repository {id: $id})
        SET r.name = $name, r.url = $url
        """
        await self.neo4j_manager.run_query(
            query,
            {"id": repo_id, "name": name, "url": url},
        )

    async def upsert_artifact(self, artifact: Artifact) -> None:
        """Upsert artifact node mapping types to labels."""
        art_id = str(artifact.id)
        repo_id = str(artifact.repository_id)
        created_at_iso = artifact.created_at.isoformat()

        if artifact.artifact_type == "issue":
            query = """
            MATCH (r:Repository {id: $repo_id})
            MERGE (i:Issue {id: $id})
            SET i.external_id = $external_id,
                i.title = $title,
                i.author = $author,
                i.created_at = $created_at,
                i.closed_at = $closed_at,
                i.url = $url,
                i.labels = $labels
            MERGE (r)-[:CONTAINS]->(i)
            """
            closed_at_iso = artifact.closed_at.isoformat() if artifact.closed_at else None
            await self.neo4j_manager.run_query(
                query,
                {
                    "id": art_id,
                    "repo_id": repo_id,
                    "external_id": artifact.external_id,
                    "title": artifact.title,
                    "author": artifact.author,
                    "created_at": created_at_iso,
                    "closed_at": closed_at_iso,
                    "url": artifact.url,
                    "labels": list(artifact.labels),
                },
            )

        elif artifact.artifact_type == "pull_request":
            query = """
            MATCH (r:Repository {id: $repo_id})
            MERGE (p:PR {id: $id})
            SET p.external_id = $external_id,
                p.title = $title,
                p.author = $author,
                p.created_at = $created_at,
                p.merged_at = $merged_at,
                p.url = $url,
                p.merged = $merged,
                p.state = $state
            MERGE (r)-[:CONTAINS]->(p)
            """
            merged_at_iso = artifact.merged_at.isoformat() if artifact.merged_at else None
            await self.neo4j_manager.run_query(
                query,
                {
                    "id": art_id,
                    "repo_id": repo_id,
                    "external_id": artifact.external_id,
                    "title": artifact.title,
                    "author": artifact.author,
                    "created_at": created_at_iso,
                    "merged_at": merged_at_iso,
                    "url": artifact.url,
                    "merged": artifact.metadata_fields.get("merged", False),
                    "state": artifact.metadata_fields.get("state", "open"),
                },
            )

        elif artifact.artifact_type == "commit":
            query = """
            MATCH (r:Repository {id: $repo_id})
            MERGE (c:Commit {id: $id})
            SET c.external_id = $external_id,
                c.title = $title,
                c.author = $author,
                c.created_at = $created_at,
                c.url = $url
            MERGE (r)-[:CONTAINS]->(c)
            """
            await self.neo4j_manager.run_query(
                query,
                {
                    "id": art_id,
                    "repo_id": repo_id,
                    "external_id": artifact.external_id,
                    "title": artifact.title,
                    "author": artifact.author,
                    "created_at": created_at_iso,
                    "url": artifact.url,
                },
            )

        elif artifact.artifact_type == "adr":
            query = """
            MATCH (r:Repository {id: $repo_id})
            MERGE (a:ADR {id: $id})
            SET a.external_id = $external_id,
                a.title = $title,
                a.author = $author,
                a.created_at = $created_at,
                a.url = $url
            MERGE (r)-[:CONTAINS]->(a)
            """
            await self.neo4j_manager.run_query(
                query,
                {
                    "id": art_id,
                    "repo_id": repo_id,
                    "external_id": artifact.external_id,
                    "title": artifact.title,
                    "author": artifact.author,
                    "created_at": created_at_iso,
                    "url": artifact.url,
                },
            )

    async def create_relationships(
        self,
        artifacts: List[Artifact],
        entities_map: Dict[UUID, ExtractedEntities],
    ) -> None:
        """Create connections (LED_TO, CREATED, MENTIONS, USES, DECIDES, MODIFIES) between nodes."""
        logger.info("Creating graph relationships in Neo4j", count=len(artifacts))

        # Build maps for reference lookup
        artifact_by_id = {art.id: art for art in artifacts}

        for artifact in artifacts:
            art_id = str(artifact.id)
            entities = entities_map.get(artifact.id)
            if not entities:
                continue

            # 1. Connect artifact to Technology nodes
            for tech in entities.technologies:
                # Merge Technology node
                tech_query = "MERGE (t:Technology {name: $name})"
                await self.neo4j_manager.run_query(tech_query, {"name": tech})

                # Connect based on type
                if artifact.artifact_type == "issue":
                    rel_query = """
                    MATCH (i:Issue {id: $id})
                    MATCH (t:Technology {name: $tech})
                    MERGE (i)-[:MENTIONS]->(t)
                    """
                elif artifact.artifact_type == "pull_request":
                    rel_query = """
                    MATCH (p:PR {id: $id})
                    MATCH (t:Technology {name: $tech})
                    MERGE (p)-[:USES]->(t)
                    """
                elif artifact.artifact_type == "commit":
                    rel_query = """
                    MATCH (c:Commit {id: $id})
                    MATCH (t:Technology {name: $tech})
                    MERGE (c)-[:MODIFIES]->(t)
                    """
                elif artifact.artifact_type == "adr":
                    rel_query = """
                    MATCH (a:ADR {id: $id})
                    MATCH (t:Technology {name: $tech})
                    MERGE (a)-[:DECIDES]->(t)
                    """
                else:
                    continue

                await self.neo4j_manager.run_query(rel_query, {"id": art_id, "tech": tech})

            # 2. Connect Issue -> PR (LED_TO)
            if artifact.artifact_type == "pull_request":
                # Find linked issues
                linked_issues = artifact.metadata_fields.get("linked_issues", [])
                for issue_num in linked_issues:
                    # Look up if this issue exists in the list (same repo)
                    issue_query = """
                    MATCH (p:PR {id: $id})<-[:CONTAINS]-(r:Repository)-[:CONTAINS]->(i:Issue {external_id: $issue_num})
                    MERGE (i)-[:LED_TO]->(p)
                    """
                    await self.neo4j_manager.run_query(
                        issue_query,
                        {"issue_num": str(issue_num), "id": art_id},
                    )

            # 3. Connect PR -> Commit (CREATED)
            if artifact.artifact_type == "commit":
                # Check if commit entities mention a PR
                for pr_ref in entities.pr_refs:
                    # pr_ref is like "PR #45", parse out the 45
                    match = re.search(r"\d+", pr_ref)
                    if match:
                        pr_num = match.group(0)
                        pr_query = """
                        MATCH (c:Commit {id: $id})<-[:CONTAINS]-(r:Repository)-[:CONTAINS]->(p:PR {external_id: $pr_num})
                        MERGE (p)-[:CREATED]->(c)
                        """
                        await self.neo4j_manager.run_query(
                            pr_query,
                            {"pr_num": pr_num, "id": art_id},
                        )

        logger.info("Graph relationships created successfully")
import re
