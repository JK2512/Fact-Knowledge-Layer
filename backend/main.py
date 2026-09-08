"""
FastAPI application — Fact Knowledge Layer API and static file server.
"""

import os
import json
import shutil
import logging
from pathlib import Path
from typing import Optional
from pydantic import BaseModel
from fastapi import FastAPI, UploadFile, File, HTTPException, Query, Response
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from backend.config import UPLOAD_DIR, get_extraction_mode
from backend.database import (
    init_db, insert_document, get_all_documents, get_document,
    delete_document, insert_facts, get_all_facts, get_fact_by_id,
    get_facts_by_document, get_facts_by_ids, update_document_fact_count,
    insert_relationships, get_all_relationships, get_relationship_by_id,
    clear_relationships, insert_failure, get_all_failures, get_stats,
)
from backend.models import Document, ExtractionFailure
from backend.pdf_parser import PDFParser
from backend.fact_extractor import FactExtractor
from backend.fact_linker import FactLinker
from backend.rag.rag_engine import RAGEngine
from backend.graph import EvidenceGraph
from backend.reconciliation import build_reconciliation_matrix
from backend.dossier_generator import generate_audit_dossier
from backend.benchmarks.evaluator import FactBenchmarkEvaluator
from backend.visual_diff import render_annotated_page_image, get_visual_comparison_pair

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

class QueryRequest(BaseModel):
    question: Optional[str] = None
    query: Optional[str] = None

# ── App setup ──────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Fact Knowledge Layer",
    description="Extract, link, and compare facts across PDF documents",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
@app.on_event("startup")
def startup():
    init_db()
    logger.info("Database initialized. Extraction mode: %s", get_extraction_mode())

# ── Static files ───────────────────────────────────────────────────────────────
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

@app.get("/", response_class=HTMLResponse)
def serve_ui():
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return index_path.read_text(encoding="utf-8")
    return "<h1>Fact Knowledge Layer</h1><p>Frontend not found.</p>"

@app.get("/favicon.ico")
@app.get("/favicon.svg")
def serve_favicon():
    fav_path = FRONTEND_DIR / "favicon.svg"
    if fav_path.exists():
        return FileResponse(fav_path, media_type="image/svg+xml")
    return HTMLResponse("", status_code=204)


# ── Upload & Process ───────────────────────────────────────────────────────────

