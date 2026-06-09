import json

from app.models import SourceRecord
from app.pipeline import run_pipeline


def test_pipeline_generates_source_grounded_artifacts() -> None:
    sources = [
        SourceRecord(
            source_id="src_synquest",
            title="SynQuest retrieval workflow",
            kind="document",
            body="SynQuest registers source material and uses hybrid retrieval to keep generated questions traceable.",
        ),
        SourceRecord(
            source_id="src_image2slides",
            title="Image2Slides content workflow",
            kind="document",
            body="Image2Slides separates source-locked facts, slide plans, generated narrative, and visual QA reports.",
        ),
    ]

    state = run_pipeline(
        sources=sources,
        objective="Create a source-grounded content plan",
        audience="AI workflow reviewers",
        tone="concise",
        run_id="run_test",
    )

    assert state["status"] == "ok"
    assert "content_brief.md" in state["artifacts"]
    assert "slide_plan.json" in state["artifacts"]
    assert "article_draft.md" in state["artifacts"]
    assert "source_registry.json" in state["artifacts"]
    registry = json.loads(state["artifacts"]["source_registry.json"])
    assert {item["source_id"] for item in registry} == {"src_synquest", "src_image2slides"}
    assert state["validation_errors"] == []


def test_pipeline_fallback_when_too_few_sources() -> None:
    sources = [
        SourceRecord(
            source_id="src_single",
            title="Single source",
            kind="document",
            body="A single source is not enough for this portfolio content workflow validation rule.",
        )
    ]

    state = run_pipeline(sources, "Draft content", "reviewers", "concise", run_id="run_single")

    assert state["status"] == "fallback"
    assert state["validation_errors"]
    assert "Validation fallback" in state["artifacts"]["content_brief.md"]

