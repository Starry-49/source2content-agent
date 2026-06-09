from __future__ import annotations

import hashlib
import json
import re
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from app.models import RetrievalHit, SourceRecord, new_id
from app.retrieval import HybridRetriever


class ContentState(TypedDict, total=False):
    run_id: str
    objective: str
    audience: str
    tone: str
    sources: list[SourceRecord]
    source_registry: list[dict[str, Any]]
    retrieval_hits: list[dict[str, Any]]
    content_brief: str
    slide_plan: list[dict[str, Any]]
    article_draft: str
    validation_errors: list[str]
    status: str
    artifacts: dict[str, str]


def source_registry_node(state: ContentState) -> ContentState:
    registry = []
    for source in state.get("sources", []):
        digest = hashlib.sha256(source.body.encode("utf-8")).hexdigest()[:12]
        registry.append(
            {
                "source_id": source.source_id,
                "title": source.title,
                "kind": source.kind,
                "char_count": len(source.body),
                "digest": digest,
                "metadata": source.metadata,
            }
        )
    return {"source_registry": registry}


def retrieval_node(state: ContentState) -> ContentState:
    sources = state.get("sources", [])
    query = " ".join([state.get("objective", ""), state.get("audience", ""), "content plan evidence workflow"])
    retriever = HybridRetriever(sources)
    hits = [hit.model_dump() for hit in retriever.search(query, top_k=min(4, len(sources)))]
    return {"retrieval_hits": hits}


def brief_node(state: ContentState) -> ContentState:
    hits = [RetrievalHit(**hit) for hit in state.get("retrieval_hits", [])]
    lines = [
        "# Content Brief",
        "",
        f"Objective: {state.get('objective', '')}",
        f"Audience: {state.get('audience', '')}",
        f"Tone: {state.get('tone', '')}",
        "",
        "## Source-grounded angles",
    ]
    for index, hit in enumerate(hits, start=1):
        lines.append(f"- [{hit.source_id}] {hit.title}: {hit.excerpt}")
    lines.extend(
        [
            "",
            "## Boundary rules",
            "- Claims must be traceable to listed source ids.",
            "- Drafts should separate source-backed facts from generated framing.",
            "- Missing evidence should be surfaced as a validation note, not filled by guesswork.",
        ]
    )
    return {"content_brief": "\n".join(lines)}


def planning_node(state: ContentState) -> ContentState:
    hits = [RetrievalHit(**hit) for hit in state.get("retrieval_hits", [])]
    slide_plan = [
        {
            "slide": 1,
            "title": "Why this content exists",
            "purpose": "Set objective, audience, and source boundary.",
            "source_ids": [hit.source_id for hit in hits[:2]],
        },
        {
            "slide": 2,
            "title": "Knowledge base and retrieval flow",
            "purpose": "Explain how source material is registered, indexed, and retrieved.",
            "source_ids": [hit.source_id for hit in hits[:3]],
        },
        {
            "slide": 3,
            "title": "Content generation plan",
            "purpose": "Turn source evidence into a draft structure with reusable sections.",
            "source_ids": [hit.source_id for hit in hits[:2]],
        },
        {
            "slide": 4,
            "title": "Validation and fallback",
            "purpose": "Show citation checks and boundary handling before handoff.",
            "source_ids": [hit.source_id for hit in hits[-2:]],
        },
    ]
    return {"slide_plan": slide_plan}


def draft_node(state: ContentState) -> ContentState:
    hits = [RetrievalHit(**hit) for hit in state.get("retrieval_hits", [])]
    intro_sources = ", ".join(f"[{hit.source_id}]" for hit in hits[:2]) or "[no-source]"
    body = [
        "# Article Draft",
        "",
        "## Opening",
        f"This draft turns a compact source set into reusable content artifacts for {state.get('audience', 'reviewers')} {intro_sources}.",
        "",
        "## Source-grounded workflow",
    ]
    for hit in hits:
        body.append(
            f"- {hit.title} contributes evidence for the workflow through: {hit.excerpt} [{hit.source_id}]"
        )
    body.extend(
        [
            "",
            "## Handoff",
            "The generated brief, slide plan, and source registry should be reviewed together before publication.",
        ]
    )
    return {"article_draft": "\n".join(body)}


def validation_node(state: ContentState) -> ContentState:
    source_ids = {item["source_id"] for item in state.get("source_registry", [])}
    artifacts = [
        state.get("content_brief", ""),
        json.dumps(state.get("slide_plan", []), ensure_ascii=False),
        state.get("article_draft", ""),
    ]
    citations = set(re.findall(r"\[([A-Za-z0-9_-]+)\]", "\n".join(artifacts)))
    errors: list[str] = []
    missing = sorted(citation for citation in citations if citation not in source_ids)
    if missing:
        errors.append(f"Unknown citation ids: {', '.join(missing)}")
    if len(state.get("retrieval_hits", [])) == 0:
        errors.append("No retrieval hits were available for content generation.")
    if len(source_ids) < 2:
        errors.append("At least two sources are recommended for a grounded content run.")
    return {"validation_errors": errors, "status": "fallback" if errors else "ok"}


def should_fallback(state: ContentState) -> str:
    return "fallback" if state.get("validation_errors") else "ok"


def fallback_node(state: ContentState) -> ContentState:
    warning = "\n".join(f"- {error}" for error in state.get("validation_errors", []))
    brief = state.get("content_brief", "")
    return {
        "content_brief": f"{brief}\n\n## Validation fallback\n{warning}".strip(),
        "article_draft": "# Article Draft\n\nGeneration stopped before publication because validation failed.",
        "slide_plan": [],
        "status": "fallback",
    }


def artifact_node(state: ContentState) -> ContentState:
    artifacts = {
        "content_brief.md": state.get("content_brief", ""),
        "slide_plan.json": json.dumps(state.get("slide_plan", []), ensure_ascii=False, indent=2),
        "article_draft.md": state.get("article_draft", ""),
        "source_registry.json": json.dumps(state.get("source_registry", []), ensure_ascii=False, indent=2),
        "validation_report.json": json.dumps(
            {
                "status": state.get("status", "fallback"),
                "validation_errors": state.get("validation_errors", []),
            },
            ensure_ascii=False,
            indent=2,
        ),
    }
    return {"artifacts": artifacts}


def build_graph():
    graph = StateGraph(ContentState)
    graph.add_node("source_registry", source_registry_node)
    graph.add_node("retrieve", retrieval_node)
    graph.add_node("brief", brief_node)
    graph.add_node("plan", planning_node)
    graph.add_node("draft", draft_node)
    graph.add_node("validate", validation_node)
    graph.add_node("fallback", fallback_node)
    graph.add_node("artifacts", artifact_node)

    graph.set_entry_point("source_registry")
    graph.add_edge("source_registry", "retrieve")
    graph.add_edge("retrieve", "brief")
    graph.add_edge("brief", "plan")
    graph.add_edge("plan", "draft")
    graph.add_edge("draft", "validate")
    graph.add_conditional_edges("validate", should_fallback, {"ok": "artifacts", "fallback": "fallback"})
    graph.add_edge("fallback", "artifacts")
    graph.add_edge("artifacts", END)
    return graph.compile()


def run_pipeline(
    sources: list[SourceRecord],
    objective: str,
    audience: str,
    tone: str,
    run_id: str | None = None,
) -> ContentState:
    compiled = build_graph()
    state: ContentState = {
        "run_id": run_id or new_id("run"),
        "sources": sources,
        "objective": objective,
        "audience": audience,
        "tone": tone,
    }
    return compiled.invoke(state)

