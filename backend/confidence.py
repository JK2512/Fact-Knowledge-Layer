"""
Evidence Confidence Scoring Module.
Calculates deterministic, interpretable weighted Evidence Confidence Scores
and factor breakdowns for extracted facts.

Weights:
- Evidence Quality:           25% (0.25)
- Metric/Value Completeness:  20% (0.20)
- Unit/Scale Confidence:      15% (0.15)
- Context Completeness:       15% (0.15)
- Subject Confidence:         10% (0.10)
- Source/Layout Quality:      10% (0.10)
- Cross-document Support:      5% (0.05)
Total:                       100% (1.00)
"""

import re
from typing import Dict, Any, Optional, Tuple

FACTOR_WEIGHTS = {
    "evidence_quality": 0.25,
    "metric_completeness": 0.20,
    "unit_confidence": 0.15,
    "context_completeness": 0.15,
    "subject_confidence": 0.10,
    "source_quality": 0.10,
    "corroboration_support": 0.05,
}


def calculate_evidence_confidence(
    subject: str = "",
    predicate: str = "",
    numeric_value: Optional[float] = None,
    unit: str = "",
    source_text: str = "",
    context: str = "",
    time_period: str = "",
    source_page: int = 0,
    has_corroboration: bool = False,
    is_ambiguous: bool = False,
) -> Tuple[float, Dict[str, float]]:
    """
    Computes deterministic weighted evidence confidence score and factor breakdown.
    
    Returns:
        (score: float in [0.0, 1.0], factors: Dict[str, float])
    """
    # 1. Evidence Quality (25%)
    # Evaluates presence, length, and quote clarity of verbatim source text
    st = (source_text or "").strip()
    if is_ambiguous:
        ev_q = 0.20
    elif not st:
        ev_q = 0.30
    elif len(st) >= 50:
        ev_q = 1.00
    elif len(st) >= 20:
        ev_q = 0.85
    else:
        ev_q = 0.60

    # 2. Metric/Value Completeness (20%)
    # Evaluates presence of parsed numeric value and valid predicate label
    pred = (predicate or "").strip().lower()
    if numeric_value is not None and len(pred) > 3:
        if "unidentified" in pred or pred == "value" or is_ambiguous:
            metric_comp = 0.30
        elif any(kw in pred for kw in [
            "volume", "growth", "revenue", "gdp", "deficit", "expenditure",
            "inflation", "sales", "ebitda", "profit", "shipment", "rate",
            "receipts", "borrowing", "gfd", "tax", "income", "asset"
        ]):
            metric_comp = 1.00
        else:
            metric_comp = 0.85
    elif numeric_value is not None:
        metric_comp = 0.50
    else:
        metric_comp = 0.20

    # 3. Unit/Scale Confidence (15%)
    # Evaluates presence of explicit financial/volume units vs missing/ambiguous
    u = (unit or "").strip().lower()
    if is_ambiguous or not u:
        unit_conf = 0.10
    elif any(std_u in u for std_u in [
        "crore", "cr", "million", "mn", "billion", "bn", "lakh",
        "parcels", "units", "usd", "inr", "tonnes", "kg"
    ]):
        unit_conf = 1.00
    elif "%" in u or "percent" in u or "bps" in u:
        unit_conf = 0.95
    elif u in ["₹", "$", "€", "£"]:
        unit_conf = 0.50  # Currency present but scale is missing
    else:
        unit_conf = 0.75

    # 4. Context Completeness (15%)
    # Evaluates time period and section/table context
    has_period = bool(time_period and len(time_period.strip()) >= 3 and time_period.strip().lower() != "unknown")
    has_ctx = bool(context and len(context.strip()) >= 3)
    if is_ambiguous:
        ctx_comp = 0.15
    elif has_period and has_ctx:
        ctx_comp = 1.00
    elif has_period:
        ctx_comp = 0.85
    elif has_ctx:
        ctx_comp = 0.65
    else:
        ctx_comp = 0.25

    # 5. Subject Confidence (10%)
    # Evaluates named entity identification
    subj = (subject or "").strip()
    if is_ambiguous or not subj or subj.lower() in ["unknown", "document"]:
        subj_conf = 0.20
    elif len(subj) >= 4 and any(ent in subj.lower() for ent in [
        "delhivery", "india", "rbi", "imf", "government", "ministry", "central", "survey", "company"
    ]):
        subj_conf = 1.00
    elif len(subj) >= 3:
        subj_conf = 0.80
    else:
        subj_conf = 0.40

    # 6. Source Quality (10%)
    # Evaluates page citation and document grounding
    if is_ambiguous:
        src_qual = 0.50
    elif source_page > 0:
        src_qual = 1.00
    else:
        src_qual = 0.60

    # 7. Cross-Document Support (5%)
    # Evaluates corroboration across multiple distinct documents
    corrob_sup = 1.00 if has_corroboration else 0.00

    factors = {
        "evidence_quality": round(ev_q, 2),
        "metric_completeness": round(metric_comp, 2),
        "unit_confidence": round(unit_conf, 2),
        "context_completeness": round(ctx_comp, 2),
        "subject_confidence": round(subj_conf, 2),
        "source_quality": round(src_qual, 2),
        "corroboration_support": round(corrob_sup, 2),
    }

    weighted_score = (
        FACTOR_WEIGHTS["evidence_quality"] * factors["evidence_quality"] +
        FACTOR_WEIGHTS["metric_completeness"] * factors["metric_completeness"] +
        FACTOR_WEIGHTS["unit_confidence"] * factors["unit_confidence"] +
        FACTOR_WEIGHTS["context_completeness"] * factors["context_completeness"] +
        FACTOR_WEIGHTS["subject_confidence"] * factors["subject_confidence"] +
        FACTOR_WEIGHTS["source_quality"] * factors["source_quality"] +
        FACTOR_WEIGHTS["corroboration_support"] * factors["corroboration_support"]
    )

    final_score = round(max(0.0, min(1.0, weighted_score)), 2)
    return final_score, factors


def compute_fact_confidence_factors(fact_dict: Dict[str, Any], has_corroboration: bool = False) -> Dict[str, Any]:
    """Helper to compute confidence factors for a fact dictionary."""
    is_ambiguous = (
        fact_dict.get("subject", "").lower() in ["unknown", "document", ""] and
        not fact_dict.get("unit")
    )
    score, factors = calculate_evidence_confidence(
        subject=fact_dict.get("subject", ""),
        predicate=fact_dict.get("predicate", ""),
        numeric_value=fact_dict.get("numeric_value"),
        unit=fact_dict.get("unit", ""),
        source_text=fact_dict.get("source_text", ""),
        context=fact_dict.get("context", ""),
        time_period=fact_dict.get("time_period", ""),
        source_page=fact_dict.get("source_page", 0),
        has_corroboration=has_corroboration,
        is_ambiguous=is_ambiguous,
    )
    return {
        "confidence": score,
        "confidence_factors": factors,
    }
