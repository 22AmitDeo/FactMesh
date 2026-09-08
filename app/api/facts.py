"""Fact search, filtering, and evidence grounding API endpoints."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.storage.db import get_db
from app.models.database import FactModel, DocumentModel, RelationModel
from app.services.pdf_parser import PDFParser

router = APIRouter(prefix="/api/facts", tags=["facts"])


@router.get("")
def list_facts(
    doc_id: Optional[str] = Query(None, description="Filter by document ID"),
    search: Optional[str] = Query(None, description="Search subject, predicate, value, or quote"),
    subject: Optional[str] = Query(None, description="Filter by exact subject"),
    time_scope: Optional[str] = Query(None, description="Filter by time scope"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Retrieves facts with dynamic filtering and evidence grounding."""
    query = db.query(FactModel)

    if doc_id:
        query = query.filter(FactModel.doc_id == doc_id)
    if subject:
        query = query.filter(FactModel.subject.ilike(f"%{subject}%"))
    if time_scope:
        query = query.filter(FactModel.time_scope.ilike(f"%{time_scope}%"))
    if search:
        search_pat = f"%{search}%"
        query = query.filter(
            or_(
                FactModel.subject.ilike(search_pat),
                FactModel.predicate.ilike(search_pat),
                FactModel.value.ilike(search_pat),
                FactModel.quote.ilike(search_pat),
            )
        )

    total = query.count()
    facts = query.order_by(FactModel.created_at.desc()).offset(skip).limit(limit).all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "facts": [f.to_dict() for f in facts],
    }


@router.get("/{fact_id}")
def get_fact(fact_id: str, db: Session = Depends(get_db)):
    """Retrieves fact detail including spatial bounding box and full page evidence text."""
    fact = db.query(FactModel).filter_by(id=fact_id).first()
    if not fact:
        raise HTTPException(status_code=404, detail="Fact not found")

    data = fact.to_dict()

    # Enrich with full page text if document is available
    if fact.document and fact.document.file_path:
        try:
            pages = list(PDFParser.stream_pages(fact.document.file_path))
            if 0 < fact.page <= len(pages):
                data["page_full_text"] = pages[fact.page - 1].text
        except Exception:
            data["page_full_text"] = None

    return data


@router.get("/{fact_id}/relations")
def get_fact_relations(fact_id: str, db: Session = Depends(get_db)):
    """Retrieves all cross-document relationships where this fact is a participant."""
    fact = db.query(FactModel).filter_by(id=fact_id).first()
    if not fact:
        raise HTTPException(status_code=404, detail="Fact not found")

    relations = db.query(RelationModel).filter(
        or_(RelationModel.fact_id_a == fact_id, RelationModel.fact_id_b == fact_id)
    ).all()

    return [r.to_dict() for r in relations]
