import pytest
import fitz
from pathlib import Path
from app.services.pdf_parser import PDFParser

@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    pdf_path = tmp_path / "sample_financial_report.pdf"
    doc = fitz.open()
    
    # Page 1
    page1 = doc.new_page(width=595, height=842)
    p1_text = (
        "Delhivery Limited\n"
        "Annual Financial Highlights FY2024\n"
        "In FY24, Delhivery express parcel volume crossed 740 million shipments.\n"
        "Revenue from operations grew to INR 8,142 Crores."
    )
    page1.insert_text((50, 80), p1_text, fontsize=12)
    
    # Page 2
    page2 = doc.new_page(width=595, height=842)
    p2_text = (
        "Operational Network\n"
        "The company operated 24 automated sort centers across India.\n"
        "Full-time employee headcount stood at 31,200 as of March 31, 2024."
    )
    page2.insert_text((50, 80), p2_text, fontsize=12)
    
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


def test_pdf_info(sample_pdf: Path):
    info = PDFParser.get_document_info(sample_pdf)
    assert info["page_count"] == 2


def test_pdf_streaming(sample_pdf: Path):
    pages = list(PDFParser.stream_pages(sample_pdf))
    assert len(pages) == 2
    assert "740 million shipments" in pages[0].text
    assert "automated sort centers" in pages[1].text


def test_locate_quote_in_page(sample_pdf: Path):
    quote = "express parcel volume crossed 740 million shipments"
    loc = PDFParser.locate_quote_in_page(sample_pdf, page_num=1, quote=quote)
    assert loc["found"] is True
    assert loc["char_start"] >= 0
    assert loc["char_end"] > loc["char_start"]
    assert loc["bbox"] is not None
    assert len(loc["bbox"]) == 4
    # Verify coordinates are positive and valid
    assert loc["bbox"][0] > 0
    assert loc["bbox"][2] > loc["bbox"][0]
