import pytest
import numpy as np
from app.services.embeddings import EmbeddingService, IncrementalVectorIndex

def test_embedding_normalization():
    service = EmbeddingService()
    vec = service.embed_text("Delhivery delivered 740 million packages.")
    assert isinstance(vec, np.ndarray)
    assert len(vec) == 384
    norm = np.linalg.norm(vec)
    assert pytest.approx(norm, abs=1e-4) == 1.0


def test_semantic_similarity_matching():
    service = EmbeddingService()
    v1 = service.embed_text("Revenue from operations reached INR 8,142 Crores.")
    v2 = service.embed_text("Total operating revenue grew to 8,142 Crores.")
    v_unrelated = service.embed_text("The weather was sunny in Bengaluru yesterday.")

    sim_close = float(np.dot(v1, v2))
    sim_unrelated = float(np.dot(v1, v_unrelated))

    assert sim_close > 0.70
    assert sim_unrelated < 0.40
    assert sim_close > sim_unrelated


def test_incremental_vector_index():
    service = EmbeddingService()
    index = IncrementalVectorIndex()

    v_a = service.embed_fact("Express parcel volume", "reached", "740 million")
    v_b = service.embed_fact("Operating revenue", "reached", "8,142 Crores")
    v_c = service.embed_fact("Parcel deliveries", "exceeded", "740 million")

    # Add facts from doc 1
    index.add_fact("fact_1", "doc_1", v_a, "Express parcel volume reached 740 million")
    index.add_fact("fact_2", "doc_1", v_b, "Operating revenue reached 8,142 Crores")

    # Query from doc 2 with v_c (should match fact_1 from doc_1)
    candidates = index.search_candidates(v_c, exclude_doc_id="doc_2", top_k=2, min_similarity=0.50)
    assert len(candidates) > 0
    top_match_id, score = candidates[0]
    assert top_match_id == "fact_1"
    assert score > 0.65

    # Should not match own document facts
    no_candidates = index.search_candidates(v_c, exclude_doc_id="doc_1", top_k=2)
    assert len(no_candidates) == 0
