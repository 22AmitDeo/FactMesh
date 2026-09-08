"""Incremental relationship engine with vector candidate filtering and LLM reasoning."""

import logging
import uuid
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.config import settings
from app.models.database import FactModel, RelationModel
from app.services.embeddings import embedding_service, vector_index
from app.services.llm_client import llm_client

logger = logging.getLogger(__name__)


class RelationJudgment:
    def __init__(self, type: str, difference_type: str, explanation: str):
        self.type = type  # corroborates, contradicts, reconciled, unrelated
        self.difference_type = difference_type  # time_scope, unit, scope, value_mismatch, none
        self.explanation = explanation

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "difference_type": self.difference_type,
            "explanation": self.explanation,
        }


class RelationEngine:
    """Discovers and classifies cross-document relationships using ANN search + LLM judgment."""

    SYSTEM_PROMPT = (
        "You are an expert financial and evidentiary analyst.\n"
        "Your role is to compare two facts extracted from corporate/institutional documents.\n"
        "Classify their relationship into one of four categories:\n"
        "1. 'corroborates': Both facts support the same underlying truth or state, even if phrased differently or using equivalent units.\n"
        "2. 'contradicts': Facts assert incompatible claims for the same metric, scope, and time period.\n"
        "3. 'reconciled': An apparent difference or conflict is fully explained by differing context (such as time scope: Q4 vs Full Year, currency, accounting standard, or geographic scope).\n"
        "4. 'unrelated': The facts do not directly describe the same underlying event or metric.\n\n"
        "Output ONLY valid JSON matching this schema:\n"
        "{\n"
        "  \"type\": \"corroborates\" | \"contradicts\" | \"reconciled\" | \"unrelated\",\n"
        "  \"difference_type\": \"time_scope\" | \"unit\" | \"geographic_scope\" | \"accounting_standard\" | \"value_mismatch\" | \"none\",\n"
        "  \"explanation\": \"Concise 1-2 sentence evidence-grounded explanation citing both facts.\"\n"
        "}"
    )

    @classmethod
    def judge_pair(cls, fact_a: FactModel, fact_b: FactModel) -> RelationJudgment:
        """Prompts the LLM (or heuristic engine) to judge relationship between Fact A and Fact B."""
        prompt = (
            f"Judge the relationship between Fact A and Fact B:\n\n"
            f"--- FACT A ---\n"
            f"Document: {fact_a.document.filename if fact_a.document else 'Doc A'}\n"
            f"Subject: {fact_a.subject}\n"
            f"Predicate: {fact_a.predicate}\n"
            f"Value: {fact_a.value}\n"
            f"Unit: {fact_a.unit or 'N/A'}\n"
            f"Time Scope: {fact_a.time_scope or 'N/A'}\n"
            f"Evidence Quote: \"{fact_a.quote}\"\n"
            f"Extra Context: {fact_a.extra}\n\n"
            f"--- FACT B ---\n"
            f"Document: {fact_b.document.filename if fact_b.document else 'Doc B'}\n"
            f"Subject: {fact_b.subject}\n"
            f"Predicate: {fact_b.predicate}\n"
            f"Value: {fact_b.value}\n"
            f"Unit: {fact_b.unit or 'N/A'}\n"
            f"Time Scope: {fact_b.time_scope or 'N/A'}\n"
            f"Evidence Quote: \"{fact_b.quote}\"\n"
            f"Extra Context: {fact_b.extra}\n\n"
            f"Provide your judgment as JSON."
        )

        try:
            res = llm_client.generate_json(prompt, system_instruction=cls.SYSTEM_PROMPT)
            rel_type = str(res.get("type", "unrelated")).lower().strip()
            diff_type = str(res.get("difference_type", "none")).strip()
            explanation = str(res.get("explanation", "Relationship evaluated.")).strip()

            if rel_type not in ["corroborates", "contradicts", "reconciled", "unrelated"]:
                rel_type = "unrelated"

            return RelationJudgment(type=rel_type, difference_type=diff_type, explanation=explanation)
        except Exception as e:
            logger.error(f"Error in relation judgment: {e}")
            return RelationJudgment(type="unrelated", difference_type="none", explanation="Evaluation error.")

    @classmethod
    def process_new_facts_incrementally(
        cls,
        db: Session,
        new_facts: List[FactModel],
        top_k: int = 5,
        min_similarity: float = 0.50,
    ) -> List[RelationModel]:
        """
        Incrementally processes newly ingested facts against the existing index.
        Only compares new facts to existing candidates (No O(N^2) rebuild).
        """
        discovered_relations: List[RelationModel] = []

        for new_fact in new_facts:
            # 1. Embed new fact
            v_new = embedding_service.embed_fact(new_fact.subject, new_fact.predicate, new_fact.value)
            
            # 2. ANN candidate search in existing vector index (excluding current document)
            candidates = vector_index.search_candidates(
                query_vector=v_new,
                exclude_doc_id=new_fact.doc_id,
                top_k=top_k,
                min_similarity=min_similarity,
            )

            # 3. Pairwise LLM evaluation for candidate matches
            for candidate_id, sim_score in candidates:
                candidate_fact = db.query(FactModel).filter_by(id=candidate_id).first()
                if not candidate_fact:
                    continue

                # Check if relation already exists
                existing = db.query(RelationModel).filter(
                    ((RelationModel.fact_id_a == new_fact.id) & (RelationModel.fact_id_b == candidate_fact.id)) |
                    ((RelationModel.fact_id_a == candidate_fact.id) & (RelationModel.fact_id_b == new_fact.id))
                ).first()

                if existing:
                    continue

                # LLM reasoning
                judgment = cls.judge_pair(new_fact, candidate_fact)
                
                if judgment.type in ["corroborates", "contradicts", "reconciled"]:
                    rel_id = str(uuid.uuid4())
                    relation = RelationModel(
                        id=rel_id,
                        fact_id_a=new_fact.id,
                        fact_id_b=candidate_fact.id,
                        type=judgment.type,
                        difference_type=judgment.difference_type,
                        explanation=judgment.explanation,
                    )
                    db.add(relation)
                    discovered_relations.append(relation)

            # 4. Add the new fact to the vector index so future documents can match against it
            vector_index.add_fact(
                fact_id=new_fact.id,
                doc_id=new_fact.doc_id,
                vector=v_new,
                text=f"{new_fact.subject} {new_fact.predicate} {new_fact.value}",
            )

        db.commit()
        return discovered_relations

    @classmethod
    def reindex_all_existing_facts(cls, db: Session) -> None:
        """Loads all existing facts from SQLite into the vector index on application startup."""
        facts = db.query(FactModel).all()
        vector_index.clear()
        for f in facts:
            v = embedding_service.embed_fact(f.subject, f.predicate, f.value)
            vector_index.add_fact(
                fact_id=f.id,
                doc_id=f.doc_id,
                vector=v,
                text=f"{f.subject} {f.predicate} {f.value}",
            )
        logger.info(f"Indexed {len(facts)} facts into vector store.")
