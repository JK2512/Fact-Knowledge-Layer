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


def get_search_candidates(query: str) -> List[str]:
    """Generate search candidates from query (exact text, number only, number with commas, etc.)."""
    candidates = []
    q_clean = query.strip()
    if q_clean:
        candidates.append(q_clean)

    # Number with comma stripped
    no_comma = q_clean.replace(',', '')
    if no_comma != q_clean:
        candidates.append(no_comma)

    # Number with symbols/units stripped (%, ₹, $, per cent, mn, million)
    stripped = re.sub(r'(?i)(?:%|₹|\$|per\s*cent|percent|million|mn|cr|crore|crores|b|billion|lakh|lakhs)', '', q_clean).strip()
    if stripped and stripped not in candidates:
        candidates.append(stripped)

    # Extract all individual numbers/floats
    num_matches = re.findall(r'\b\d[\d,]*(?:\.\d+)?\b', q_clean)
    for n in num_matches:
        if n not in candidates:
            candidates.append(n)
        n_plain = n.replace(',', '')
        if n_plain not in candidates:
            candidates.append(n_plain)

    return candidates


def find_best_page_and_rects(doc: fitz.Document, initial_page: int, query: Optional[str]) -> Tuple[int, List[fitz.Rect]]:
    """Resolve the true physical PDF page and precise bounding box coordinates for a metric query."""
    if not query or not query.strip():
        return max(0, min(initial_page, len(doc) - 1)), []

    candidates = get_search_candidates(query)

    # 1. Check specified initial page FIRST with all candidates
    if 0 <= initial_page < len(doc):
        p = doc[initial_page]
        for c in candidates:
            if len(c) >= 2:
                rects = p.search_for(c)
                if rects:
                    return initial_page, rects

    # 2. Scan entire document for candidates (exact candidate match first, then numbers)
    for c in candidates:
        if len(c) >= 2:
            for idx, p in enumerate(doc):
                rects = p.search_for(c)
                if rects:
                    return idx, rects

    # Fallback to initial page
    return max(0, min(initial_page, len(doc) - 1)), []


def render_annotated_page_image(
    filename: str,
    page_num: int,
    highlight_text: Optional[str] = None,
    color_type: str = "contradiction",
    dpi: int = 150,
) -> Optional[bytes]:
    """Render a PDF page to PNG with high-visibility highlighted bounding boxes."""
    pdf_path = find_pdf_path(filename)
    if not pdf_path or not pdf_path.exists():
        return None

    try:
        doc = fitz.open(str(pdf_path))
        target_page_idx = max(0, min(page_num - 1, len(doc) - 1))

        # Resolve exact physical page and bounding box coordinates
        resolved_page_idx, rects_to_highlight = find_best_page_and_rects(doc, target_page_idx, highlight_text)
        page = doc[resolved_page_idx]

        # Colors for high-visibility annotations
        color_palette = {
            "contradiction": {
                "stroke": (0.93, 0.15, 0.15),  # Crimson Red
                "fill": (1.0, 0.78, 0.78),
            },
            "corroboration": {
                "stroke": (0.05, 0.70, 0.32),  # Vivid Emerald Green
                "fill": (0.75, 1.0, 0.82),
            },
            "reconciliation": {
                "stroke": (0.60, 0.15, 0.88),  # Royal Purple
                "fill": (0.92, 0.82, 1.0),
            },
            "default": {
                "stroke": (0.15, 0.40, 0.95),  # Royal Blue
                "fill": (0.80, 0.90, 1.0),
            }
        }
        colors = color_palette.get(color_type.lower(), color_palette["default"])

        # Draw high-visibility highlight annotations onto page
        for r in rects_to_highlight[:5]:
            # Generous bounding box halo padding so the highlight is unmistakable
            pad_rect = fitz.Rect(r.x0 - 8, r.y0 - 5, r.x1 + 8, r.y1 + 5)
            annot = page.add_rect_annot(pad_rect)
            annot.set_colors(stroke=colors["stroke"], fill=colors["fill"])
            annot.set_border(width=4.0)
            annot.set_opacity(0.92)
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
