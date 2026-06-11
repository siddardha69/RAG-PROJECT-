import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel
from app.models.artifact import Artifact


class Chunk(BaseModel):
    """Data class representing a text chunk from an artifact for vector indexing."""

    chunk_id: str
    artifact_id: UUID
    artifact_type: str
    repository: str
    chunk_type: str  # e.g., problem, discussion, resolution, purpose, alternatives, etc.
    text: str
    author: str
    created_at: datetime
    url: Optional[str] = None
    metadata: Dict[str, Any]


class ChunkingEngine:
    """Artifact-type-aware chunking engine."""

    def chunk_artifact(self, artifact: Artifact) -> List[Chunk]:
        """Route artifact to appropriate chunker based on its type."""
        if artifact.artifact_type == "issue":
            return self._chunk_issue(artifact)
        elif artifact.artifact_type == "pull_request":
            return self._chunk_pull_request(artifact)
        elif artifact.artifact_type == "adr":
            return self._chunk_adr(artifact)
        elif artifact.artifact_type == "commit":
            return self._chunk_commit(artifact)
        else:
            # Fallback
            full_text = f"{artifact.title}\n{artifact.body}"
            chunks = self._split_by_tokens(full_text)
            repo_name = getattr(artifact.repository, "name", "unknown")
            return [
                Chunk(
                    chunk_id=str(uuid.uuid4()),
                    artifact_id=artifact.id,
                    artifact_type=artifact.artifact_type,
                    repository=repo_name,
                    chunk_type="full",
                    text=c,
                    author=artifact.author,
                    created_at=artifact.created_at,
                    url=artifact.url,
                    metadata={},
                )
                for c in chunks
            ]

    def _chunk_issue(self, artifact: Artifact) -> List[Chunk]:
        """Chunk an Issue into problem, discussion, and resolution."""
        chunks = []
        repo_name = getattr(artifact.repository, "name", "unknown")

        # 1. Problem Chunk
        body_lines = artifact.body.split("\n")
        first_para = ""
        for line in body_lines:
            if line.strip():
                first_para = line.strip()
                break
        problem_text = f"Issue #{artifact.external_id}: {artifact.title}\n\nDescription: {first_para}"
        chunks.append(
            Chunk(
                chunk_id=str(uuid.uuid4()),
                artifact_id=artifact.id,
                artifact_type="issue",
                repository=repo_name,
                chunk_type="problem",
                text=problem_text,
                author=artifact.author,
                created_at=artifact.created_at,
                url=artifact.url,
                metadata={},
            )
        )

        # 2. Discussion Chunk
        # Combine comments if present
        body_parts = artifact.body.split("\nComments:\n")
        discussion_body = body_parts[1] if len(body_parts) > 1 else ""
        if discussion_body:
            split_discussion = self._split_by_tokens(discussion_body)
            for c in split_discussion:
                chunks.append(
                    Chunk(
                        chunk_id=str(uuid.uuid4()),
                        artifact_id=artifact.id,
                        artifact_type="issue",
                        repository=repo_name,
                        chunk_type="discussion",
                        text=f"Discussion for Issue #{artifact.external_id}:\n{c}",
                        author="various",
                        created_at=artifact.created_at,
                        url=artifact.url,
                        metadata={},
                    )
                )

        # 3. Resolution Chunk
        state = artifact.metadata_fields.get("state", "open")
        labels = ", ".join(artifact.labels)
        res_text = (
            f"Resolution status for Issue #{artifact.external_id}:\n"
            f"State: {state}\n"
            f"Labels: {labels}\n"
            f"Closed at: {artifact.closed_at or 'N/A'}"
        )
        chunks.append(
            Chunk(
                chunk_id=str(uuid.uuid4()),
                artifact_id=artifact.id,
                artifact_type="issue",
                repository=repo_name,
                chunk_type="resolution",
                text=res_text,
                author=artifact.author,
                created_at=artifact.created_at,
                url=artifact.url,
                metadata={},
            )
        )

        return chunks

    def _chunk_pull_request(self, artifact: Artifact) -> List[Chunk]:
        """Chunk a Pull Request into purpose, implementation, alternatives, and outcome."""
        chunks = []
        repo_name = getattr(artifact.repository, "name", "unknown")

        # 1. Purpose Chunk
        desc_part = artifact.body.split("\nFiles modified:\n")[0]
        desc_lines = desc_part.split("\n\n")
        first_3_paras = "\n\n".join(desc_lines[:3])
        purpose_text = f"PR #{artifact.external_id} Purpose: {artifact.title}\n\n{first_3_paras}"
        chunks.append(
            Chunk(
                chunk_id=str(uuid.uuid4()),
                artifact_id=artifact.id,
                artifact_type="pull_request",
                repository=repo_name,
                chunk_type="purpose",
                text=purpose_text,
                author=artifact.author,
                created_at=artifact.created_at,
                url=artifact.url,
                metadata={},
            )
        )

        # 2. Alternatives Chunk (if alternatives exist)
        alt_text = self._detect_alternatives_section(artifact.body)
        if alt_text:
            chunks.append(
                Chunk(
                    chunk_id=str(uuid.uuid4()),
                    artifact_id=artifact.id,
                    artifact_type="pull_request",
                    repository=repo_name,
                    chunk_type="alternatives",
                    text=f"PR #{artifact.external_id} Alternatives Considered:\n{alt_text}",
                    author=artifact.author,
                    created_at=artifact.created_at,
                    url=artifact.url,
                    metadata={},
                )
            )

        # 3. Implementation Chunk
        changed_files = artifact.metadata_fields.get("changed_files", [])
        impl_text = (
            f"PR #{artifact.external_id} Implementation details:\n"
            f"Files Changed: {', '.join(changed_files[:10])}{' and more' if len(changed_files) > 10 else ''}\n"
            f"Technical Description: {artifact.body[:1000]}"
        )
        chunks.append(
            Chunk(
                chunk_id=str(uuid.uuid4()),
                artifact_id=artifact.id,
                artifact_type="pull_request",
                repository=repo_name,
                chunk_type="implementation",
                text=impl_text,
                author=artifact.author,
                created_at=artifact.created_at,
                url=artifact.url,
                metadata={},
            )
        )

        # 4. Outcome Chunk
        merged = artifact.metadata_fields.get("merged", False)
        state = artifact.metadata_fields.get("state", "open")
        outcome_text = (
            f"PR #{artifact.external_id} Outcome:\n"
            f"Merged: {merged}\n"
            f"State: {state}\n"
            f"Merged at: {artifact.merged_at or 'N/A'}\n"
            f"Closed at: {artifact.closed_at or 'N/A'}"
        )
        chunks.append(
            Chunk(
                chunk_id=str(uuid.uuid4()),
                artifact_id=artifact.id,
                artifact_type="pull_request",
                repository=repo_name,
                chunk_type="outcome",
                text=outcome_text,
                author=artifact.author,
                created_at=artifact.created_at,
                url=artifact.url,
                metadata={},
            )
        )

        return chunks

    def _chunk_adr(self, artifact: Artifact) -> List[Chunk]:
        """Chunk an ADR by splitting into standard markdown headers."""
        chunks = []
        repo_name = getattr(artifact.repository, "name", "unknown")

        sections = {
            "context": ["## Context", "## context", "### Context"],
            "decision": ["## Decision", "## decision", "### Decision"],
            "alternatives": ["## Alternatives Considered", "## alternatives", "### Alternatives", "## Alternatives"],
            "consequences": ["## Consequences", "## consequences", "### Consequences"],
        }

        body = artifact.body
        found_any = False

        for chunk_type, headers in sections.items():
            # Find start and end of this section
            start_idx = -1
            found_header = ""
            for h in headers:
                start_idx = body.find(h)
                if start_idx != -1:
                    found_header = h
                    break

            if start_idx != -1:
                found_any = True
                # Section goes from header start to next header starting with '##'
                remaining_body = body[start_idx + len(found_header) :]
                next_header_match = re.search(r"\n## ", remaining_body)
                if next_header_match:
                    section_text = remaining_body[: next_header_match.start()]
                else:
                    section_text = remaining_body

                section_text = section_text.strip()
                chunks.append(
                    Chunk(
                        chunk_id=str(uuid.uuid4()),
                        artifact_id=artifact.id,
                        artifact_type="adr",
                        repository=repo_name,
                        chunk_type=chunk_type,
                        text=f"ADR: {artifact.title}\nSection: {chunk_type.upper()}\n\n{section_text}",
                        author=artifact.author,
                        created_at=artifact.created_at,
                        url=artifact.url,
                        metadata={},
                    )
                )

        if not found_any:
            # Fallback to splitting standard token chunks
            split_chunks = self._split_by_tokens(body)
            for c in split_chunks:
                chunks.append(
                    Chunk(
                        chunk_id=str(uuid.uuid4()),
                        artifact_id=artifact.id,
                        artifact_type="adr",
                        repository=repo_name,
                        chunk_type="full",
                        text=f"ADR: {artifact.title}\n\n{c}",
                        author=artifact.author,
                        created_at=artifact.created_at,
                        url=artifact.url,
                        metadata={},
                    )
                )

        return chunks

    def _chunk_commit(self, artifact: Artifact) -> List[Chunk]:
        """Chunk a Commit into a single chunk."""
        repo_name = getattr(artifact.repository, "name", "unknown")
        files = artifact.metadata_fields.get("files_changed", [])
        commit_text = (
            f"Commit: {artifact.title}\n"
            f"Author: {artifact.author}\n"
            f"Date: {artifact.created_at}\n"
            f"Details: {artifact.body}"
        )
        return [
            Chunk(
                chunk_id=str(uuid.uuid4()),
                artifact_id=artifact.id,
                artifact_type="commit",
                repository=repo_name,
                chunk_type="full",
                text=commit_text,
                author=artifact.author,
                created_at=artifact.created_at,
                url=artifact.url,
                metadata={"files_changed": files},
            )
        ]

    def _split_by_tokens(self, text: str, max_tokens: int = 512) -> List[str]:
        """Split text into sentences, grouping sentences under max_tokens limit with 50-token overlap."""
        # Split on sentence boundaries
        sentence_end = re.compile(r"(?<=[.!?])\s+")
        sentences = sentence_end.split(text)

        chunks = []
        current_chunk_words = []
        current_word_count = 0
        overlap_sentences = []

        for sentence in sentences:
            sentence_words = sentence.split()
            sentence_word_count = len(sentence_words)

            if not sentence_words:
                continue

            # If a single sentence exceeds the max limit, split it by words
            if sentence_word_count > max_tokens:
                if current_chunk_words:
                    chunks.append(" ".join(current_chunk_words))
                    current_chunk_words = []
                    current_word_count = 0
                for i in range(0, sentence_word_count, max_tokens - 50):
                    chunks.append(" ".join(sentence_words[i : i + max_tokens]))
                continue

            if current_word_count + sentence_word_count > max_tokens:
                chunks.append(" ".join(current_chunk_words))
                # Set up overlap for next chunk
                # Take last few sentences that approximate ~50 words
                overlap_words = []
                overlap_count = 0
                for s in reversed(overlap_sentences):
                    s_words = s.split()
                    if overlap_count + len(s_words) <= 50:
                        overlap_words = s_words + overlap_words
                        overlap_count += len(s_words)
                    else:
                        break
                current_chunk_words = overlap_words + sentence_words
                current_word_count = len(current_chunk_words)
                overlap_sentences = [sentence]
            else:
                current_chunk_words.extend(sentence_words)
                current_word_count += sentence_word_count
                overlap_sentences.append(sentence)

        if current_chunk_words:
            chunks.append(" ".join(current_chunk_words))

        return chunks

    def _detect_alternatives_section(self, text: str) -> Optional[str]:
        """Detect any paragraphs or sentences focusing on alternative designs or rejected options."""
        # Find paragraphs with decision keywords
        keywords = ["instead", "alternative", "considered", "rejected", "opted for"]
        paragraphs = text.split("\n\n")
        matched_paras = []

        for p in paragraphs:
            low_p = p.lower()
            if any(k in low_p for k in keywords):
                matched_paras.append(p.strip())

        if matched_paras:
            return "\n\n".join(matched_paras[:3])
        return None
import re
