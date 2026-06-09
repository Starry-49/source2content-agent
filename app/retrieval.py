from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass
from typing import Iterable

from rank_bm25 import BM25Okapi
from rapidfuzz import fuzz
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.models import RetrievalHit, SourceRecord


TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]")


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def excerpt(text: str, query: str, max_len: int = 260) -> str:
    if len(text) <= max_len:
        return text
    lower = text.lower()
    query_terms = tokenize(query)
    first_hit = min((lower.find(term) for term in query_terms if lower.find(term) >= 0), default=0)
    start = max(first_hit - 80, 0)
    snippet = text[start : start + max_len].strip()
    return f"{snippet}..."


@dataclass
class OptionalSemanticEncoder:
    model_name: str | None

    def __post_init__(self) -> None:
        self.model = None
        if not self.model_name or self.model_name.lower() == "disabled":
            return
        try:
            from sentence_transformers import SentenceTransformer

            self.model = SentenceTransformer(self.model_name)
        except Exception:
            self.model = None

    def available(self) -> bool:
        return self.model is not None

    def score(self, query: str, texts: list[str]) -> list[float]:
        if not self.model:
            return [0.0 for _ in texts]
        vectors = self.model.encode([query, *texts], normalize_embeddings=True)
        query_vec = vectors[0]
        return [float(query_vec @ vec) for vec in vectors[1:]]


class HybridRetriever:
    """Small hybrid retrieval index for mixed English/Chinese source materials."""

    def __init__(self, sources: Iterable[SourceRecord], semantic_model: str | None = None) -> None:
        self.sources = list(sources)
        self.documents = [f"{source.title}\n{source.body}" for source in self.sources]
        self.tokens = [tokenize(doc) for doc in self.documents]
        self.bm25 = BM25Okapi(self.tokens) if self.tokens else None
        self.vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=1)
        self.tfidf_matrix = self.vectorizer.fit_transform(self.documents) if self.documents else None
        model_name = semantic_model
        if model_name is None:
            model_name = os.getenv("SOURCE2CONTENT_SEMANTIC_MODEL", "disabled")
        self.semantic = OptionalSemanticEncoder(model_name)

    def search(self, query: str, top_k: int = 4) -> list[RetrievalHit]:
        if not self.sources:
            return []

        bm25_scores = self._bm25_scores(query)
        tfidf_scores = self._tfidf_scores(query)
        fuzzy_scores = self._fuzzy_scores(query)
        semantic_scores = self.semantic.score(query, self.documents)

        hits: list[RetrievalHit] = []
        for idx, source in enumerate(self.sources):
            reasons = {
                "bm25": bm25_scores[idx],
                "tfidf": tfidf_scores[idx],
                "rapidfuzz": fuzzy_scores[idx],
                "semantic": semantic_scores[idx],
            }
            score = (
                0.38 * reasons["bm25"]
                + 0.30 * reasons["tfidf"]
                + 0.20 * reasons["rapidfuzz"]
                + 0.12 * reasons["semantic"]
            )
            hits.append(
                RetrievalHit(
                    source_id=source.source_id,
                    title=source.title,
                    score=round(float(score), 4),
                    reasons={key: round(float(value), 4) for key, value in reasons.items()},
                    excerpt=excerpt(source.body, query),
                )
            )

        return sorted(hits, key=lambda hit: hit.score, reverse=True)[:top_k]

    def _bm25_scores(self, query: str) -> list[float]:
        if not self.bm25:
            return []
        raw = self.bm25.get_scores(tokenize(query))
        return self._normalize(raw)

    def _tfidf_scores(self, query: str) -> list[float]:
        if self.tfidf_matrix is None:
            return []
        query_vector = self.vectorizer.transform([query])
        raw = cosine_similarity(query_vector, self.tfidf_matrix)[0]
        return self._normalize(raw)

    def _fuzzy_scores(self, query: str) -> list[float]:
        raw = [fuzz.token_set_ratio(query, doc) / 100 for doc in self.documents]
        return self._normalize(raw)

    @staticmethod
    def _normalize(values: Iterable[float]) -> list[float]:
        values = [float(value) for value in values]
        if not values:
            return []
        max_value = max(values)
        min_value = min(values)
        if math.isclose(max_value, min_value):
            return [1.0 if max_value > 0 else 0.0 for _ in values]
        return [(value - min_value) / (max_value - min_value) for value in values]