@app.post("/api/upload")
def upload_pdf(file: UploadFile = File(...)):
    """Upload a PDF, extract facts, and run cross-document analysis."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are accepted")

    # Save uploaded file
    dest = UPLOAD_DIR / file.filename
    try:
        with open(str(dest), "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        raise HTTPException(500, "Failed to save file: {}".format(str(e)))

    # Process the PDF
    try:
        result = _process_pdf(str(dest), file.filename)
    except Exception as e:
        logger.exception("Failed to process PDF")
        raise HTTPException(500, "Processing failed: {}".format(str(e)))

    return JSONResponse(result)


def _process_pdf(filepath: str, filename: str) -> dict:
    """Full pipeline: parse → extract → link → store."""

    # 1. Parse PDF
    with PDFParser(filepath) as parser:
        pages = parser.extract_all_text()
        tables = parser.extract_all_tables()
        title = parser.get_title()
        meta = parser.get_metadata()
        page_count = parser.page_count

    # 2. Create document record
    mode = get_extraction_mode()
    doc = Document(
        filename=filename,
        title=title,
        page_count=page_count,
        extraction_mode=mode,
        metadata=json.dumps(meta),
    )
    insert_document(doc)

    # 3. Extract facts
    extractor = FactExtractor()
    facts, failures = extractor.extract(pages, tables, doc.id, title)

    # 4. Store facts and failures
    insert_facts(facts)
    update_document_fact_count(doc.id, len(facts))
    for failure in failures:
        insert_failure(failure)

    # 5. Run incremental cross-document analysis
    all_docs = get_all_documents()
    if len(all_docs) > 1:
        existing_facts = [f for f in get_all_facts() if f["document_id"] != doc.id]
        linker = FactLinker()
        if existing_facts:
            new_raw_facts = [f.to_dict() for f in facts]
            new_rels = linker.analyze_incremental(new_raw_facts, existing_facts, all_docs)
            insert_relationships(new_rels)
        else:
            all_facts = get_all_facts()
            clear_relationships()
            relationships = linker.analyze(all_facts, all_docs)
            insert_relationships(relationships)
        rel_count = len(get_all_relationships())
    else:
        rel_count = 0

    return {
        "document": doc.to_dict(),
        "facts_extracted": len(facts),
        "failures": len(failures),
        "relationships_detected": rel_count,
        "extraction_mode": mode,
    }


# ── Documents ──────────────────────────────────────────────────────────────────

@app.get("/api/documents")
def list_documents():
    docs = get_all_documents()
    for d in docs:
        d["metadata"] = json.loads(d.get("metadata", "{}"))
    return docs


@app.get("/api/documents/{doc_id}")
def get_doc(doc_id: str):
    doc = get_document(doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    doc["metadata"] = json.loads(doc.get("metadata", "{}"))
    return doc


@app.delete("/api/documents/{doc_id}")
def remove_document(doc_id: str):
    doc = get_document(doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    delete_document(doc_id)

    # Re-run analysis
    all_facts = get_all_facts()
    all_docs = get_all_documents()
    clear_relationships()
    if len(all_docs) > 1:
        linker = FactLinker()
        relationships = linker.analyze(all_facts, all_docs)
        insert_relationships(relationships)

    return {"status": "deleted", "id": doc_id}


# ── Facts ──────────────────────────────────────────────────────────────────────

@app.get("/api/facts")
def list_facts(
    fact_type: Optional[str] = Query(None),
    min_confidence: Optional[float] = Query(None),
    subject: Optional[str] = Query(None),
    document_id: Optional[str] = Query(None),
):
    if document_id:
        return get_facts_by_document(document_id)
    return get_all_facts(fact_type=fact_type, min_confidence=min_confidence, subject=subject)


@app.get("/api/facts/{fact_id}")
def get_single_fact(fact_id: str):
    fact = get_fact_by_id(fact_id)
    if not fact:
        raise HTTPException(404, "Fact not found")
    return fact


# ── Relationships ──────────────────────────────────────────────────────────────

@app.get("/api/relationships")
def list_relationships(
    relationship_type: Optional[str] = Query(None),
    limit: Optional[int] = Query(None),
):
    rels = get_all_relationships()
    if relationship_type:
        rels = [r for r in rels if r.get("relationship_type") == relationship_type]
    if limit:
        rels = rels[:limit]

    # Batch lookup to prevent N+1 queries
    all_facts = get_all_facts()
    fact_map = {f["id"]: f for f in all_facts}
    doc_map = {d["id"]: d for d in get_all_documents()}

    for rel in rels:
        fact_ids = rel.get("fact_ids", [])
        rel_facts = []
        for fid in fact_ids:
            if fid in fact_map:
                f_copy = dict(fact_map[fid])
                doc = doc_map.get(f_copy.get("document_id"), {})
                f_copy["document_filename"] = doc.get("filename", "Unknown")
                rel_facts.append(f_copy)
        rel["facts"] = rel_facts
    return rels


@app.get("/api/relationships/{rel_id}")
def get_single_relationship(rel_id: str):
    rel = get_relationship_by_id(rel_id)
    if not rel:
        raise HTTPException(404, "Relationship not found")
    fact_ids = rel.get("fact_ids", [])
    rel["facts"] = get_facts_by_ids(fact_ids)
    for fact in rel["facts"]:
        doc = get_document(fact["document_id"])
        fact["document_filename"] = doc["filename"] if doc else "Unknown"
    return rel


# ── Re-Analysis ───────────────────────────────────────────────────────────────

@app.post("/api/analyze")
def reanalyze():
    """Re-run cross-document analysis on all existing facts."""
    all_facts = get_all_facts()
    all_docs = get_all_documents()

    clear_relationships()
    if len(all_docs) > 1:
        linker = FactLinker()
        relationships = linker.analyze(all_facts, all_docs)
        insert_relationships(relationships)
        return {"relationships_detected": len(relationships)}
    return {"relationships_detected": 0}


# ── Failures ───────────────────────────────────────────────────────────────────

@app.get("/api/failures")
def list_failures():
    return get_all_failures()


# ── Stats ──────────────────────────────────────────────────────────────────────

@app.get("/api/stats")
def stats():
    return get_stats()


# ── Knowledge RAG Query Layer ──────────────────────────────────────────────────

@app.post("/api/query")
def query_knowledge_base(req: QueryRequest):
    """Answer natural language questions using hybrid retrieval and contradiction-aware RAG."""
    q_str = req.question or req.query
    if not q_str or not q_str.strip():
        raise HTTPException(400, "Question cannot be empty")
    rag = RAGEngine()
    result = rag.query(q_str.strip())
    return JSONResponse(result)


# ── Evidence Relationship Graph ────────────────────────────────────────────────

@app.get("/api/graph")
def get_evidence_graph(
    relationship_type: Optional[str] = Query(None),
    document_id: Optional[str] = Query(None),
    limit: int = Query(150),
):
    """Retrieve full or filtered evidence relationship graph for visual exploration."""
    graph = EvidenceGraph()
    data = graph.build_full_graph(
        relationship_type=relationship_type,
        document_id=document_id,
        limit_nodes=limit,
    )
    return JSONResponse(data)


# ── Reconciliation Matrix ───────────────────────────────────────────────────────

@app.get("/api/reconciliation-matrix")
def get_reconciliation_matrix():
    """Retrieve cross-document comparative reconciliation matrix for corporate & macro metrics."""
    data = build_reconciliation_matrix()
    return JSONResponse(data)


# ── Quantitative Benchmarking ──────────────────────────────────────────────────

@app.get("/api/benchmark")
def get_system_benchmark():
    """Run quantitative benchmark evaluation and return faithfulness & precision scorecard."""
    evaluator = FactBenchmarkEvaluator()
    data = evaluator.run_evaluations()
    return JSONResponse(data)


# ── Compliance & Due Diligence Dossier ──────────────────────────────────────────

class DossierRequest(BaseModel):
    query: Optional[str] = None

@app.post("/api/export-dossier")
def export_audit_dossier(req: Optional[DossierRequest] = None):
    """Generate executive due-diligence audit dossier with cryptographic provenance."""
    q_str = req.query if req else None
    dossier = generate_audit_dossier(q_str)
    return JSONResponse(dossier)


# ── Visual Document Diff & Page Annotations ────────────────────────────────────

@app.get("/api/visual-diff/page")
def get_annotated_page_image(
    document: str = Query(...),
    page: int = Query(1),
    highlight: Optional[str] = Query(None),
    color: str = Query("contradiction"),
    dpi: int = Query(150),
):
    """Render high-resolution PDF page image with highlighted bounding boxes."""
    img_bytes = render_annotated_page_image(
        filename=document,
        page_num=page,
        highlight_text=highlight,
        color_type=color,
        dpi=dpi,
    )
    if not img_bytes:
        raise HTTPException(404, f"Could not render page {page} of {document}")
    return Response(content=img_bytes, media_type="image/png")


@app.get("/api/visual-diff/pair")
def get_relationship_visual_pair(relationship_id: str = Query(...)):
    """Retrieve side-by-side visual comparison payload for a cross-document relationship."""
    pair = get_visual_comparison_pair(relationship_id)
    if not pair:
        raise HTTPException(404, "Visual comparison pair not available for this relationship")
    return JSONResponse(pair)


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
