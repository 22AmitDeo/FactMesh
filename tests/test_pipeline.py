import pytest
import fitz
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.database import Base, DocumentModel, FactModel, RelationModel
from app.services.pipeline import IngestionPipeline
from app.services.embeddings import vector_index

@pytest.fixture
def db_session():
    test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, echo=False)
    Base.metadata.create_all(test_engine)
    Session = sessionmaker(bind=test_engine)
    session = Session()
    vector_index.clear()
    try:
        yield session
    finally:
        session.close()
        vector_index.clear()


@pytest.fixture
def test_pdf(tmp_path: Path) -> Path:
    p = tmp_path / "test_pipeline_doc.pdf"
    doc = fitz.open()
    
    page1 = doc.new_page()
    page1.insert_text((50, 100), "Delhivery Limited Financial Report.\nIn FY24, revenue from operations grew to INR 8,142 Crores.", fontsize=11)
    
    page2 = doc.new_page()
    page2.insert_text((50, 100), "Network Summary:\nFull-time headcount stood at 31,200 employees as of March 31, 2024.", fontsize=11)
    
    doc.save(str(p))
    doc.close()
    return p


@pytest.mark.asyncio
async def test_end_to_end_pipeline_processing(db_session, test_pdf: Path):
    doc = await IngestionPipeline.process_document(
        db=db_session,
        file_path=test_pdf,
        filename="test_pipeline_doc.pdf",
    )
    assert doc.status == "ready"
    assert doc.page_count == 2
    
    facts = db_session.query(FactModel).filter_by(doc_id=doc.id).all()
    assert len(facts) >= 2
    
    # Check grounding
    grounded_fact = facts[0]
    assert grounded_fact.quote
    assert grounded_fact.char_start >= 0
    assert grounded_fact.bbox is not None
