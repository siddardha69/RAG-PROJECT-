import pytest
from uuid import uuid4
from sqlalchemy import select
from app.models.artifact import Artifact
from app.models.query_log import QueryLog


@pytest.mark.asyncio
async def test_query_returns_response(async_client, db_session, sample_repository, sample_artifacts):
    # Add seed data
    db_session.add(sample_repository)
    for art in sample_artifacts:
        db_session.add(art)
    await db_session.commit()

    payload = {
        "question": "Why did we introduce Redis cache?",
        "repository_id": str(sample_repository.id),
        "include_recommendations": False,
    }

    # Since the mock embedding and search will return empty by default, the router returns a clean "Not enough evidence" response
    response = await async_client.post("/api/query", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "citations" in data
    assert "latency_ms" in data

    # Verify query log is written
    stmt = select(QueryLog).where(QueryLog.question == payload["question"])
    res = await db_session.execute(stmt)
    log = res.scalar_one_or_none()
    assert log is not None
    assert log.question == payload["question"]


@pytest.mark.asyncio
async def test_timeline_not_found_returns_404(async_client):
    random_id = str(uuid4())
    response = await async_client.get(f"/api/timeline/{random_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_recommendation_not_found_returns_404(async_client):
    random_id = str(uuid4())
    response = await async_client.get(f"/api/recommendations/{random_id}")
    assert response.status_code == 404
