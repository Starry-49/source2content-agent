from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.storage import WorkspaceStore


def test_api_ingest_run_and_fetch_artifact(tmp_path: Path) -> None:
    app.state.store = WorkspaceStore(tmp_path)
    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    for payload in [
        {
            "source_id": "src_a",
            "title": "Knowledge workflow",
            "kind": "document",
            "body": "A source-grounded workflow registers evidence, retrieves context, drafts content, and validates citations.",
        },
        {
            "source_id": "src_b",
            "title": "Slide workflow",
            "kind": "document",
            "body": "A slide plan should separate source facts, generated structure, validation reports, and human review.",
        },
    ]:
        response = client.post("/sources", json=payload)
        assert response.status_code == 200

    run = client.post(
        "/runs",
        json={
            "objective": "Create a source-grounded slide and article plan",
            "audience": "AI product reviewers",
            "tone": "direct",
        },
    )
    assert run.status_code == 200
    body = run.json()
    assert body["status"] == "ok"

    manifest = client.get(f"/artifacts/{body['run_id']}")
    assert manifest.status_code == 200
    assert manifest.json()["source_count"] == 2

    artifact = client.get(f"/artifacts/{body['run_id']}/content_brief.md")
    assert artifact.status_code == 200
    assert "Content Brief" in artifact.text

