"""Vector embedding service and incremental ANN similarity index."""

import logging
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Computes dense vector representations for facts and queries."""

    _instance = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EmbeddingService, cls).__new__(cls)
            cls._instance._load_model()
        return cls._instance

    def _load_model(self):
        """Loads sentence-transformers model."""
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL}")
            self._model = SentenceTransformer(settings.EMBEDDING_MODEL)
        except Exception as e:
            logger.error(f"Failed to load sentence-transformers: {e}. Using deterministic fallback.")
            self._model = None

    def embed_text(self, text: str) -> np.ndarray:
        """Embeds arbitrary text and returns a unit-normalized vector."""
        clean_text = text.strip() if text else ""
        if self._model is not None:
            raw_vec = self._model.encode(clean_text, convert_to_numpy=True)
            norm = np.linalg.norm(raw_vec)
            if norm > 0:
                return (raw_vec / norm).astype(np.float32)
            return raw_vec.astype(np.float32)
        else:
            # Fallback deterministic pseudo-embedding for zero-dependency / emergency mode
            import hashlib
            vec = np.zeros(384, dtype=np.float32)
            for word in clean_text.lower().split():
                h = int(hashlib.md5(word.encode()).hexdigest(), 16)
                idx = h % 384
                vec[idx] += 1.0
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec /= norm
            return vec

    def embed_fact(self, subject: str, predicate: str, value: str) -> np.ndarray:
        """Produces canonical embedding for a fact triple."""
        canonical_str = f"{subject} {predicate} {value}".strip()
        return self.embed_text(canonical_str)


class IncrementalVectorIndex:
    """
    Incremental in-memory ANN vector index for candidate retrieval.
    Scales linearly with new documents without O(N^2) rescans.
    """

    def __init__(self):
        # fact_id -> {"doc_id": doc_id, "vector": np.ndarray, "text": text}
        self.entries: Dict[str, Dict[str, Any]] = {}

    def add_fact(self, fact_id: str, doc_id: str, vector: np.ndarray, text: str = "") -> None:
        """Incrementally adds a new fact embedding to the index."""
        # Ensure float32 and unit norm
        norm = np.linalg.norm(vector)
        norm_vec = (vector / norm).astype(np.float32) if norm > 0 else vector.astype(np.float32)
        self.entries[fact_id] = {
            "doc_id": doc_id,
            "vector": norm_vec,
            "text": text,
        }

    def remove_fact(self, fact_id: str) -> None:
        """Removes a fact from the index."""
        self.entries.pop(fact_id, None)

    def clear(self) -> None:
        """Clears all indexed vectors."""
        self.entries.clear()

    def search_candidates(
        self,
        query_vector: np.ndarray,
        exclude_doc_id: Optional[str] = None,
        top_k: int = 5,
        min_similarity: float = 0.50,
    ) -> List[Tuple[str, float]]:
        """
        Searches the existing index for top-k most similar candidate facts.
        Excludes facts originating from the same document (cross-document focus).
        Returns list of (fact_id, similarity_score) sorted descending by similarity.
        """
        if not self.entries:
            return []

        # Ensure query vector is unit normalized
        norm = np.linalg.norm(query_vector)
        q_vec = (query_vector / norm).astype(np.float32) if norm > 0 else query_vector.astype(np.float32)

        candidates = []
        for fid, entry in self.entries.items():
            if exclude_doc_id is not None and entry["doc_id"] == exclude_doc_id:
                continue

            sim = float(np.dot(q_vec, entry["vector"]))
            if sim >= min_similarity:
                candidates.append((fid, round(sim, 4)))

        # Sort descending by similarity
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[:top_k]


# Global singleton instances
embedding_service = EmbeddingService()
vector_index = IncrementalVectorIndex()
