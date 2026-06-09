from app.models import SourceRecord
from app.retrieval import HybridRetriever


def test_hybrid_retriever_ranks_relevant_source() -> None:
    sources = [
        SourceRecord(
            source_id="src_agent",
            title="Agent workflow validation",
            kind="document",
            body="Agent workflow requires source registry, verifier, handoff, and validation reports.",
        ),
        SourceRecord(
            source_id="src_lab",
            title="Wet lab protocol",
            kind="document",
            body="PCR protocol includes primer design, amplification, and gel electrophoresis.",
        ),
    ]

    hits = HybridRetriever(sources).search("agent verifier source registry", top_k=2)

    assert hits[0].source_id == "src_agent"
    assert hits[0].score > hits[1].score
    assert "bm25" in hits[0].reasons
    assert "tfidf" in hits[0].reasons
    assert "rapidfuzz" in hits[0].reasons
    assert "semantic" in hits[0].reasons

