import re
from datetime import datetime
from typing import Any, Dict, List
from uuid import UUID
from app.models.artifact import Artifact


class ArtifactNormalizer:
    """Converts raw GitHub data into normalized Artifact model instances."""

    def _naive_dt(self, dt: Any) -> Any:
        if isinstance(dt, datetime):
            return dt.replace(tzinfo=None)
        return dt

    def normalize_issue(self, raw: Dict[str, Any], repository_id: UUID) -> Artifact:
        """Convert raw issue dict into Artifact model."""
        body_for_embedding = self._build_issue_body(raw)
        linked_items = self._extract_linked_items(body_for_embedding)

        meta = {
            "state": raw.get("state", "open"),
            "linked_issues": linked_items.get("issues", []),
            "linked_prs": linked_items.get("prs", []),
        }

        return Artifact(
            repository_id=repository_id,
            artifact_type="issue",
            external_id=raw["external_id"],
            title=raw["title"],
            body=body_for_embedding,
            author=raw["author"],
            url=raw.get("url"),
            created_at=self._naive_dt(raw["created_at"]),
            closed_at=self._naive_dt(raw.get("closed_at")),
            labels=raw.get("labels", []),
            metadata_fields=meta,
        )

    def normalize_pull_request(self, raw: Dict[str, Any], repository_id: UUID) -> Artifact:
        """Convert raw PR dict into Artifact model."""
        body_for_embedding = self._build_pr_body(raw)
        linked_items = self._extract_linked_items(body_for_embedding)

        meta = {
            "state": raw.get("state", "open"),
            "merged": raw.get("merged", False),
            "changed_files": raw.get("changed_files", []),
            "linked_issues": linked_items.get("issues", []),
            "linked_prs": linked_items.get("prs", []),
        }

        return Artifact(
            repository_id=repository_id,
            artifact_type="pull_request",
            external_id=raw["external_id"],
            title=raw["title"],
            body=body_for_embedding,
            author=raw["author"],
            url=raw.get("url"),
            created_at=self._naive_dt(raw["created_at"]),
            merged_at=self._naive_dt(raw.get("merged_at")),
            closed_at=self._naive_dt(raw.get("closed_at")),
            labels=raw.get("labels", []),
            metadata_fields=meta,
        )

    def normalize_commit(self, raw: Dict[str, Any], repository_id: UUID) -> Artifact:
        """Convert raw commit dict into Artifact model."""
        body_for_embedding = f"Commit message: {raw['title']}\n{raw['body']}\nChanged Files:\n" + "\n".join(raw.get("files_changed", []))
        linked_items = self._extract_linked_items(body_for_embedding)

        meta = {
            "files_changed": raw.get("files_changed", []),
            "linked_issues": linked_items.get("issues", []),
            "linked_prs": linked_items.get("prs", []),
        }

        return Artifact(
            repository_id=repository_id,
            artifact_type="commit",
            external_id=raw["external_id"],
            title=raw["title"],
            body=body_for_embedding,
            author=raw["author"],
            url=raw.get("url"),
            created_at=self._naive_dt(raw["created_at"]),
            metadata_fields=meta,
        )

    def normalize_adr(self, raw: Dict[str, Any], repository_id: UUID) -> Artifact:
        """Convert raw ADR dict into Artifact model."""
        meta = {
            "file_path": raw["external_id"],
        }

        return Artifact(
            repository_id=repository_id,
            artifact_type="adr",
            external_id=raw["external_id"],
            title=raw["title"],
            body=raw["body"],
            author=raw.get("author", "system"),
            url=raw.get("url"),
            created_at=self._naive_dt(raw["created_at"]),
            metadata_fields=meta,
        )

    def _build_issue_body(self, raw: Dict[str, Any]) -> str:
        """Combine title + body + all comment texts into one string for embedding."""
        parts = [
            f"Issue #{raw['external_id']}: {raw['title']}",
            f"Description: {raw.get('body', '')}",
        ]
        if raw.get("comments"):
            parts.append("\nComments:")
            for comment in raw["comments"]:
                parts.append(f"[{comment['created_at']}] {comment['author']}: {comment['body']}")
        return "\n".join(parts)

    def _build_pr_body(self, raw: Dict[str, Any]) -> str:
        """Combine PR description + review comments + changed file list."""
        parts = [
            f"Pull Request #{raw['external_id']}: {raw['title']}",
            f"Description: {raw.get('body', '')}",
        ]
        if raw.get("changed_files"):
            parts.append(f"Files modified: {', '.join(raw['changed_files'])}")
        if raw.get("review_comments"):
            parts.append("\nReview Comments/Discussions:")
            for comment in raw["review_comments"]:
                parts.append(f"[{comment['created_at']}] {comment['author']}: {comment['body']}")
        return "\n".join(parts)

    def _extract_linked_items(self, text: str) -> Dict[str, List[int]]:
        """Find references like #123, PR #45, issue #67 using regex."""
        # Find all occurrences of # followed by digits
        matches = re.findall(r"#(\d+)", text)
        refs = [int(m) for m in matches]

        # In this simple model we'll treat them as both issue and PR links
        # as GitHub uses a unified numbering system for issues and PRs.
        return {
            "issues": refs,
            "prs": refs,
        }
