"""Document upload and inspection API endpoints."""

import shutil
import uuid
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.config import settings
from app.storage.db import get_db, SessionLocal
from app.models.database import DocumentModel, FactModel
from app.services.pipeline import IngestionPipeline

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("", status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Uploads a PDF and processes it through the fact knowledge pipeline."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    doc_id = str(uuid.uuid4())
    safe_filename = Path(file.filename).name
    save_path = settings.UPLOAD_DIR / f"{doc_id}_{safe_filename}"

    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Process document
    doc = await IngestionPipeline.process_document(
        db=db,
        file_path=save_path,
        filename=safe_filename,
        doc_id=doc_id,
    )

    return doc.to_dict()


@router.get("", response_model=List[dict])
def list_documents(db: Session = Depends(get_db)):
    """Lists all ingested documents with status and metadata."""
    docs = db.query(DocumentModel).order_by(DocumentModel.uploaded_at.desc()).all()
    return [d.to_dict() for d in docs]


@router.get("/{doc_id}")
def get_document(doc_id: str, db: Session = Depends(get_db)):
    """Retrieves single document detail and associated facts."""
    doc = db.query(DocumentModel).filter_by(id=doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    data = doc.to_dict()
    data["facts"] = [f.to_dict() for f in doc.facts]
    return data


@router.delete("/{doc_id}")
def delete_document(doc_id: str, db: Session = Depends(get_db)):
    """Deletes a document and cascades to its facts and relations."""
    doc = db.query(DocumentModel).filter_by(id=doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Remove file from disk if exists
    try:
        p = Path(doc.file_path)
        if p.exists():
            p.unlink()
    except Exception:
        pass

    db.delete(doc)
    db.commit()
    return {"message": "Document deleted successfully"}
