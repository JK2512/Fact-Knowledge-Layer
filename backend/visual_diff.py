"""
Visual Document Diff & Page Image Renderer.
Renders high-resolution PDF page images with highlighted bounding boxes
for side-by-side visual document comparison and evidence auditing.
"""

import io
import re
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
import fitz  # PyMuPDF

from backend.config import UPLOAD_DIR, DATA_DIR
from backend.database import get_all_documents, get_all_facts, get_relationship_by_id


def find_pdf_path(filename: str) -> Optional[Path]:
    """Locate the PDF file across uploads and starter-datasets directories."""
    # 1. Check upload dir
    p = UPLOAD_DIR / filename
    if p.exists():
        return p

    # 2. Check starter-datasets recursively
    base = Path(__file__).resolve().parent.parent
    for candidate in base.glob(f"**/{filename}"):
        if candidate.is_file():
            return candidate

    return None


def find_best_page_and_rects(doc: fitz.Document, initial_page: int, query: Optional[str]) -> Tuple[int, List[fitz.Rect]]:
    """Resolve the true physical PDF page and precise bounding box coordinates for a metric query."""
    if not query or not query.strip():
        return max(0, min(initial_page, len(doc) - 1)), []

    q = query.strip()
    # Extract core numeric token (e.g. "6.25", "42.27", "740", "50,765.87")
    num_match = re.search(r'[\d,]+(?:\.\d+)?', q)
    num_str = num_match.group(0) if num_match else ''
    num_clean = num_str.replace(',', '')

    # 1. Try initial specified page
    if 0 <= initial_page < len(doc):
        p = doc[initial_page]
        # Exact query match
        rects = p.search_for(q)
        if rects:
            return initial_page, rects
        # Number with unit
        if num_str and len(num_str) >= 2:
            rects = p.search_for(num_str)
            if rects:
                return initial_page, rects
        if num_clean and num_clean != num_str and len(num_clean) >= 2:
            rects = p.search_for(num_clean)
            if rects:
                return initial_page, rects

    # 2. Scan document to find the exact matching page (handles printed page vs physical page offset)
    for idx, p in enumerate(doc):
        rects = p.search_for(q)
        if rects:
            return idx, rects

    if num_str and len(num_str) >= 2:
        for idx, p in enumerate(doc):
            rects = p.search_for(num_str)
            if rects:
                return idx, rects
            if num_clean and num_clean != num_str:
                rects = p.search_for(num_clean)
                if rects:
                    return idx, rects

    # Fallback to initial page without bogus partial-word rects
    return max(0, min(initial_page, len(doc) - 1)), []


def render_annotated_page_image(
    filename: str,
    page_num: int,
    highlight_text: Optional[str] = None,
    color_type: str = "contradiction",
    dpi: int = 150,
) -> Optional[bytes]:
    """Render a PDF page to PNG with highlighted bounding boxes."""
    pdf_path = find_pdf_path(filename)
    if not pdf_path or not pdf_path.exists():
        return None

    try:
        doc = fitz.open(str(pdf_path))
        target_page_idx = max(0, min(page_num - 1, len(doc) - 1))

        # Resolve exact physical page and bounding box coordinates
        resolved_page_idx, rects_to_highlight = find_best_page_and_rects(doc, target_page_idx, highlight_text)
        page = doc[resolved_page_idx]

        # Colors for annotations (RGB tuple 0.0 - 1.0)
        color_palette = {
            "contradiction": {
                "stroke": (0.93, 0.15, 0.15),  # Crimson Red
                "fill": (1.0, 0.85, 0.85),
            },
            "corroboration": {
                "stroke": (0.09, 0.63, 0.36),  # Emerald Green
                "fill": (0.85, 0.98, 0.90),
            },
            "reconciliation": {
                "stroke": (0.58, 0.20, 0.83),  # Royal Purple
                "fill": (0.94, 0.88, 1.0),
            },
            "default": {
                "stroke": (0.15, 0.38, 0.92),  # Blue
                "fill": (0.85, 0.92, 1.0),
            }
        }
        colors = color_palette.get(color_type.lower(), color_palette["default"])

        # Draw highlight annotations onto page
        for r in rects_to_highlight[:5]:
            pad_rect = fitz.Rect(r.x0 - 4, r.y0 - 2, r.x1 + 4, r.y1 + 2)
            annot = page.add_rect_annot(pad_rect)
            annot.set_colors(stroke=colors["stroke"], fill=colors["fill"])
            annot.set_border(width=3.0)
            annot.set_opacity(0.85)
            annot.update()

        # Render page to PNG pixmap
        pix = page.get_pixmap(dpi=dpi)
        img_bytes = pix.tobytes("png")
        doc.close()
        return img_bytes

    except Exception as e:
        print(f"Error rendering PDF page image for {filename}: {e}")
        return None


def get_visual_comparison_pair(rel_id: str) -> Optional[Dict[str, Any]]:
    """Build side-by-side visual comparison payload for a relationship."""
    rel = get_relationship_by_id(rel_id)
    if not rel:
        return None

    fact_ids = rel.get("fact_ids", [])
    if isinstance(fact_ids, str):
        import json
        fact_ids = json.loads(fact_ids)

    all_facts = {f["id"]: f for f in get_all_facts()}
    docs = {d["id"]: d["filename"] for d in get_all_documents()}

    linked_facts = [all_facts[fid] for fid in fact_ids if fid in all_facts]
    if len(linked_facts) < 2:
        return None

    f1 = linked_facts[0]
    f2 = linked_facts[1]

    doc1_name = docs.get(f1.get("document_id"), "Document 1")
    doc2_name = docs.get(f2.get("document_id"), "Document 2")

    return {
        "relationship_id": rel.get("id"),
        "relationship_type": rel.get("relationship_type"),
        "reasoning": rel.get("reasoning"),
        "confidence": rel.get("confidence"),
        "doc1": {
            "filename": doc1_name,
            "page": f1.get("source_page", 1),
            "metric": f1.get("subject", ""),
            "value": f1.get("value", ""),
            "quote": f1.get("source_text", ""),
            "image_url": f"/api/visual-diff/page?document={doc1_name}&page={f1.get('source_page', 1)}&highlight={f1.get('value', '')}&color={rel.get('relationship_type')}",
        },
        "doc2": {
            "filename": doc2_name,
            "page": f2.get("source_page", 1),
            "metric": f2.get("subject", ""),
            "value": f2.get("value", ""),
            "quote": f2.get("source_text", ""),
            "image_url": f"/api/visual-diff/page?document={doc2_name}&page={f2.get('source_page', 1)}&highlight={f2.get('value', '')}&color={rel.get('relationship_type')}",
        }
    }
