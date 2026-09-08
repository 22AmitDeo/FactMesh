import pytest
from app.services.extractor import FactExtractor, ExtractedFact

def test_ground_and_verify_fact_exact_match():
    page_text = (
        "Delhivery Limited Annual Report.\n"
        "In FY24, revenue from operations grew to INR 8,142 Crores, representing a growth of 13%."
    )
    fact = ExtractedFact(
        subject="revenue from operations",
        predicate="grew to",
        value="INR 8,142 Crores",
        quote="revenue from operations grew to INR 8,142 Crores",
        unit="INR Crores",
        time_scope="FY24",
    )
    FactExtractor._ground_and_verify_fact(fact, page_text, page_num=1)
    
    assert fact.is_hallucinated_quote is False
    assert fact.char_start >= 0
    assert fact.char_end > fact.char_start
    assert page_text[fact.char_start:fact.char_end] == fact.quote


def test_ground_and_verify_fact_hallucination_detection():
    page_text = (
        "Delhivery Limited Annual Report.\n"
        "The company operates nationwide delivery networks."
    )
    fact = ExtractedFact(
        subject="quarterly profit",
        predicate="skyrocketed to",
        value="$500 Million",
        quote="quarterly profit skyrocketed to $500 Million across all continents",
    )
    FactExtractor._ground_and_verify_fact(fact, page_text, page_num=1)
    
    assert fact.is_hallucinated_quote is True
    assert fact.confidence <= 0.30
    assert "Hallucination Guard" in (fact.validation_notes or "")


def test_fact_extraction_pipeline():
    page_text = (
        "Operational Overview:\n"
        "Full-time headcount stood at 31,200 employees as of March 31, 2024."
    )
    facts = FactExtractor.extract_facts_from_page(page_text, page_num=1)
    assert len(facts) > 0
    first = facts[0]
    assert first.subject
    assert first.predicate
    assert first.value
    assert first.quote in page_text
