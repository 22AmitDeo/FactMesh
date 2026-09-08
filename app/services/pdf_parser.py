"""PDF parser service using PyMuPDF (fitz) with character and bounding box tracking."""

from typing import List, Dict, Any, Optional, Generator
from pathlib import Path
import fitz  # PyMuPDF


class ParsedPage:
    def __init__(
        self,
        page_num: int,
        text: str,
        width: float,
        height: float,
        blocks: Optional[List[Dict[str, Any]]] = None,
    ):
        self.page_num = page_num
        self.text = text
        self.width = width
        self.height = height
        self.blocks = blocks or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "page_num": self.page_num,
            "text": self.text,
            "width": self.width,
            "height": self.height,
            "block_count": len(self.blocks),
        }


class PDFParser:
    """Extracts text, character spans, and spatial bounding boxes from PDF documents."""

    @staticmethod
    def get_document_info(file_path: str | Path) -> Dict[str, Any]:
        """Returns metadata and total page count for a given PDF."""
        doc = fitz.open(str(file_path))
        info = {
            "page_count": len(doc),
            "title": doc.metadata.get("title") or Path(file_path).name,
            "author": doc.metadata.get("author") or "Unknown",
            "format": doc.metadata.get("format") or "PDF",
        }
        doc.close()
        return info

    @staticmethod
    def stream_pages(file_path: str | Path) -> Generator[ParsedPage, None, None]:
        """Streams pages one-by-one from a PDF file without loading the entire document at once."""
        doc = fitz.open(str(file_path))
        try:
            for page_index in range(len(doc)):
                page = doc[page_index]
                text = page.get_text("text")
                rect = page.rect
                
                # Extract text blocks with coordinates
                raw_blocks = page.get_text("blocks")
                blocks = []
                for b in raw_blocks:
                    # b: (x0, y0, x1, y1, text, block_no, block_type)
                    if len(b) >= 5 and isinstance(b[4], str) and b[4].strip():
                        blocks.append({
                            "bbox": [round(b[0], 2), round(b[1], 2), round(b[2], 2), round(b[3], 2)],
                            "text": b[4].strip(),
                            "block_id": b[5] if len(b) > 5 else 0,
                        })

                yield ParsedPage(
                    page_num=page_index + 1,
                    text=text,
                    width=rect.width,
                    height=rect.height,
                    blocks=blocks,
                )
        finally:
            doc.close()

    @staticmethod
    def locate_quote_in_page(
        file_path: str | Path,
        page_num: int,
        quote: str,
    ) -> Dict[str, Any]:
        """
        Locates the exact quote on a specific page of a PDF.
        Returns:
            {
                "found": bool,
                "char_start": int,
                "char_end": int,
                "bbox": [x0, y0, x1, y1],
                "normalized_bbox": [nx0, ny0, nx1, ny1],
                "matched_text": str
            }
        """
        clean_quote = quote.strip()
        if not clean_quote:
            return {"found": False, "char_start": -1, "char_end": -1, "bbox": None}

        doc = fitz.open(str(file_path))
        try:
            if page_num < 1 or page_num > len(doc):
                return {"found": False, "char_start": -1, "char_end": -1, "bbox": None}

            page = doc[page_num - 1]
            page_text = page.get_text("text")
            rect = page.rect

            # 1. Exact string search in raw page text for character offsets
            char_start = page_text.find(clean_quote)
            char_end = -1
            if char_start != -1:
                char_end = char_start + len(clean_quote)
            else:
                # Try normalized whitespace search
                import re
                norm_quote = " ".join(clean_quote.split())
                norm_text = " ".join(page_text.split())
                norm_start = norm_text.find(norm_quote)
                if norm_start != -1:
                    # Approximate in original text
                    char_start = 0
                    char_end = len(clean_quote)

            # 2. Coordinate search via PyMuPDF search_for
            rects = page.search_for(clean_quote)
            bbox = None
            norm_bbox = None

            if not rects:
                # If search for full quote fails (due to line breaks), search for first 6 words
                words = clean_quote.split()
                if len(words) > 3:
                    prefix = " ".join(words[:4])
                    rects = page.search_for(prefix)

            if rects:
                # Merge matching bounding boxes
                x0 = min(r.x0 for r in rects)
                y0 = min(r.y0 for r in rects)
                x1 = max(r.x1 for r in rects)
                y1 = max(r.y1 for r in rects)
                bbox = [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)]

                # Normalized coordinates (0.0 to 1.0)
                if rect.width > 0 and rect.height > 0:
                    norm_bbox = [
                        round(x0 / rect.width, 4),
                        round(y0 / rect.height, 4),
                        round(x1 / rect.width, 4),
                        round(y1 / rect.height, 4),
                    ]

            return {
                "found": (char_start != -1 or bbox is not None),
                "char_start": char_start,
                "char_end": char_end,
                "bbox": bbox,
                "normalized_bbox": norm_bbox,
                "page_width": rect.width,
                "page_height": rect.height,
            }
        finally:
            doc.close()
