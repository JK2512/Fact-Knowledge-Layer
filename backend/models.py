"""
Data models for the Fact Knowledge Layer.
Uses dataclasses for clean, typed data structures.
"""

import uuid
import json
from dataclasses import dataclass, field, asdict
from typing import List, Optional
from datetime import datetime


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class Document:
    """A processed PDF document."""
    id: str = field(default_factory=_new_id)
    filename: str = ""
    title: str = ""
    upload_date: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    page_count: int = 0
    extraction_mode: str = "rule_based"
    fact_count: int = 0
    metadata: str = "{}"  # JSON string for flexible metadata

    def to_dict(self):
        d = asdict(self)
        d["metadata"] = json.loads(d["metadata"]) if isinstance(d["metadata"], str) else d["metadata"]
        return d


@dataclass
class Fact:
    """A single extracted fact linked to its source document."""
    id: str = field(default_factory=_new_id)
    document_id: str = ""
    fact_type: str = ""        # numerical, percentage, entity, temporal, categorical
    subject: str = ""          # what the fact is about (e.g. "Delhivery", "India GDP")
    predicate: str = ""        # the attribute (e.g. "revenue", "growth_rate")
    value: str = ""            # the raw value as extracted
    numeric_value: Optional[float] = None  # parsed numeric value for comparison
    unit: str = ""             # ₹ crore, %, USD million, etc.
    time_period: str = ""      # FY2024, Q4 FY24, CY2024, etc.
    confidence: float = 0.5
    source_page: int = 0
    source_text: str = ""      # the exact quote from the document
    context: str = ""          # broader context / section name
    normalized_subject: str = ""   # canonicalized subject for matching
    normalized_predicate: str = "" # canonicalized predicate for matching
    normalized_period: str = ""    # canonicalized period for matching
    normalized_value: Optional[float] = None  # value converted to common unit
    confidence_factors: Optional[dict] = None

    def to_dict(self):
        d = asdict(self)
        if not d.get("confidence_factors"):
            from backend.confidence import calculate_evidence_confidence
            _, factors = calculate_evidence_confidence(
                subject=self.subject,
                predicate=self.predicate,
                numeric_value=self.numeric_value,
                unit=self.unit,
                source_text=self.source_text,
                context=self.context,
                time_period=self.time_period,
                source_page=self.source_page,
            )
            d["confidence_factors"] = factors
        return d


@dataclass
class Relationship:
    """A cross-document relationship between two or more facts."""
    id: str = field(default_factory=_new_id)
    relationship_type: str = ""  # corroboration, contradiction, reconciliation
    fact_ids: str = "[]"         # JSON array of fact IDs
    reasoning: str = ""          # explanation of why this relationship exists
    confidence: float = 0.5
    category: str = ""           # grouping label (e.g. "revenue", "GDP growth")
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self):
        d = asdict(self)
        d["fact_ids"] = json.loads(d["fact_ids"]) if isinstance(d["fact_ids"], str) else d["fact_ids"]
        return d


@dataclass
class ExtractionFailure:
    """Documented extraction or reasoning failure."""
    id: str = field(default_factory=_new_id)
    document_id: str = ""
    failure_type: str = ""     # parse_error, ambiguous, missing_context, wrong_extraction
    description: str = ""
    source_page: int = 0
    source_text: str = ""
    attempted_fact: str = "{}" # JSON of what was attempted
    improvement: str = ""      # how it could be fixed
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self):
        d = asdict(self)
        d["attempted_fact"] = json.loads(d["attempted_fact"]) if isinstance(d["attempted_fact"], str) else d["attempted_fact"]
        return d
