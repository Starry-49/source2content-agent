from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.models import SourceInput, SourceRecord, new_id


class WorkspaceStore:
    def __init__(self, root: Path | None = None) -> None:
        default_root = Path(os.getenv("SOURCE2CONTENT_WORKSPACE", ".source2content"))
        self.root = root or default_root
        self.sources_dir = self.root / "sources"
        self.runs_dir = self.root / "runs"
        self.sources_dir.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def save_source(self, source_input: SourceInput) -> SourceRecord:
        source = SourceRecord(
            source_id=source_input.source_id or new_id("src"),
            title=source_input.title,
            kind=source_input.kind,
            body=source_input.body,
            metadata=source_input.metadata,
        )
        path = self.sources_dir / f"{source.source_id}.json"
        path.write_text(source.model_dump_json(indent=2), encoding="utf-8")
        return source

    def list_sources(self) -> list[SourceRecord]:
        sources: list[SourceRecord] = []
        for path in sorted(self.sources_dir.glob("*.json")):
            sources.append(SourceRecord.model_validate_json(path.read_text(encoding="utf-8")))
        return sources

    def get_sources(self, source_ids: list[str] | None = None) -> list[SourceRecord]:
        sources = self.list_sources()
        if source_ids is None:
            return sources
        wanted = set(source_ids)
        return [source for source in sources if source.source_id in wanted]

    def save_run_artifacts(self, run_id: str, artifacts: dict[str, str]) -> dict[str, str]:
        run_dir = self.runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        paths: dict[str, str] = {}
        for name, content in artifacts.items():
            path = run_dir / name
            path.write_text(content, encoding="utf-8")
            paths[name] = str(path)
        return paths

    def run_manifest(self, run_id: str) -> dict[str, Any]:
        run_dir = self.runs_dir / run_id
        if not run_dir.exists():
            raise FileNotFoundError(run_id)
        return {
            "run_id": run_id,
            "artifacts": {path.name: str(path) for path in sorted(run_dir.iterdir()) if path.is_file()},
        }

    def read_artifact(self, run_id: str, artifact_name: str) -> str:
        path = self.runs_dir / run_id / artifact_name
        if not path.exists():
            raise FileNotFoundError(f"{run_id}/{artifact_name}")
        return path.read_text(encoding="utf-8")

