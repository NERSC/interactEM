import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from interactem.app.core.config import settings
from interactem.app.models import PipelineRevision


def test_create_pipeline_creates_initial_revision(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test that creating a pipeline also creates revision 0."""
    data = {
        "data": {
            "operators": [],
            "edges": [],
        }
    }
    r = client.post(
        f"{settings.API_V1_STR}/pipelines/",
        headers=superuser_token_headers,
        json=data,
    )
    assert 200 <= r.status_code < 300
    created_pipeline = r.json()
    pipeline_id = created_pipeline["id"]

    # Verify pipeline was created with current_revision_id = 0
    assert created_pipeline["current_revision_id"] == 0

    # Verify that revision 0 actually exists in the database
    revision = db.get(PipelineRevision, (uuid.UUID(pipeline_id), 0))
    assert revision is not None
    assert revision.revision_id == 0
    assert revision.pipeline_id == uuid.UUID(pipeline_id)
    assert revision.data == data["data"]


def test_get_pipeline_revision_0(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test that we can retrieve revision 0 of a pipeline."""
    # Create a pipeline
    data = {
        "data": {
            "operators": [],
            "edges": [],
        }
    }
    r = client.post(
        f"{settings.API_V1_STR}/pipelines/",
        headers=superuser_token_headers,
        json=data,
    )
    assert 200 <= r.status_code < 300
    pipeline_id = r.json()["id"]

    # Get revision 0
    r = client.get(
        f"{settings.API_V1_STR}/pipelines/{pipeline_id}/revisions/0",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    revision = r.json()
    assert revision["revision_id"] == 0
    assert revision["pipeline_id"] == pipeline_id
    assert revision["data"] == data["data"]


def test_run_pipeline_revision_0(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test that we can run revision 0 of a pipeline."""
    # Create a pipeline
    data = {
        "data": {
            "operators": [],
            "edges": [],
        }
    }
    r = client.post(
        f"{settings.API_V1_STR}/pipelines/",
        headers=superuser_token_headers,
        json=data,
    )
    assert 200 <= r.status_code < 300
    pipeline_id = r.json()["id"]

    # Run revision 0
    r = client.post(
        f"{settings.API_V1_STR}/pipelines/{pipeline_id}/revisions/0/run",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    deployment = r.json()
    assert deployment["pipeline_id"] == pipeline_id
    assert deployment["revision_id"] == 0
    assert deployment["state"] == "PENDING"


def test_run_nonexistent_revision_returns_404(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test that running a non-existent revision returns 404."""
    # Create a pipeline
    data = {
        "data": {
            "operators": [],
            "edges": [],
        }
    }
    r = client.post(
        f"{settings.API_V1_STR}/pipelines/",
        headers=superuser_token_headers,
        json=data,
    )
    assert 200 <= r.status_code < 300
    pipeline_id = r.json()["id"]

    # Try to run a non-existent revision
    r = client.post(
        f"{settings.API_V1_STR}/pipelines/{pipeline_id}/revisions/999/run",
        headers=superuser_token_headers,
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "Pipeline revision not found"


def test_list_pipeline_revisions_includes_revision_0(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test that listing pipeline revisions includes revision 0."""
    # Create a pipeline
    data = {
        "data": {
            "operators": [],
            "edges": [],
        }
    }
    r = client.post(
        f"{settings.API_V1_STR}/pipelines/",
        headers=superuser_token_headers,
        json=data,
    )
    assert 200 <= r.status_code < 300
    pipeline_id = r.json()["id"]

    # List revisions
    r = client.get(
        f"{settings.API_V1_STR}/pipelines/{pipeline_id}/revisions",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    revisions = r.json()
    assert len(revisions) == 1
    assert revisions[0]["revision_id"] == 0
    assert revisions[0]["pipeline_id"] == pipeline_id


def test_add_revision_increments_from_0(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Test that adding a new revision correctly increments from revision 0."""
    # Create a pipeline
    data = {
        "data": {
            "operators": [],
            "edges": [],
        }
    }
    r = client.post(
        f"{settings.API_V1_STR}/pipelines/",
        headers=superuser_token_headers,
        json=data,
    )
    assert 200 <= r.status_code < 300
    pipeline_id = r.json()["id"]

    # Add a new revision
    new_data = {
        "data": {
            "operators": [
                {
                    "id": str(uuid.uuid4()),
                    "spec_id": "test-operator",
                    "version": "1.0.0",
                    "parameters": {},
                }
            ],
            "edges": [],
        }
    }
    r = client.post(
        f"{settings.API_V1_STR}/pipelines/{pipeline_id}/revisions",
        headers=superuser_token_headers,
        json=new_data,
    )
    assert r.status_code == 200
    new_revision = r.json()
    assert new_revision["revision_id"] == 1
    assert new_revision["pipeline_id"] == pipeline_id

    # Verify that both revisions exist
    r = client.get(
        f"{settings.API_V1_STR}/pipelines/{pipeline_id}/revisions",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    revisions = r.json()
    assert len(revisions) == 2
    revision_ids = [rev["revision_id"] for rev in revisions]
    assert 0 in revision_ids
    assert 1 in revision_ids
