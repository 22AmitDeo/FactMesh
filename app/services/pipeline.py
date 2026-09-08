"""End-to-end document ingestion pipeline with page streaming and concurrency control."""

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.config import settings
from app.models.database import DocumentModel, FactModel, RelationModel
from app.services.pdf_parser import PDFParser, ParsedPage
from app.services.extractor import FactExtractor, ExtractedFact
from app.services.relation_engine import RelationEngine

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """Coordinates page streaming, bounded-concurrency fact extraction, and incremental relation matching."""

    @classmethod
    async def process_document(
        cls,
        db: Session,
        file_path: str | Path,
        filename: Optional[str] = None,
        doc_id: Optional[str] = None,
    ) -> DocumentModel:
        """
        Processes a PDF document end-to-end:
        1. Analyzes PDF metadata and page count.
        2. Streams pages and extracts facts concurrently with semaphore bounding.
        3. Saves facts to SQLite with character grounding and spatial bboxes.
        4. Incrementally discovers cross-document relationships without O(N^2) rebuild.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF file not found: {path}")

        actual_filename = filename or path.name
        actual_doc_id = doc_id or str(uuid.uuid4())
        file_size = path.stat().st_size

        # Create or update Document record
        doc = db.query(DocumentModel).filter_by(id=actual_doc_id).first()
        if not doc:
            doc = DocumentModel(
                id=actual_doc_id,
                filename=actual_filename,
                file_path=str(path),
                file_size=file_size,
                status="processing",
            )
            db.add(doc)
            db.commit()
            db.refresh(doc)

        try:
            # 1. Inspect document info
            info = PDFParser.get_document_info(path)
            doc.page_count = info.get("page_count", 0)
            db.commit()

            # 2. Concurrency semaphore for bounded LLM extraction
            semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_PAGES)
            
            async def process_single_page(page: ParsedPage) -> List[FactModel]:
                async with semaphore:
                    # Run extraction (blocking CPU/network call) in thread pool
                    loop = asyncio.get_event_loop()
                    extracted: List[ExtractedFact] = await loop.run_in_executor(
                        None,
                        FactExtractor.extract_facts_from_page,
                        page.text,
                        page.page_num,
                        str(path),
                    )

                    page_facts: List[FactModel] = []
                    for item in extracted:
                        fact_id = str(uuid.uuid4())
                        f_model = FactModel(
                            id=fact_id,
                            doc_id=doc.id,
                            page=page.page_num,
                            char_start=item.char_start,
                            char_end=item.char_end,
                            bbox=item.bbox,
                            normalized_bbox=item.normalized_bbox,
                            quote=item.quote,
                            subject=item.subject,
                            predicate=item.predicate,
                            value=item.value,
                            unit=item.unit,
                            time_scope=item.time_scope,
                            confidence=item.confidence,
                            is_hallucinated_quote=item.is_hallucinated_quote,
                            validation_notes=item.validation_notes,
                            extra=item.extra,
                        )
                        page_facts.append(f_model)
                    return page_facts

            # 3. Stream pages and launch concurrent tasks
            tasks = []
            for parsed_page in PDFParser.stream_pages(path):
                tasks.append(process_single_page(parsed_page))

            # Gather all extracted facts
            page_results = await asyncio.gather(*tasks)
            all_new_facts: List[FactModel] = []
            for fact_list in page_results:
                all_new_facts.extend(fact_list)

            # 4. Save facts to database
            for f in all_new_facts:
                db.add(f)
            db.commit()
            logger.info(f"Saved {len(all_new_facts)} facts for document '{doc.filename}'.")

            # 5. Incremental relation discovery against pre-existing facts
            RelationEngine.process_new_facts_incrementally(
                db,
                all_new_facts,
                top_k=settings.TOP_K_CANDIDATES,
                min_similarity=settings.SIMILARITY_THRESHOLD,
            )

            # Update document status to ready
            doc.status = "ready"
            db.commit()
            db.refresh(doc)
            return doc

        except Exception as e:
            logger.error(f"Failed to process document {actual_filename}: {e}", exc_info=True)
            doc.status = "failed"
            doc.error_message = str(e)
            db.commit()
            db.refresh(doc)
            return doc
