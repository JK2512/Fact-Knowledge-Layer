"""
Structured SQL-based Knowledge Retriever.
Queries SQLite facts using subject, predicate, period, and unit filters.
"""

import re
import json
from typing import List, Dict, Any, Optional
from backend.database import get_db, get_all_documents
from backend.fact_extractor import normalize_subject, normalize_predicate, normalize_period
from backend.retrieval.schemas import QueryInterpretation, RetrievedFact


class StructuredRetriever:
    """Interprets natural language queries into structured parameters and queries SQLite."""

    def __init__(self):
        self._load_doc_cache()

    def _load_doc_cache(self):
        try:
            docs = get_all_documents()
            self.doc_map = {d["id"]: d for d in docs}
        except Exception:
            self.doc_map = {}

    def interpret_query(self, query: str) -> QueryInterpretation:
        """Extract subjects, metrics, periods, and intent from a natural language query."""
        q_lower = query.lower()

        subjects = []
        if any(w in q_lower for w in ["delhivery", "company", "express parcel", "shipment"]):
            subjects.append("delhivery")
        if any(w in q_lower for w in ["india", "indian", "macro", "economy", "national"]):
            subjects.append("india")
        if any(w in q_lower for w in ["rbi", "reserve bank"]):
            subjects.append("rbi")
        if any(w in q_lower for w in ["imf", "fund"]):
            subjects.append("imf")

        metrics = []
        METRIC_KEYWORDS = {
            "gdp": ["gdp", "growth", "real gdp", "gdp growth"],
            "revenue": ["revenue", "turnover", "income", "sales"],
            "shipments": ["shipment", "express parcel", "parcel", "volume", "packages", "parcels"],
            "fiscal_deficit": ["fiscal deficit", "deficit", "fiscal"],
            "cpi_inflation": ["cpi", "inflation", "headline inflation", "consumer price"],
            "wpi_inflation": ["wpi", "wholesale price"],
            "ebitda": ["ebitda", "operating profit"],
            "pat": ["pat", "profit", "net profit", "loss"],
            "cad": ["cad", "current account deficit", "current account balance"],
            "forex_reserves": ["forex", "foreign exchange", "reserves"],
            "exports": ["export", "merchandise export"],
            "imports": ["import", "merchandise import"],
            "employee_count": ["employee", "headcount", "team size"],
        }
        for norm_m, kws in METRIC_KEYWORDS.items():
            if any(kw in q_lower for kw in kws):
                metrics.append(norm_m)

        # Time periods
        periods = []
        fy_matches = re.findall(r'(?:fy|FY)\s*\'?(\d{2,4})', query)
        for fy in fy_matches:
            full_fy = "FY20" + fy if len(fy) == 2 else "FY" + fy
            periods.append(full_fy)
            periods.append("FY" + fy[-2:])  # Also search short form

        yr_matches = re.findall(r'\b(20\d{2})\b', query)
        for yr in yr_matches:
            periods.append(yr)

        q_matches = re.findall(r'(Q[1-4])\s*(?:FY|fy)?\s*\'?(\d{2,4})?', query)
        for q_m in q_matches:
            periods.append(q_m[0].upper())

        # Intent
        intent = "lookup"
        if any(w in q_lower for w in ["agree", "disagree", "differ", "conflict", "contradict", "dispute"]):
            intent = "contradiction_check"
        elif any(w in q_lower for w in ["compare", "versus", "vs", "across"]):
            intent = "compare"
        elif any(w in q_lower for w in ["why", "explain", "reason", "reconcile"]):
            intent = "reconcile"

        STOP_WORDS = {
            "what", "was", "were", "the", "and", "for", "from", "sources", "available", "documents",
            "show", "tell", "does", "did", "how", "much", "many", "give", "find", "with", "which",
            "across", "differ", "why", "value", "safely", "interpreted", "can", "figures", "report",
            "reports", "document", "information", "do", "corroborate", "agree", "disagree"
        }
        keywords = [w for w in re.findall(r'[a-zA-Z0-9_\.]+', q_lower) if len(w) > 2 and w not in STOP_WORDS]

        return QueryInterpretation(
            raw_query=query,
            subjects=subjects,
            metrics=metrics,
            periods=periods,
            keywords=keywords,
            intent=intent,
        )

    def retrieve(self, interp: QueryInterpretation, limit: int = 50) -> List[RetrievedFact]:
        """Execute structured SQL queries based on the query interpretation."""
        self._load_doc_cache()
        params = []
        or_clauses = []

        if interp.subjects:
            for s in interp.subjects:
                or_clauses.append("normalized_subject LIKE ? OR subject LIKE ?")
                params.extend([f"%{s}%", f"%{s}%"])

        if interp.metrics:
            for m in interp.metrics:
                or_clauses.append("normalized_predicate LIKE ? OR predicate LIKE ?")
                params.extend([f"%{m}%", f"%{m}%"])

        if interp.periods:
            for p in interp.periods:
                or_clauses.append("normalized_period LIKE ? OR time_period LIKE ?")
                params.extend([f"%{p}%", f"%{p}%"])

        if interp.keywords:
            for kw in interp.keywords[:4]:
                or_clauses.append("predicate LIKE ? OR source_text LIKE ? OR subject LIKE ? OR value LIKE ?")
                params.extend([f"%{kw}%", f"%{kw}%", f"%{kw}%", f"%{kw}%"])

        where_clause = f"({' OR '.join(or_clauses)})" if or_clauses else "1=1"

        query_sql = f"""
            SELECT * FROM facts
            WHERE {where_clause}
            ORDER BY confidence DESC
            LIMIT ?
        """
        params.append(limit * 3)

        results = []
        with get_db() as conn:
            rows = conn.execute(query_sql, params).fetchall()
            for r in rows:
                doc = self.doc_map.get(r["document_id"], {})
                # Base scoring
                score = r["confidence"]
                doc_fn = doc.get("filename", "").lower()
                if "india" in interp.subjects:
                    if any(m in doc_fn for m in ["economic-survey", "rbi", "imf", "india"]):
                        score += 0.5
                    elif "delhivery" in doc_fn and "delhivery" not in interp.subjects:
                        score -= 0.5
                if "delhivery" in interp.subjects:
                    if "delhivery" in doc_fn:
                        score += 0.5
                    elif any(m in doc_fn for m in ["economic-survey", "rbi", "imf"]):
                        score -= 0.5

                if interp.subjects and any(s in (r["normalized_subject"] or "").lower() for s in interp.subjects):
                    score += 0.2
                if interp.metrics and any(m in (r["normalized_predicate"] or "").lower() for m in interp.metrics):
                    score += 0.3
                if interp.periods and any(p in (r["normalized_period"] or "").lower() for p in interp.periods):
                    score += 0.2
                if interp.keywords:
                    full_text = f"{r['subject']} {r['predicate']} {r['value']} {r['source_text']}".lower()
                    for kw in interp.keywords:
                        if kw.lower() in full_text:
                            score += 0.25

                results.append(RetrievedFact(
                    id=r["id"],
                    document_id=r["document_id"],
                    document_filename=doc.get("filename", "Unknown"),
                    document_title=doc.get("title", doc.get("filename", "Unknown")),
                    fact_type=r["fact_type"],
                    subject=r["subject"],
                    predicate=r["predicate"],
                    value=r["value"],
                    numeric_value=r["numeric_value"],
                    unit=r["unit"],
                    time_period=r["time_period"],
                    confidence=r["confidence"],
                    source_page=r["source_page"],
                    source_text=r["source_text"],
                    context=r["context"],
                    normalized_subject=r["normalized_subject"],
                    normalized_predicate=r["normalized_predicate"],
                    normalized_period=r["normalized_period"],
                    normalized_value=r["normalized_value"],
                    retrieval_score=score,
                    retrieval_source="structured",
                ))

        results.sort(key=lambda x: x.retrieval_score, reverse=True)
        return results
