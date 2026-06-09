from __future__ import annotations

from pathlib import Path

from app.models import SourceInput, SourceRecord
from app.pipeline import run_pipeline


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DIR = ROOT / "data" / "sample_sources"
OUT_DIR = ROOT / "artifacts" / "sample_run"


def load_sources() -> list[SourceRecord]:
    sources: list[SourceRecord] = []
    for index, path in enumerate(sorted(SAMPLE_DIR.glob("*.md")), start=1):
        source = SourceInput(
            source_id=f"S{index}",
            title=path.stem.replace("_", " ").title(),
            kind="document",
            body=path.read_text(encoding="utf-8"),
            metadata={"path": str(path.relative_to(ROOT)), "sample": True},
        )
        sources.append(SourceRecord(**source.model_dump()))
    return sources


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    state = run_pipeline(
        sources=load_sources(),
        objective="Turn source-grounded AI workflow notes into a portfolio-ready content brief, slide plan, and article draft.",
        audience="AI Agent product and engineering reviewers",
        tone="concise, evidence-first, portfolio-friendly",
        run_id="sample_run",
    )
    for name, content in state["artifacts"].items():
        (OUT_DIR / name).write_text(content, encoding="utf-8")
    print(f"Generated {len(state['artifacts'])} artifacts in {OUT_DIR}")


if __name__ == "__main__":
    main()

