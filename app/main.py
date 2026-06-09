from __future__ import annotations

import json
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse

from app import __version__
from app.models import ArtifactManifest, RunRequest, RunResponse, SourceIngestResponse, SourceInput
from app.pipeline import run_pipeline
from app.storage import WorkspaceStore


app = FastAPI(
    title="Source2Content Agent",
    version=__version__,
    summary="Source-grounded content workflow service for brief, slide plan, and article draft artifacts.",
)


def get_store() -> WorkspaceStore:
    if not hasattr(app.state, "store"):
        app.state.store = WorkspaceStore()
    return app.state.store


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "source2content-agent", "version": __version__}


@app.post("/sources", response_model=SourceIngestResponse)
def ingest_source(source: SourceInput, store: WorkspaceStore = Depends(get_store)) -> SourceIngestResponse:
    record = store.save_source(source)
    return SourceIngestResponse(
        source_id=record.source_id,
        title=record.title,
        kind=record.kind,
        char_count=len(record.body),
    )


@app.get("/sources")
def list_sources(store: WorkspaceStore = Depends(get_store)):
    return [source.model_dump(exclude={"body"}) for source in store.list_sources()]


@app.post("/runs", response_model=RunResponse)
def create_run(request: RunRequest, store: WorkspaceStore = Depends(get_store)) -> RunResponse:
    inline_sources = [store.save_source(source) for source in request.sources or []]
    stored_sources = store.get_sources(request.source_ids)
    sources = inline_sources or stored_sources
    if not sources:
        raise HTTPException(status_code=400, detail="No sources available. POST /sources first or pass inline sources.")

    state = run_pipeline(
        sources=sources,
        objective=request.objective,
        audience=request.audience,
        tone=request.tone,
    )
    artifact_paths = store.save_run_artifacts(state["run_id"], state["artifacts"])
    return RunResponse(
        run_id=state["run_id"],
        status=state["status"],  # type: ignore[arg-type]
        artifacts=artifact_paths,
        validation_errors=state.get("validation_errors", []),
        source_registry=state.get("source_registry", []),
    )


@app.get("/artifacts/{run_id}", response_model=ArtifactManifest)
def get_artifact_manifest(run_id: str, store: WorkspaceStore = Depends(get_store)) -> ArtifactManifest:
    try:
        manifest = store.run_manifest(run_id)
        report = json.loads(store.read_artifact(run_id, "validation_report.json"))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    registry = json.loads(store.read_artifact(run_id, "source_registry.json"))
    return ArtifactManifest(
        run_id=run_id,
        status=report.get("status", "fallback"),
        artifact_paths=manifest["artifacts"],
        validation_errors=report.get("validation_errors", []),
        source_count=len(registry),
    )


@app.get("/artifacts/{run_id}/{artifact_name}")
def get_artifact(run_id: str, artifact_name: str, store: WorkspaceStore = Depends(get_store)):
    try:
        content = store.read_artifact(run_id, artifact_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if Path(artifact_name).suffix == ".json":
        return JSONResponse(json.loads(content))
    return PlainTextResponse(content)

