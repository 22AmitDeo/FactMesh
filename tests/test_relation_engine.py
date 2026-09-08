import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.database import Base, DocumentModel, FactModel, RelationModel
from app.services.relation_engine import RelationEngine, RelationJudgment
from app.services.embeddings import vector_index

@pytest.fixture
def db_session():
    test_engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(test_engine)
    Session = sessionmaker(bind=test_engine)
    session = Session()
    vector_index.clear()
    try:
        yield session
    finally:
        session.close()
        vector_index.clear()


def test_relation_judgment_corroboration():
    fact_a = FactModel(
        id=str(uuid.uuid4()),
        doc_id="doc1",
        quote="In FY24, express parcel volume reached 740 million packages.",
        subject="express parcel volume",
        predicate="reached",
        value="740 million packages",
        time_scope="FY24",
    )
    fact_b = FactModel(
        id=str(uuid.uuid4()),
        doc_id="doc2",
        quote="Total package volume stood at 740 million packages in FY24.",
        subject="express parcel volume",
        predicate="stood at",
        value="740 million packages",
        time_scope="FY24",
    )
    judgment = RelationEngine.judge_pair(fact_a, fact_b)
    assert judgment.type == "corroborates"
    assert "740" in judgment.explanation


def test_relation_judgment_reconciliation():
    fact_q4 = FactModel(
        id=str(uuid.uuid4()),
        doc_id="doc_q4",
        quote="Q4 FY24 revenue from operations was INR 1,850 Crores.",
        subject="revenue from operations",
        predicate="was",
        value="INR 1,850 Crores",
        time_scope="Q4 FY24",
    )
    fact_fy = FactModel(
        id=str(uuid.uuid4()),
        doc_id="doc_fy",
        quote="Full fiscal year FY24 revenue from operations reached INR 8,142 Crores.",
        subject="revenue from operations",
        predicate="reached",
        value="INR 8,142 Crores",
        time_scope="FY24",
    )
    judgment = RelationEngine.judge_pair(fact_q4, fact_fy)
    assert judgment.type == "reconciled"
    assert judgment.difference_type == "time_scope"


def test_incremental_processing_workflow(db_session):
    # Doc 1
    doc1 = DocumentModel(id="doc1", filename="doc1.pdf", file_path="doc1.pdf")
    db_session.add(doc1)
    f1 = FactModel(
        id="f1",
        doc_id="doc1",
        page=1,
        quote="Employee headcount stood at 31,200 as of March 31, 2024.",
        subject="headcount",
        predicate="stood at",
        value="31,200",
        time_scope="FY24",
    )
    db_session.add(f1)
    db_session.commit()

    # Index doc 1
    RelationEngine.process_new_facts_incrementally(db_session, [f1], min_similarity=0.40)
    assert "f1" in vector_index.entries

    # Doc 2 with conflicting headcount
    doc2 = DocumentModel(id="doc2", filename="doc2.pdf", file_path="doc2.pdf")
    db_session.add(doc2)
    f2 = FactModel(
        id="f2",
        doc_id="doc2",
        page=2,
        quote="Headcount stood at 27,450 as of March 31, 2024.",
        subject="headcount",
        predicate="stood at",
        value="27,450",
        time_scope="FY24",
    )
    db_session.add(f2)
    db_session.commit()

    # Process doc 2 incrementally
    relations = RelationEngine.process_new_facts_incrementally(db_session, [f2], min_similarity=0.40)
    assert len(relations) == 1
    assert relations[0].type == "contradicts"
    assert relations[0].fact_id_a == "f2"
    assert relations[0].fact_id_b == "f1"
