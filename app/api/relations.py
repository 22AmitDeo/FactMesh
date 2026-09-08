"""Cross-document relationships and knowledge graph statistics API endpoints."""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.storage.db import get_db
from app.models.database import RelationModel, FactModel, DocumentModel

router = APIRouter(prefix="/api/relations", tags=["relations"])


@router.get("")
def list_relations(
    type: Optional[str] = Query(None, description="Filter by type: corroborates, contradicts, reconciled"),
    doc_id: Optional[str] = Query(None, description="Filter by participating document"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Lists cross-document relationships with explanations and participating facts."""
    query = db.query(RelationModel)

    if type:
        query = query.filter(RelationModel.type == type.lower())

    if doc_id:
        query = query.join(FactModel, RelationModel.fact_id_a == FactModel.id).filter(
            FactModel.doc_id == doc_id
        )

    total = query.count()
    relations = query.order_by(RelationModel.created_at.desc()).offset(skip).limit(limit).all()

    return {
        "total": total,
        "relations": [r.to_dict() for r in relations],
    }


@router.get("/stats")
def get_knowledge_stats(db: Session = Depends(get_db)):
    """Computes high-level statistics across the fact knowledge layer."""
    doc_count = db.query(DocumentModel).count()
    fact_count = db.query(FactModel).count()
    rel_count = db.query(RelationModel).count()

    corroborates = db.query(RelationModel).filter_by(type="corroborates").count()
    contradicts = db.query(RelationModel).filter_by(type="contradicts").count()
    reconciled = db.query(RelationModel).filter_by(type="reconciled").count()
    
    hallucination_guards = db.query(FactModel).filter_by(is_hallucinated_quote=True).count()

    return {
        "documents": doc_count,
        "facts": fact_count,
        "relations": rel_count,
        "breakdown": {
            "corroborates": corroborates,
            "contradicts": contradicts,
            "reconciled": reconciled,
        },
        "hallucination_guards_triggered": hallucination_guards,
    }
