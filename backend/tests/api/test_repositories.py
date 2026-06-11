import pytest
from uuid import uuid4
from sqlalchemy import select
from app.models.repository import Repository


@pytest.mark.asyncio
async def test_ingest_valid_github_url_returns_202(async_client, db_session):
    payload = {"github_url": "https://github.com/tiangolo/fastapi", "branch": "master"}
    response = await async_client.post("/api/repositories/ingest", json=payload)

    assert response.status_code == 202
    data = response.json()
    assert "repository_id" in data
    assert data["status"] == "pending"

    # Verify database has repository record
    stmt = select(Repository).where(Repository.github_url == payload["github_url"])
    res = await db_session.execute(stmt)
    repo = res.scalar_one_or_none()
    assert repo is not None
    assert repo.status == "pending"


@pytest.mark.asyncio
async def test_ingest_invalid_url_returns_422(async_client):
    payload = {"github_url": "https://invalid-url.com/repo", "branch": "main"}
    response = await async_client.post("/api/repositories/ingest", json=payload)

    # Pydantic validation error or status 422
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_repositories_returns_200(async_client, db_session, sample_repository):
    # Add sample repository to database
    db_session.add(sample_repository)
    await db_session.commit()

    response = await async_client.get("/api/repositories")
    assert response.status_code == 200
    data = response.json()
    assert "repositories" in data
    assert data["total"] >= 1
    assert data["repositories"][0]["github_url"] == sample_repository.github_url


@pytest.mark.asyncio
async def test_get_repository_not_found_returns_404(async_client):
    random_id = str(uuid4())
    response = await async_client.get(f"/api/repositories/{random_id}")
    assert response.status_code == 404
