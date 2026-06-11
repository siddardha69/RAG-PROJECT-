from typing import Any, Dict, List
from app.database.neo4j_client import Neo4jClientManager
from app.core.logging import get_logger

logger = get_logger(__name__)


class GraphTraversal:
    """Retrieves decision-related subgraphs and associations from Neo4j."""

    def __init__(self, neo4j_manager: Neo4jClientManager):
        self.neo4j_manager = neo4j_manager

    async def find_decision_neighborhood(
        self,
        anchor_artifact_ids: List[str],
        depth: int = 2,
    ) -> List[Dict[str, Any]]:
        """
        Query Neo4j for nodes linked within `depth` hops of the anchor nodes.
        Returns list of matched node summaries.
        """
        if not anchor_artifact_ids:
            return []

        # We match paths of length 1 to depth
        query = f"""
        MATCH (a)-[*1..{depth}]-(related)
        WHERE a.id IN $anchor_ids AND NOT related:Repository AND NOT related:Technology
        RETURN DISTINCT related.id as id,
                        labels(related)[0] as type,
                        related.title as title,
                        related.message as message,
                        related.created_at as created_at,
                        related.url as url
        """
        records = await self.neo4j_manager.run_query(
            query,
            {"anchor_ids": anchor_artifact_ids},
        )

        results = []
        for r in records:
            title = r.get("title") or r.get("message") or "Untitled"
            results.append({
                "id": r["id"],
                "type": r["type"],
                "title": title,
                "created_at": r["created_at"],
                "url": r["url"],
            })
        return results

    async def find_technologies_in_context(
        self,
        technology_names: List[str],
    ) -> List[Dict[str, Any]]:
        """Find artifacts that Decided, Used, Modified or Mentioned specific technologies."""
        if not technology_names:
            return []

        query = """
        MATCH (a)-[r:USES|DECIDES|MODIFY|MENTIONS|MODIFIES]->(t:Technology)
        WHERE t.name IN $tech_names
        RETURN DISTINCT a.id as id,
                        labels(a)[0] as type,
                        a.title as title,
                        a.message as message,
                        a.created_at as created_at,
                        a.url as url,
                        type(r) as relationship,
                        t.name as technology
        """
        records = await self.neo4j_manager.run_query(
            query,
            {"tech_names": technology_names},
        )

        results = []
        for r in records:
            title = r.get("title") or r.get("message") or "Untitled"
            results.append({
                "id": r["id"],
                "type": r["type"],
                "title": title,
                "created_at": r["created_at"],
                "url": r["url"],
                "relationship": r["relationship"],
                "technology": r["technology"],
            })
        return results

    async def get_decision_chain(self, artifact_id: str) -> List[Dict[str, Any]]:
        """
        Find decision lineages traversing related paths:
        Issue -> LED_TO -> PR -> CREATED -> Commit
        Or ADRs -> DECIDES -> Technology
        Returns chronological pathway.
        """
        query = """
        MATCH path = (a)-[*1..3]-(b)
        WHERE a.id = $id AND NOT b:Repository AND NOT b:Technology
        RETURN [n in nodes(path) | {id: n.id, type: labels(n)[0], title: coalesce(n.title, n.message, "Untitled"), created_at: n.created_at}] as nodes,
               [r in relationships(path) | type(r)] as rels
        """
        records = await self.neo4j_manager.run_query(query, {"id": artifact_id})

        visited_nodes = {}
        # Always include the anchor node itself
        anchor_query = """
        MATCH (a) WHERE a.id = $id
        RETURN labels(a)[0] as type, a.title as title, a.message as message, a.created_at as created_at
        """
        anchors = await self.neo4j_manager.run_query(anchor_query, {"id": artifact_id})
        if anchors:
            a = anchors[0]
            title = a.get("title") or a.get("message") or "Untitled"
            visited_nodes[artifact_id] = {
                "artifact_id": artifact_id,
                "type": a["type"],
                "title": title,
                "date": a["created_at"],
                "relationship": "anchor",
            }

        for r in records:
            nodes = r.get("nodes", [])
            rels = r.get("rels", [])
            for node, rel_type in zip(nodes, rels):
                nid = node.get("id")
                if not nid or nid == artifact_id:
                    continue

                visited_nodes[nid] = {
                    "artifact_id": nid,
                    "type": node.get("type", "Artifact"),
                    "title": node.get("title", "Untitled"),
                    "date": node.get("created_at"),
                    "relationship": rel_type,
                }

        # Sort chronological
        chain = list(visited_nodes.values())
        chain.sort(key=lambda x: x["date"] or "")
        return chain

    async def get_all_nodes_and_edges(self, repository_name: str) -> Dict[str, Any]:
        """Return all nodes and relationships for a repository for graph UI rendering."""
        # Find repo node first
        query = """
        MATCH (r:Repository {name: $repo_name})-[:CONTAINS]->(a)
        OPTIONAL MATCH (a)-[rel]->(b)
        WHERE NOT b:Repository
        RETURN a, labels(a) as a_labels, rel, b, labels(b) as b_labels
        """
        records = await self.neo4j_manager.run_query(query, {"repo_name": repository_name})

        nodes_dict = {}
        edges = []

        for r in records:
            a_node = r.get("a")
            a_labels = r.get("a_labels", [])
            rel = r.get("rel")
            b_node = r.get("b")
            b_labels = r.get("b_labels", [])

            if a_node:
                aid = a_node.get("id")
                label = a_node.get("title") or a_node.get("message") or a_node.get("name") or "Untitled"
                nodes_dict[aid] = {
                    "id": aid,
                    "label": label,
                    "type": a_labels[0] if a_labels else "Artifact",
                    "properties": dict(a_node),
                }

            if b_node:
                bid = b_node.get("id") or b_node.get("name")  # Technology nodes have 'name' as identifier
                label = b_node.get("title") or b_node.get("message") or b_node.get("name") or "Untitled"
                b_type = b_labels[0] if b_labels else "Artifact"
                nodes_dict[bid] = {
                    "id": bid,
                    "label": label,
                    "type": b_type,
                    "properties": dict(b_node),
                }

            if rel and a_node and b_node:
                aid = a_node.get("id")
                bid = b_node.get("id") or b_node.get("name")
                if isinstance(rel, tuple) and len(rel) >= 2:
                    rel_type = rel[1]
                else:
                    rel_type = getattr(rel, "type", "ASSOCIATED")
                edges.append({
                    "source": aid,
                    "target": bid,
                    "relationship": rel_type,
                })

        return {
            "nodes": list(nodes_dict.values()),
            "edges": edges,
        }
