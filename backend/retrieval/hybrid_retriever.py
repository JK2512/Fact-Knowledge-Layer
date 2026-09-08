"""
Hybrid Retriever combining Structured SQL Queries and Lexical/Semantic Fact-Evidence Search.
Merges, deduplicates, ranks results, and fetches connected cross-document relationships.
"""

import json
from typing import List, Dict, Any, Optional
from backend.database import get_db, get_all_relationships, get_all_documents, get_facts_by_ids
from backend.retrieval.schemas import (
    QueryInterpretation,
    RetrievedFact,
    RetrievedEvidence,
    RetrievalResult,
)
from backend.retrieval.structured_retriever import StructuredRetriever
from backend.retrieval.semantic_retriever import SemanticRetriever


class HybridRetriever:
    """Combines structured parameters and lexical search for robust, grounded knowledge retrieval."""

    def __init__(self):
        self.structured = StructuredRetriever()
        self.semantic = SemanticRetriever()

    def retrieve(self, query: str, top_k: int = 15) -> RetrievalResult:
        """Execute hybrid retrieval pipeline:
        1. Interpret question (subject, metric, period, intent)
        2. Structured SQL retrieval
        3. Lexical/semantic retrieval
        4. Merge, deduplicate, and rank
        5. Attach connected cross-document relationships and verbatim evidence
        """
        # 1. Query interpretation
        interp = self.structured.interpret_query(query)

        # 2. Structured retrieval
        struct_facts = self.structured.retrieve(interp, limit=top_k * 2)

        # 3. Lexical/semantic retrieval
        sem_facts = self.semantic.search(query, top_k=top_k * 2)

        # 4. Merge and deduplicate
        merged_map: Dict[str, RetrievedFact] = {}

        # Prioritize exact structured matches
        for f in struct_facts:
            merged_map[f.id] = f

        # Supplement with semantic facts
        for f in sem_facts:
            if f.id in merged_map:
                # Boost existing fact
                merged_map[f.id].retrieval_score += f.retrieval_score * 0.3
                merged_map[f.id].retrieval_source = "hybrid"
            else:
                merged_map[f.id] = f

        sorted_facts = sorted(
            merged_map.values(),
            key=lambda x: (x.retrieval_score, x.confidence),
            reverse=True
        )[:top_k]

        if not sorted_facts:
            return RetrievalResult(
                query=query,
                interpretation=interp,
                facts=[],
                relationships=[],
                evidence=[],
                sources=[],
                is_empty=True,
            )

        # 5. Extract retrieved fact IDs and find connected relationships
        retrieved_fact_ids = {f.id for f in sorted_facts}
        all_rels = get_all_relationships()

        matched_relationships = []
        doc_cache = {d["id"]: d for d in get_all_documents()}

        for rel in all_rels:
            rel_fact_ids = set(rel.get("fact_ids", []))
            # If any retrieved fact is part of this relationship, or if relationship connects facts in the topic
            if rel_fact_ids & retrieved_fact_ids:
                # Fetch full fact objects for this relationship
                rel_facts_raw = get_facts_by_ids(list(rel_fact_ids))
                for rf in rel_facts_raw:
                    doc = doc_cache.get(rf["document_id"], {})
                    rf["document_filename"] = doc.get("filename", "Unknown")

                rel_copy = dict(rel)
                rel_copy["facts"] = rel_facts_raw
                matched_relationships.append(rel_copy)

        # 6. Extract verbatim evidence snippets
        evidence_list = []
        seen_evidence = set()
        for f in sorted_facts:
            ev_key = (f.document_id, f.source_page, f.value)
            if ev_key not in seen_evidence and f.source_text:
                seen_evidence.add(ev_key)
                evidence_list.append(RetrievedEvidence(
                    fact_id=f.id,
                    document_id=f.document_id,
                    document_filename=f.document_filename,
                    page_number=f.source_page,
                    verbatim_text=f.source_text,
                    subject=f.subject,
                    predicate=f.predicate,
                    value_stated=f.value,
                    time_period=f.time_period,
                ))

        # 7. Collect unique source documents
        source_doc_ids = {f.document_id for f in sorted_facts}
        sources = [
            doc_cache[did] for did in source_doc_ids if did in doc_cache
        ]

        return RetrievalResult(
            query=query,
            interpretation=interp,
            facts=sorted_facts,
            relationships=matched_relationships,
            evidence=evidence_list,
            sources=sources,
            is_empty=False,
        )
