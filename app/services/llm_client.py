"""Multi-provider LLM client supporting Groq (primary), Gemini (fallback), and offline heuristics."""

import json
import logging
import re
from typing import Dict, Any, List, Optional
from app.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    """Manages LLM completions across Groq, Gemini, and offline heuristic modes."""

    def __init__(self):
        self.groq_client = None
        self.gemini_client = None
        
        if settings.GROQ_API_KEY:
            try:
                from groq import Groq
                self.groq_client = Groq(api_key=settings.GROQ_API_KEY)
                logger.info("Groq client initialized successfully.")
            except Exception as e:
                logger.warning(f"Failed to initialize Groq client: {e}")

        if settings.GEMINI_API_KEY:
            try:
                import google.generativeai as genai
                genai.configure(api_key=settings.GEMINI_API_KEY)
                self.gemini_client = genai.GenerativeModel(settings.GEMINI_MODEL)
                logger.info("Gemini client initialized successfully.")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini client: {e}")

    def generate_json(self, prompt: str, system_instruction: str = "") -> Any:
        """Generates structured JSON using Groq, Gemini, or heuristic fallback."""
        # 1. Try Groq (Primary choice)
        if self.groq_client:
            try:
                messages = []
                if system_instruction:
                    messages.append({"role": "system", "content": system_instruction})
                messages.append({"role": "user", "content": prompt})
                
                completion = self.groq_client.chat.completions.create(
                    model=settings.GROQ_MODEL,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.1,
                )
                content = completion.choices[0].message.content
                return self._parse_json(content)
            except Exception as e:
                logger.warning(f"Groq generation failed, attempting fallback: {e}")

        # 2. Try Gemini (Secondary fallback)
        if self.gemini_client:
            try:
                full_prompt = f"{system_instruction}\n\n{prompt}\n\nReturn response ONLY as valid JSON."
                response = self.gemini_client.generate_content(full_prompt)
                return self._parse_json(response.text)
            except Exception as e:
                logger.warning(f"Gemini generation failed: {e}")

        # 3. Deterministic Heuristic Fallback (For offline test suites and zero-key environments)
        return self._heuristic_fallback(prompt)

    def _parse_json(self, text: str) -> Any:
        """Strips markdown code fences and parses JSON securely."""
        clean = text.strip()
        if clean.startswith("```json"):
            clean = clean[7:]
        elif clean.startswith("```"):
            clean = clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        clean = clean.strip()
        return json.loads(clean)

    def _heuristic_fallback(self, prompt: str) -> Any:
        """
        Intelligent rule-based fallback for local offline testing when no LLM API key is present.
        Extracts factual sentences with numbers, currencies, dates, or organizational verbs.
        """
        # Relation reasoning prompt heuristic
        if "RELATIONSHIP ANALYSIS" in prompt or "Judge the relationship" in prompt:
            return self._heuristic_relation_judge(prompt)

        # Fact extraction prompt heuristic
        return self._heuristic_fact_extraction(prompt)

    def _heuristic_fact_extraction(self, prompt: str) -> Dict[str, Any]:
        """Heuristic fact extractor that locates grounded sentences with numerical or semantic facts."""
        facts = []
        # Find the text payload in the prompt
        text_match = re.search(r"--- PAGE TEXT ---\s*(.*?)\s*--- END PAGE TEXT ---", prompt, re.DOTALL)
        content = text_match.group(1) if text_match else prompt

        # Split into sentences
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", content) if len(s.strip()) > 15]

        # Pattern matches for metrics, dates, and organizational actions
        metric_patterns = [
            (r"(revenue|income|sales|turnover)\s+(from operations\s+)?(grew to|increased to|stood at|was|reached)\s+([₹$€INR\d\.,\s]+(?:Crores?|Cr|Millions?|Billions?|B|M|k)?)", "metric"),
            (r"(express parcel volume|shipment volume|volume)\s+(crossed|reached|stood at|was)\s+([\d\.,\s]+(?:million|billion|crore)?\s*(?:shipments|packages)?)", "operational"),
            (r"(headcount|workforce|employees?)\s+(stood at|was|reached)\s+([\d\.,\s]+)", "headcount"),
            (r"(automated sort centers?|service centers?|hubs?)\s+(stood at|was|numbered)\s+([\d\.,\s]+)", "network"),
            (r"([\w\s]+)\s+(was appointed|resigned as|serves as|became)\s+([\w\s]+)", "governance"),
        ]

        for s in sentences:
            # Check for year/period scope
            time_scope = None
            yr_match = re.search(r"\b(FY\s*\d{2,4}|20\d{2}(?:-\d{2,4})?|Q[1-4]\s*(?:FY\s*\d{2,4})?)\b", s, re.IGNORECASE)
            if yr_match:
                time_scope = yr_match.group(0).upper()

            matched = False
            for pat, category in metric_patterns:
                m = re.search(pat, s, re.IGNORECASE)
                if m:
                    subj = m.group(1).strip()
                    pred = m.group(len(m.groups()) - 1).strip()
                    val = m.group(len(m.groups())).strip()
                    
                    unit = None
                    if "crore" in val.lower() or "cr" in val.lower():
                        unit = "INR Crores"
                    elif "million" in val.lower() or "m" in val.lower():
                        unit = "Millions"

                    facts.append({
                        "subject": subj,
                        "predicate": pred,
                        "value": val,
                        "quote": s,
                        "unit": unit,
                        "time_scope": time_scope,
                        "extra": {
                            "category": category,
                            "extraction_mode": "heuristic_fallback",
                        }
                    })
                    matched = True
                    break

            if not matched and any(char.isdigit() for char in s) and len(s) < 160:
                # Generic fallback fact for sentences containing numbers
                words = s.split()
                if len(words) >= 4:
                    facts.append({
                        "subject": " ".join(words[:3]),
                        "predicate": "reported",
                        "value": " ".join(words[3:]),
                        "quote": s,
                        "unit": None,
                        "time_scope": time_scope,
                        "extra": {"extraction_mode": "heuristic_fallback_generic"}
                    })

        return {"facts": facts[:10]}

    def _heuristic_relation_judge(self, prompt: str) -> Dict[str, Any]:
        """Heuristic relationship reasoning between Fact A and Fact B."""
        # Extract section blocks for Fact A and Fact B
        part_a = prompt.split("--- FACT A ---")[1].split("--- FACT B ---")[0] if "--- FACT A ---" in prompt else ""
        part_b = prompt.split("--- FACT B ---")[1].split("Provide your judgment")[0] if "--- FACT B ---" in prompt else ""

        def extract_field(block: str, field_name: str) -> str:
            m = re.search(rf"{field_name}:\s*(.*?)(?:\n|$)", block, re.IGNORECASE)
            return m.group(1).strip() if m else ""

        val_a = extract_field(part_a, "Value").lower()
        val_b = extract_field(part_b, "Value").lower()
        time_a = extract_field(part_a, "Time Scope").lower()
        time_b = extract_field(part_b, "Time Scope").lower()
        subj_a = extract_field(part_a, "Subject").lower()
        subj_b = extract_field(part_b, "Subject").lower()

        # Case 1: Reconciled by context if time scopes differ (e.g. Q4 vs FY24)
        if (
            time_a != time_b
            and time_a not in ["n/a", "none", ""]
            and time_b not in ["n/a", "none", ""]
        ):
            return {
                "type": "reconciled",
                "difference_type": "time_scope",
                "explanation": f"Apparent contradiction between '{val_a}' and '{val_b}' is reconciled by differing reporting periods ({time_a.upper()} vs {time_b.upper()})."
            }

        # Case 2: Same or normalized numerical value -> corroborates
        norm_val_a = re.sub(r"[^\d\.]", "", val_a)
        norm_val_b = re.sub(r"[^\d\.]", "", val_b)
        if norm_val_a and norm_val_b and norm_val_a == norm_val_b:
            return {
                "type": "corroborates",
                "difference_type": "none",
                "explanation": f"Both documents corroborate equivalent values ({val_a} and {val_b}) for this metric."
            }

        # Case 3: Same scope, conflicting values -> contradicts
        if norm_val_a and norm_val_b and norm_val_a != norm_val_b:
            return {
                "type": "contradicts",
                "difference_type": "value_mismatch",
                "explanation": f"Direct contradiction on the same metric: Source reports {val_a} whereas other source reports {val_b}."
            }

        return {
            "type": "unrelated",
            "difference_type": "none",
            "explanation": "Facts discuss different aspects or insufficient overlap for direct relation."
        }


llm_client = LLMClient()
