"""Database models for Document, Fact, and Relation with dynamic JSON schema support."""

import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class DocumentModel(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True)  # UUID string
    filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    page_count = Column(Integer, default=0)
    file_size = Column(Integer, default=0)
    status = Column(String(50), default="processing")  # processing, ready, failed
    error_message = Column(Text, nullable=True)
    uploaded_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))

    facts = relationship("FactModel", back_populates="document", cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "filename": self.filename,
            "file_path": self.file_path,
            "page_count": self.page_count,
            "file_size": self.file_size,
            "status": self.status,
            "error_message": self.error_message,
            "uploaded_at": self.uploaded_at.isoformat() if self.uploaded_at else None,
            "fact_count": len(self.facts) if self.facts else 0,
        }


class FactModel(Base):
    __tablename__ = "facts"

    id = Column(String(36), primary_key=True)
    doc_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    page = Column(Integer, nullable=False)
    char_start = Column(Integer, default=-1)
    char_end = Column(Integer, default=-1)
    bbox = Column(JSON, nullable=True)  # [x0, y0, x1, y1]
    normalized_bbox = Column(JSON, nullable=True)  # [nx0, ny0, nx1, ny1]
    quote = Column(Text, nullable=False)
    subject = Column(String(255), nullable=False, index=True)
    predicate = Column(String(255), nullable=False)
    value = Column(Text, nullable=False)
    unit = Column(String(100), nullable=True)
    time_scope = Column(String(100), nullable=True, index=True)
    confidence = Column(Float, default=1.0)
    is_hallucinated_quote = Column(Boolean, default=False)
    validation_notes = Column(Text, nullable=True)
    
    # Dynamic schema brownie point: open JSON column
    extra = Column(JSON, default=dict)
    
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))

    document = relationship("DocumentModel", back_populates="facts")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "doc_id": self.doc_id,
            "doc_name": self.document.filename if self.document else None,
            "page": self.page,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "bbox": self.bbox,
            "normalized_bbox": self.normalized_bbox,
            "quote": self.quote,
            "subject": self.subject,
            "predicate": self.predicate,
            "value": self.value,
            "unit": self.unit,
            "time_scope": self.time_scope,
            "confidence": self.confidence,
            "is_hallucinated_quote": self.is_hallucinated_quote,
            "validation_notes": self.validation_notes,
            "extra": self.extra or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class RelationModel(Base):
    __tablename__ = "relations"

    id = Column(String(36), primary_key=True)
    fact_id_a = Column(String(36), ForeignKey("facts.id", ondelete="CASCADE"), nullable=False, index=True)
    fact_id_b = Column(String(36), ForeignKey("facts.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String(50), nullable=False, index=True)  # corroborates, contradicts, reconciled, unrelated
    difference_type = Column(String(100), default="none")  # time_scope, unit, value_mismatch, none
    explanation = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))

    fact_a = relationship("FactModel", foreign_keys=[fact_id_a])
    fact_b = relationship("FactModel", foreign_keys=[fact_id_b])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "fact_id_a": self.fact_id_a,
            "fact_id_b": self.fact_id_b,
            "type": self.type,
            "difference_type": self.difference_type,
            "explanation": self.explanation,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "fact_a": self.fact_a.to_dict() if self.fact_a else None,
            "fact_b": self.fact_b.to_dict() if self.fact_b else None,
        }
