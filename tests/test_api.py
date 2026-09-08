import pytest
import io
import fitz
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.storage.db import init_db

@pytest.fixture(autouse=True)
def setup_test_database():
    init_db()


@pytest.fixture
def dummy_pdf_bytes():
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 100), "Delhivery Limited Q4 Report.\nQ4 revenue reached INR 2,076 Crores.", fontsize=11)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    buf.seek(0)
    return buf.read()


@pytest.mark.asyncio
async def test_demo_cases_api():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/demo/cases")
        assert response.status_code == 200
        data = response.json()
        assert "cases" in data
        assert len(data["cases"]) == 4
        # Verify categories of the 4 cases
        categories = [c["category"] for c in data["cases"]]
        assert "corroborates" in categories
        assert "contradicts" in categories
        assert "reconciled" in categories
        assert "failure_case" in categories


@pytest.mark.asyncio
async def test_relations_stats_api():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/relations/stats")
        assert response.status_code == 200
        data = response.json()
        assert "documents" in data
        assert "facts" in data
        assert "relations" in data
        assert "breakdown" in data


@pytest.mark.asyncio
async def test_document_upload_and_facts_api(dummy_pdf_bytes):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        files = {"file": ("test_doc.pdf", dummy_pdf_bytes, "application/pdf")}
        upload_resp = await client.post("/api/documents", files=files)
        assert upload_resp.status_code == 201
        doc_data = upload_resp.json()
        assert doc_data["filename"] == "test_doc.pdf"
        assert doc_data["status"] == "ready"

        # List documents
        list_resp = await client.get("/api/documents")
        assert list_resp.status_code == 200
        docs = list_resp.json()
        assert any(d["id"] == doc_data["id"] for d in docs)

        # Query facts
        facts_resp = await client.get(f"/api/facts?doc_id={doc_data['id']}")
        assert facts_resp.status_code == 200
        facts_data = facts_resp.json()
        assert facts_data["total"] > 0
