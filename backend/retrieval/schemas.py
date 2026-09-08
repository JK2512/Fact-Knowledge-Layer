"""
Schemas and data structures for the Knowledge Retrieval Layer.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class QueryInterpretation:
    """Interpreted components of a natural language question."""
    raw_query: str
    subjects: List[str] = field(default_factory=list)
    metrics: List[str] = field(default_factory=list)
    periods: List[str] = field(default_factory=list)
    fact_types: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    intent: str = "lookup"  # lookup, compare, explain, reconcile, contradiction_check


@dataclass
class RetrievedFact:
    """A structured fact retrieved with relevance score and source context."""
    id: str
    document_id: str
    document_filename: str
    document_title: str
    fact_type: str
    subject: str
    predicate: str
    value: str
    numeric_value: Optional[float]
    unit: str
    time_period: str
    confidence: float
    source_page: int
    source_text: str
    context: str
    normalized_subject: str
    normalized_predicate: str
    normalized_period: str
    normalized_value: Optional[float]
    retrieval_score: float = 0.0
    retrieval_source: str = "structured"  # structured, lexical, hybrid

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "document_id": self.document_id,
            "document_filename": self.document_filename,
            "document_title": self.document_title,
            "fact_type": self.fact_type,
            "subject": self.subject,
            "predicate": self.predicate,
            "value": self.value,
            "numeric_value": self.numeric_value,
            "unit": self.unit,
            "time_period": self.time_period,
            "confidence": self.confidence,
            "source_page": self.source_page,
            "source_text": self.source_text,
            "context": self.context,
            "normalized_subject": self.normalized_subject,
            "normalized_predicate": self.normalized_predicate,
            "normalized_period": self.normalized_period,
            "normalized_value": self.normalized_value,
            "retrieval_score": self.retrieval_score,
            "retrieval_source": self.retrieval_source,
        }


@dataclass
class RetrievedEvidence:
    """A verbatim piece of evidence tied to a document and page."""
    fact_id: str
    document_id: str
    document_filename: str
    page_number: int
    verbatim_text: str
    subject: str
    predicate: str
    value_stated: str
    time_period: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fact_id": self.fact_id,
            "document_id": self.document_id,
            "document_filename": self.document_filename,
            "page_number": self.page_number,
            "verbatim_text": self.verbatim_text,
            "subject": self.subject,
            "predicate": self.predicate,
            "value_stated": self.value_stated,
            "time_period": self.time_period,
        }


@dataclass
class RetrievalResult:
    """Merged and ranked output of the retrieval stage."""
    query: str
    interpretation: QueryInterpretation
    facts: List[RetrievedFact] = field(default_factory=list)
    relationships: List[Dict[str, Any]] = field(default_factory=list)
    evidence: List[RetrievedEvidence] = field(default_factory=list)
    sources: List[Dict[str, Any]] = field(default_factory=list)
    is_empty: bool = False
