from datetime import datetime
from uuid import uuid4
from app.models.artifact import Artifact
from app.services.chunking.chunking_engine import ChunkingEngine


def test_issue_produces_problem_chunk():
    engine = ChunkingEngine()
    artifact = Artifact(
        id=uuid4(),
        artifact_type="issue",
        external_id="101",
        title="Database lock timeout",
        body="High load causes lock timeout on payments table.",
        author="alice",
        created_at=datetime.utcnow(),
        metadata_fields={"state": "open"},
        labels=[],
    )

    chunks = engine.chunk_artifact(artifact)
    types = [c.chunk_type for c in chunks]

    assert "problem" in types
    problem_chunk = next(c for c in chunks if c.chunk_type == "problem")
    assert "lock timeout" in problem_chunk.text


def test_issue_with_comments_produces_discussion_chunk():
    engine = ChunkingEngine()
    artifact = Artifact(
        id=uuid4(),
        artifact_type="issue",
        external_id="102",
        title="Add auth middleware",
        body="We need JWT verification.\nComments:\n[2026-06-01] bob: We should use PyJWT.\n[2026-06-02] charlie: Agreed.",
        author="alice",
        created_at=datetime.utcnow(),
        metadata_fields={"state": "open"},
        labels=[],
    )

    chunks = engine.chunk_artifact(artifact)
    types = [c.chunk_type for c in chunks]

    assert "discussion" in types
    disc_chunk = next(c for c in chunks if c.chunk_type == "discussion")
    assert "bob" in disc_chunk.text
    assert "charlie" in disc_chunk.text


def test_adr_standard_sections_four_chunks():
    engine = ChunkingEngine()
    body = (
        "# ADR 1: Use Redis Cache\n\n"
        "## Context\n"
        "Database is overloaded with session queries.\n\n"
        "## Decision\n"
        "We decided to implement Redis cache.\n\n"
        "## Alternatives Considered\n"
        "Memcached was considered but lacked persistence.\n\n"
        "## Consequences\n"
        "Redis introduces another infrastructure dependency."
    )
    artifact = Artifact(
        id=uuid4(),
        artifact_type="adr",
        external_id="docs/adr/001.md",
        title="Use Redis Cache",
        body=body,
        author="system",
        created_at=datetime.utcnow(),
        metadata_fields={},
        labels=[],
    )

    chunks = engine.chunk_artifact(artifact)
    types = [c.chunk_type for c in chunks]

    assert "context" in types
    assert "decision" in types
    assert "alternatives" in types
    assert "consequences" in types
    assert len(chunks) == 4


def test_adr_no_sections_falls_back_to_full():
    engine = ChunkingEngine()
    artifact = Artifact(
        id=uuid4(),
        artifact_type="adr",
        external_id="docs/adr/002.md",
        title="Alternative design doc",
        body="Just some plain text without markdown headings describing architectural decisions.",
        author="alice",
        created_at=datetime.utcnow(),
        metadata_fields={},
        labels=[],
    )

    chunks = engine.chunk_artifact(artifact)
    types = [c.chunk_type for c in chunks]

    assert "full" in types
    assert len(chunks) >= 1


def test_pr_with_alternatives_text_produces_alternatives_chunk():
    engine = ChunkingEngine()
    artifact = Artifact(
        id=uuid4(),
        artifact_type="pull_request",
        external_id="15",
        title="Use PostgreSQL for spatial indexes",
        body=(
            "We need geo querying capabilities.\n\n"
            "We considered MongoDB but rejected it because PostgreSQL PostGIS is more robust."
        ),
        author="bob",
        created_at=datetime.utcnow(),
        metadata_fields={"changed_files": []},
        labels=[],
    )

    chunks = engine.chunk_artifact(artifact)
    types = [c.chunk_type for c in chunks]

    assert "alternatives" in types
    alt_chunk = next(c for c in chunks if c.chunk_type == "alternatives")
    assert "MongoDB" in alt_chunk.text


def test_commit_is_single_chunk():
    engine = ChunkingEngine()
    artifact = Artifact(
        id=uuid4(),
        artifact_type="commit",
        external_id="abcdef123456",
        title="fix memory leak in websocket connection",
        body="Close connections on client disconnect to prevent leakage.",
        author="bob",
        created_at=datetime.utcnow(),
        metadata_fields={"files_changed": ["ws.py"]},
        labels=[],
    )

    chunks = engine.chunk_artifact(artifact)
    assert len(chunks) == 1
    assert chunks[0].chunk_type == "full"
    assert "websocket" in chunks[0].text


def test_long_text_split_under_512_tokens():
    engine = ChunkingEngine()
    # Create a long text: 600 words
    long_text = " ".join(["word"] * 600) + "."
    split_chunks = engine._split_by_tokens(long_text, max_tokens=512)

    assert len(split_chunks) > 1
    # Check that each chunk is within limits
    for chunk in split_chunks:
        assert len(chunk.split()) <= 512
