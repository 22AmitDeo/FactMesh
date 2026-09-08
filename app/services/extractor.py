"""Fact extraction service with schema enforcement and quote hallucination detection."""

import logging
import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from app.services.llm_client import llm_client
from app.services.pdf_parser import PDFParser

logger = logging.getLogger(__name__)


class ExtractedFact(BaseModel):
    """Schema for extracted fact with evidence grounding and open extra metadata."""
    subject: str = Field(..., description="The entity or metric being described (e.g. 'Revenue from operations')")
    predicate: str = Field(..., description="The relation, action, or state (e.g. 'increased to', 'was appointed as')")
    value: str = Field(..., description="The value, quantity, status, or object")
    quote: str = Field(..., description="The verbatim excerpt from the document page serving as evidence")
    unit: Optional[str] = Field(None, description="Measurement unit (e.g. 'INR Crores', '%', 'Shipments')")
    time_scope: Optional[str] = Field(None, description="Time scope or period (e.g. 'FY24', 'Q4 FY24', 'March 31, 2024')")
    confidence: float = Field(1.0, description="Confidence score from 0.0 to 1.0")
    extra: Dict[str, Any] = Field(default_factory=dict, description="Dynamic open attributes")
    
    # Grounding metadata populated by validation
    char_start: int = -1
    char_end: int = -1
    bbox: Optional[List[float]] = None
    normalized_bbox: Optional[List[float]] = None
    is_hallucinated_quote: bool = False
    validation_notes: Optional[str] = None


class FactExtractor:
    """Extracts facts from page text and validates evidence quotes against ground-truth source."""

    SYSTEM_PROMPT = (
        "You are an expert financial and corporate document fact extraction engine.\n"
        "Extract all meaningful numerical, operational, and semantic facts from the provided text.\n"
        "RULES:\n"
        "1. Every fact MUST have subject, predicate, and value.\n"
        "2. The 'quote' field MUST be an EXACT VERBATIM SUBSTRING from the text. DO NOT rephrase or abbreviate quotes.\n"
        "3. Extract explicit units and time_scope whenever mentioned.\n"
        "4. Any additional contextual details (entity, currency, accounting standard, geography) must be placed in the 'extra' JSON object.\n"
        "5. Output JSON matching this schema: {\"facts\": [{\"subject\": \"...\", \"predicate\": \"...\", \"value\": \"...\", \"quote\": \"...\", \"unit\": \"...\", \"time_scope\": \"...\", \"extra\": {...}}]}"
    )

    @classmethod
    def extract_facts_from_page(
        cls,
        page_text: str,
        page_num: int,
        pdf_path: Optional[str] = None,
    ) -> List[ExtractedFact]:
        """
        Extracts facts from a page and validates quotes against the raw page text and PDF coordinates.
        """
        if not page_text or len(page_text.strip()) < 20:
            return []

        user_prompt = (
            f"Extract all key numerical, financial, and semantic facts from the text below.\n\n"
            f"--- PAGE TEXT ---\n"
            f"{page_text}\n"
            f"--- END PAGE TEXT ---\n\n"
            f"Ensure every quote is an exact verbatim substring from the text."
        )

        try:
            raw_response = llm_client.generate_json(user_prompt, system_instruction=cls.SYSTEM_PROMPT)
            raw_facts = raw_response.get("facts", []) if isinstance(raw_response, dict) else []
        except Exception as e:
            logger.error(f"Error during LLM fact generation on page {page_num}: {e}")
            raw_facts = []

        validated_facts: List[ExtractedFact] = []

        for item in raw_facts:
            try:
                # Dynamic open schema: ensure required fields exist
                subject = str(item.get("subject", "")).strip()
                predicate = str(item.get("predicate", "")).strip()
                value = str(item.get("value", "")).strip()
                quote = str(item.get("quote", "")).strip()

                if not subject or not predicate or not value:
                    continue

                unit = item.get("unit")
                time_scope = item.get("time_scope")
                extra = item.get("extra") if isinstance(item.get("extra"), dict) else {}

                # Create fact model
                fact = ExtractedFact(
                    subject=subject,
                    predicate=predicate,
                    value=value,
                    quote=quote,
                    unit=unit,
                    time_scope=time_scope,
                    confidence=float(item.get("confidence", 0.95)),
                    extra=extra,
                )

                # Grounding and quote hallucination detection
                cls._ground_and_verify_fact(fact, page_text, page_num, pdf_path)
                validated_facts.append(fact)

            except Exception as ex:
                logger.warning(f"Skipping malformed fact item: {ex}")

        return validated_facts

    @staticmethod
    def _ground_and_verify_fact(
        fact: ExtractedFact,
        page_text: str,
        page_num: int,
        pdf_path: Optional[str] = None,
    ) -> None:
        """
        Verifies that the quote is an authentic substring of the page text.
        If hallucinated or altered by the LLM, flags it clearly.
        """
        quote = fact.quote.strip()

        # Check exact substring
        idx = page_text.find(quote)
        if idx != -1:
            fact.char_start = idx
            fact.char_end = idx + len(quote)
            fact.is_hallucinated_quote = False
        else:
            # Check normalized whitespace match
            clean_page = " ".join(page_text.split())
            clean_quote = " ".join(quote.split())
            norm_idx = clean_page.find(clean_quote)

            if norm_idx != -1:
                # Approximate start in original text
                first_word = clean_quote.split()[0] if clean_quote.split() else ""
                approx_start = page_text.find(first_word)
                fact.char_start = max(0, approx_start)
                fact.char_end = fact.char_start + len(quote)
                fact.is_hallucinated_quote = False
            else:
                # Hallucination detected! The LLM produced a quote not present in the document.
                fact.is_hallucinated_quote = True
                fact.confidence = min(fact.confidence, 0.30)
                fact.validation_notes = (
                    f"Hallucination Guard: Evidence quote was not found as a verbatim substring in source page {page_num}."
                )

        # If PDF file path is available, obtain spatial coordinates (bbox)
        if pdf_path and not fact.is_hallucinated_quote:
            loc = PDFParser.locate_quote_in_page(pdf_path, page_num=page_num, quote=quote)
            if loc.get("found"):
                fact.bbox = loc.get("bbox")
                fact.normalized_bbox = loc.get("normalized_bbox")
                if fact.char_start == -1 and loc.get("char_start", -1) != -1:
                    fact.char_start = loc["char_start"]
                    fact.char_end = loc["char_end"]
