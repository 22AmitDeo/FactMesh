import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.database import Base, DocumentModel, FactModel, RelationModel

@pytest.fixture
def db_session():
    # In-memory SQLite for testing
    test_engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(test_engine)
    Session = sessionmaker(bind=test_engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_document_and_dynamic_fact_storage(db_session):
    doc_id = str(uuid.uuid4())
    doc = DocumentModel(
        id=doc_id,
        filename="delhivery_q4_fy24.pdf",
        file_path="/tmp/delhivery_q4_fy24.pdf",
        page_count=27,
        file_size=1024000,
        status="ready",
    )
    db_session.add(doc)
    db_session.commit()

    # Fact with dynamic schema in `extra`
    fact_id = str(uuid.uuid4())
    dynamic_metadata = {
        "entity_type": "Logistics Company",
        "auditing_firm": "KPMG",
        "currency": "INR",
        "segment": "Express Parcel",
        "unanticipated_new_field": "test_dynamic_value"
    }

    fact = FactModel(
        id=fact_id,
        doc_id=doc_id,
        page=12,
        char_start=150,
        char_end=210,
        bbox=[45.0, 120.0, 520.0, 140.0],
        quote="Express parcel shipments grew by 18% year over year.",
        subject="express parcel shipments",
        predicate="grew by",
        value="18%",
        unit="%",
        time_scope="FY24",
        extra=dynamic_metadata,
    )
    db_session.add(fact)
    db_session.commit()

    # Query back and verify dynamic extra was stored as JSON without migration
    saved_fact = db_session.query(FactModel).filter_by(id=fact_id).first()
    assert saved_fact is not None
    assert saved_fact.extra["segment"] == "Express Parcel"
    assert saved_fact.extra["unanticipated_new_field"] == "test_dynamic_value"
    assert saved_fact.document.filename == "delhivery_q4_fy24.pdf"


def test_relation_creation(db_session):
    doc_id = str(uuid.uuid4())
    doc = DocumentModel(id=doc_id, filename="doc.pdf", file_path="doc.pdf")
    db_session.add(doc)

    fact_a = FactModel(
        id=str(uuid.uuid4()),
        doc_id=doc_id,
        page=1,
        quote="Revenue was 1000",
        subject="Revenue",
        predicate="was",
        value="1000",
    )
    fact_b = FactModel(
        id=str(uuid.uuid4()),
        doc_id=doc_id,
        page=2,
        quote="Revenue reached 1000",
        subject="Revenue",
        predicate="reached",
        value="1000",
    )
    db_session.add_all([fact_a, fact_b])
    db_session.commit()

    relation = RelationModel(
        id=str(uuid.uuid4()),
        fact_id_a=fact_a.id,
        fact_id_b=fact_b.id,
        type="corroborates",
        difference_type="none",
        explanation="Both documents corroborate revenue of 1000.",
    )
    db_session.add(relation)
    db_session.commit()

    saved_rel = db_session.query(RelationModel).first()
    assert saved_rel.type == "corroborates"
    assert saved_rel.fact_a.value == "1000"
    assert saved_rel.fact_b.value == "1000"
