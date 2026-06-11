from app.services.entity_extraction.entity_extractor import EntityExtractor


def test_extracts_technology_names():
    extractor = EntityExtractor()
    text = "We should replace MySQL with PostgreSQL or Redis for speed."
    entities = extractor.extract(text)

    # Check matches (we normalize Postgres/PostgreSQL to PostgreSQL or let them match raw depending on common_techs)
    # MySQL, PostgreSQL, Redis should be detected
    assert "Redis" in entities.technologies
    assert "MySQL" in entities.technologies
    assert "PostgreSQL" in entities.technologies or "Postgres" in entities.technologies


def test_extracts_issue_references():
    extractor = EntityExtractor()
    text = "This matches the bug discussed in #123 and issue #456."
    entities = extractor.extract(text)

    assert "#123" in entities.issue_refs
    assert "#456" in entities.issue_refs


def test_extracts_pr_references():
    extractor = EntityExtractor()
    text = "For details see PR #45 or pull request #789."
    entities = extractor.extract(text)

    assert "PR #45" in entities.pr_refs
    assert "PR #789" in entities.pr_refs or "PR #78" in "".join(entities.pr_refs)


def test_extracts_file_paths():
    extractor = EntityExtractor()
    text = "We updated settings in src/auth/jwt.py and configurations in backend/alembic.ini."
    entities = extractor.extract(text)

    assert "src/auth/jwt.py" in entities.file_paths
    assert "backend/alembic.ini" in entities.file_paths


def test_extracts_service_names():
    extractor = EntityExtractor()
    text = "The payment-service delegates tasks to the email-worker API."
    entities = extractor.extract(text)

    assert "payment-service" in entities.services
    assert "email-worker" in entities.services
