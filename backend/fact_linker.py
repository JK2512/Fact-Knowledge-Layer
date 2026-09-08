"""
Cross-document fact linking and relationship detection.
Identifies corroborations, contradictions, and contextual reconciliations.
"""

import re
import json
import logging
from typing import List, Dict, Any, Optional, Tuple, Set
from collections import defaultdict

from backend.models import Fact, Relationship, _new_id
from backend.config import (
    SUBJECT_SIMILARITY_THRESHOLD,
    PREDICATE_SIMILARITY_THRESHOLD,
    VALUE_TOLERANCE_PERCENT,
)
from backend.fact_extractor import normalize_period, normalize_subject, normalize_predicate

logger = logging.getLogger(__name__)


def _jaccard_similarity(a: str, b: str) -> float:
    """Jaccard similarity between two strings based on character n-grams."""
    if not a or not b:
        return 0.0
    a, b = a.lower(), b.lower()
    if a == b:
        return 1.0

    n = 3  # trigrams
    set_a = set(a[i:i+n] for i in range(max(1, len(a) - n + 1)))
    set_b = set(b[i:i+n] for i in range(max(1, len(b) - n + 1)))

    if not set_a or not set_b:
        return 1.0 if a == b else 0.0

    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def _token_overlap(a: str, b: str) -> float:
    """Token-level overlap ratio."""
    if not a or not b:
        return 0.0
    tokens_a = set(a.lower().split())
    tokens_b = set(b.lower().split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = len(tokens_a & tokens_b)
    shorter = min(len(tokens_a), len(tokens_b))
    return intersection / shorter if shorter > 0 else 0.0


def _values_match(v1: Optional[float], v2: Optional[float], tolerance_pct: float = VALUE_TOLERANCE_PERCENT) -> bool:
    """Check if two numeric values match within tolerance."""
    if v1 is None or v2 is None:
        return False
    if v1 == 0 and v2 == 0:
        return True
    if v1 == 0 or v2 == 0:
        return False
    pct_diff = abs(v1 - v2) / max(abs(v1), abs(v2)) * 100
    return pct_diff <= tolerance_pct


def _values_close(v1: Optional[float], v2: Optional[float], tolerance_pct: float = 20.0) -> bool:
    """Check if two numeric values are in the same ballpark (for reconciliation)."""
    if v1 is None or v2 is None:
        return False
    if v1 == 0 or v2 == 0:
        return False
    ratio = max(abs(v1), abs(v2)) / min(abs(v1), abs(v2))
    return ratio < 5.0  # within 5x of each other


def _format_value(fact: Dict[str, Any]) -> str:
    """Format a fact's value for display."""
    v = fact.get("value", "")
    u = fact.get("unit", "")
    if u and u not in v:
        return "{} {}".format(v, u)
    return v


class FactLinker:
    """Detect relationships between facts across documents."""

    def analyze(
        self,
        all_facts: List[Dict[str, Any]],
        documents: List[Dict[str, Any]],
    ) -> List[Relationship]:
        """Run cross-document analysis on all facts.

        Returns a list of detected Relationship objects.
        """
        relationships = []

        # Build document lookup
        doc_map = {d["id"]: d for d in documents}

        # Group facts by normalized predicate for efficient comparison
        pred_groups = defaultdict(list)
        for fact in all_facts:
            pred = fact.get("normalized_predicate", "")
            if pred:
                pred_groups[pred].append(fact)

        # Also group by broader subject
        subj_groups = defaultdict(list)
        for fact in all_facts:
            subj = fact.get("normalized_subject", "")
            if subj:
                subj_groups[subj].append(fact)

        # Track which fact pairs we've already compared
        compared = set()

        # ── Phase 1: Exact predicate matches across documents ──────────────
        for pred, facts in pred_groups.items():
            if len(facts) < 2:
                continue

            # Only compare facts from different documents
            for i in range(len(facts)):
                for j in range(i + 1, len(facts)):
                    f1 = facts[i]
                    f2 = facts[j]

                    if f1["document_id"] == f2["document_id"]:
                        continue

                    pair_key = tuple(sorted([f1["id"], f2["id"]]))
                    if pair_key in compared:
                        continue
                    compared.add(pair_key)

                    rel = self._compare_facts(f1, f2, doc_map)
                    if rel:
                        relationships.append(rel)

        # ── Phase 2: Fuzzy predicate matching ──────────────────────────────
        predicates = list(pred_groups.keys())
        for i in range(len(predicates)):
            for j in range(i + 1, len(predicates)):
                p1, p2 = predicates[i], predicates[j]
                sim = _jaccard_similarity(p1, p2)
                token_sim = _token_overlap(p1, p2)
                combined_sim = max(sim, token_sim)

                if combined_sim < PREDICATE_SIMILARITY_THRESHOLD:
                    continue

                # Compare facts across these similar predicates
                for f1 in pred_groups[p1]:
                    for f2 in pred_groups[p2]:
                        if f1["document_id"] == f2["document_id"]:
                            continue

                        pair_key = tuple(sorted([f1["id"], f2["id"]]))
                        if pair_key in compared:
                            continue
                        compared.add(pair_key)

                        # Check subject similarity too
                        subj_sim = _jaccard_similarity(
                            f1.get("normalized_subject", ""),
                            f2.get("normalized_subject", "")
                        )
                        if subj_sim < SUBJECT_SIMILARITY_THRESHOLD:
                            continue

                        rel = self._compare_facts(f1, f2, doc_map)
                        if rel:
                            relationships.append(rel)

        # Deduplicate relationships
        relationships = self._deduplicate_relationships(relationships)

        # Sort by confidence
        relationships.sort(key=lambda r: r.confidence, reverse=True)

        logger.info("Detected %d relationships across %d facts",
                     len(relationships), len(all_facts))
        return relationships

    def analyze_incremental(
        self,
        new_facts: List[Dict[str, Any]],
        existing_facts: List[Dict[str, Any]],
        documents: List[Dict[str, Any]],
    ) -> List[Relationship]:
        """Run incremental cross-document analysis comparing only new facts against existing facts."""
        if not new_facts or not existing_facts:
            return []

        relationships = []
        doc_map = {d["id"]: d for d in documents}

        # Index existing facts by normalized predicate
        exist_pred_groups = defaultdict(list)
        for fact in existing_facts:
            pred = fact.get("normalized_predicate", "")
            if pred:
                exist_pred_groups[pred].append(fact)

        compared = set()

        for f1 in new_facts:
            pred1 = f1.get("normalized_predicate", "")
            if not pred1:
                continue

            # Exact matches with existing
            matching_existing = exist_pred_groups.get(pred1, [])
            for f2 in matching_existing:
                if f1["document_id"] == f2["document_id"]:
                    continue
                pair_key = tuple(sorted([f1["id"], f2["id"]]))
                if pair_key in compared:
                    continue
                compared.add(pair_key)
                rel = self._compare_facts(f1, f2, doc_map)
                if rel:
                    relationships.append(rel)

            # Fuzzy matches with existing
            for pred2, facts2 in exist_pred_groups.items():
                if pred1 == pred2:
                    continue
                sim = _jaccard_similarity(pred1, pred2)
                token_sim = _token_overlap(pred1, pred2)
                if max(sim, token_sim) >= PREDICATE_SIMILARITY_THRESHOLD:
                    subj1 = f1.get("normalized_subject", "")
                    for f2 in facts2:
                        if f1["document_id"] == f2["document_id"]:
                            continue
                        if _jaccard_similarity(subj1, f2.get("normalized_subject", "")) < SUBJECT_SIMILARITY_THRESHOLD:
                            continue
                        pair_key = tuple(sorted([f1["id"], f2["id"]]))
                        if pair_key in compared:
                            continue
                        compared.add(pair_key)
                        rel = self._compare_facts(f1, f2, doc_map)
                        if rel:
                            relationships.append(rel)

        relationships = self._deduplicate_relationships(relationships)
        relationships.sort(key=lambda r: r.confidence, reverse=True)
        logger.info("Incremental analysis detected %d new relationships", len(relationships))
        return relationships

    def _compare_facts(
        self,
        f1: Dict[str, Any],
        f2: Dict[str, Any],
        doc_map: Dict[str, Dict[str, Any]],
    ) -> Optional[Relationship]:
        """Compare two facts and determine their relationship."""

        v1 = f1.get("normalized_value") or f1.get("numeric_value")
        v2 = f2.get("normalized_value") or f2.get("numeric_value")

        period1 = f1.get("normalized_period", "")
        period2 = f2.get("normalized_period", "")

        doc1_name = doc_map.get(f1["document_id"], {}).get("filename", "Doc1")
        doc2_name = doc_map.get(f2["document_id"], {}).get("filename", "Doc2")

        pred1 = f1.get("predicate", f1.get("normalized_predicate", ""))
        pred2 = f2.get("predicate", f2.get("normalized_predicate", ""))
        subj1 = f1.get("subject", "")
        subj2 = f2.get("subject", "")

        # Both must have comparable values
        if v1 is None and v2 is None:
            return None

        # ── Case 1: Values match (corroboration) ──────────────────────────
        if v1 is not None and v2 is not None and _values_match(v1, v2):
            # Same or overlapping period → strong corroboration
            periods_match = (
                period1 == period2
                or not period1
                or not period2
                or period1 in period2
                or period2 in period1
            )
            if periods_match:
                confidence = min(f1.get("confidence", 0.5), f2.get("confidence", 0.5))
                confidence = min(1.0, confidence + 0.15)

                reasoning = self._build_corroboration_reasoning(
                    f1, f2, doc1_name, doc2_name
                )
                return Relationship(
                    relationship_type="corroboration",
                    fact_ids=json.dumps([f1["id"], f2["id"]]),
                    reasoning=reasoning,
                    confidence=confidence,
                    category=f1.get("normalized_predicate", pred1),
                )

        # ── Case 2: Values differ ─────────────────────────────────────────
        if v1 is not None and v2 is not None and not _values_match(v1, v2):

            # Check if the difference can be explained by context
            reconciliation_reason = self._check_reconciliation(
                f1, f2, v1, v2, period1, period2, doc1_name, doc2_name
            )

            if reconciliation_reason:
                confidence = min(f1.get("confidence", 0.5), f2.get("confidence", 0.5))
                reasoning = self._build_reconciliation_reasoning(
                    f1, f2, v1, v2, doc1_name, doc2_name, reconciliation_reason
                )
                return Relationship(
                    relationship_type="reconciliation",
                    fact_ids=json.dumps([f1["id"], f2["id"]]),
                    reasoning=reasoning,
                    confidence=confidence,
                    category=f1.get("normalized_predicate", pred1),
                )

            # If periods match and values differ significantly → contradiction
            if period1 and period2 and period1 == period2:
                confidence = min(f1.get("confidence", 0.5), f2.get("confidence", 0.5))
                reasoning = self._build_contradiction_reasoning(
                    f1, f2, v1, v2, doc1_name, doc2_name
                )
                return Relationship(
                    relationship_type="contradiction",
                    fact_ids=json.dumps([f1["id"], f2["id"]]),
                    reasoning=reasoning,
                    confidence=confidence,
                    category=f1.get("normalized_predicate", pred1),
                )

            # Values differ and periods also differ → likely reconciliation
            if period1 and period2 and period1 != period2:
                if _values_close(v1, v2):
                    confidence = min(f1.get("confidence", 0.5), f2.get("confidence", 0.5))
                    reasoning = self._build_reconciliation_reasoning(
                        f1, f2, v1, v2, doc1_name, doc2_name,
                        "different time periods ({} vs {})".format(period1, period2)
                    )
                    return Relationship(
                        relationship_type="reconciliation",
                        fact_ids=json.dumps([f1["id"], f2["id"]]),
                        reasoning=reasoning,
                        confidence=confidence,
                        category=f1.get("normalized_predicate", pred1),
                    )

        return None

    def _check_reconciliation(
        self,
        f1: Dict[str, Any], f2: Dict[str, Any],
        v1: float, v2: float,
        period1: str, period2: str,
        doc1: str, doc2: str,
    ) -> Optional[str]:
        """Check if a value difference can be explained by context."""

        # Different time periods
        if period1 and period2 and period1 != period2:
            return "different time periods ({} vs {})".format(period1, period2)

        # Different units
        unit1 = f1.get("unit", "").lower()
        unit2 = f2.get("unit", "").lower()
        if unit1 != unit2 and unit1 and unit2:
            return "different units ({} vs {})".format(
                f1.get("unit", ""), f2.get("unit", "")
            )

        # Standalone vs consolidated
        ctx1 = (f1.get("context", "") + " " + f1.get("source_text", "")).lower()
        ctx2 = (f2.get("context", "") + " " + f2.get("source_text", "")).lower()
        if ("standalone" in ctx1 and "consolidated" in ctx2) or \
           ("consolidated" in ctx1 and "standalone" in ctx2):
            return "standalone vs consolidated financial statements"

        # Provisional vs revised estimates
        if ("provisional" in ctx1 and "revised" in ctx2) or \
           ("revised" in ctx1 and "provisional" in ctx2):
            return "provisional vs revised estimates"

        # Different base years (for GDP/economic data)
        base1 = re.search(r'(?:base\s*year|at\s+\d{4}[-–]\d{2}\s+prices)', ctx1)
        base2 = re.search(r'(?:base\s*year|at\s+\d{4}[-–]\d{2}\s+prices)', ctx2)
        if base1 and base2 and base1.group() != base2.group():
            return "different base years ({} vs {})".format(base1.group(), base2.group())

        # Advance estimate vs actual
        if ("advance" in ctx1 or "estimate" in ctx1) and ("actual" in ctx2 or "revised" in ctx2):
            return "advance estimate vs actual/revised figure"
        if ("actual" in ctx1 or "revised" in ctx1) and ("advance" in ctx2 or "estimate" in ctx2):
            return "actual/revised figure vs advance estimate"

        # Rounding differences (values close but not exact)
        if _values_match(v1, v2, tolerance_pct=10.0):
            return "likely rounding difference ({:.2f} vs {:.2f})".format(v1, v2)

        return None

    def _build_corroboration_reasoning(
        self,
        f1: Dict[str, Any], f2: Dict[str, Any],
        doc1: str, doc2: str,
    ) -> str:
        """Generate natural language reasoning for a corroboration."""
        pred = f1.get("predicate", f1.get("normalized_predicate", "metric"))
        period = f1.get("time_period", "") or f2.get("time_period", "")
        period_str = " for {}".format(period) if period else ""

        return (
            "CORROBORATED: {subject}'s {predicate}{period} is consistently reported as "
            "{val1} in \"{doc1}\" and {val2} in \"{doc2}\". "
            "Both sources agree on this figure{period}, providing strong cross-document "
            "validation of this fact."
        ).format(
            subject=f1.get("subject", "Entity"),
            predicate=pred,
            period=period_str,
            val1=_format_value(f1),
            doc1=doc1,
            val2=_format_value(f2),
            doc2=doc2,
        )

    def _build_contradiction_reasoning(
        self,
        f1: Dict[str, Any], f2: Dict[str, Any],
        v1: float, v2: float,
        doc1: str, doc2: str,
    ) -> str:
        """Generate natural language reasoning for a contradiction."""
        pred = f1.get("predicate", f1.get("normalized_predicate", "metric"))
        period = f1.get("time_period", "") or f2.get("time_period", "")
        period_str = " for {}".format(period) if period else ""
        pct_diff = abs(v1 - v2) / max(abs(v1), abs(v2)) * 100

        return (
            "CONTRADICTION: {subject}'s {predicate}{period} is reported as "
            "{val1} in \"{doc1}\" but {val2} in \"{doc2}\" — a {pct:.1f}% difference. "
            "Both documents appear to reference the same {predicate}{period}, "
            "suggesting a genuine discrepancy that may warrant investigation."
        ).format(
            subject=f1.get("subject", "Entity"),
            predicate=pred,
            period=period_str,
            val1=_format_value(f1),
            doc1=doc1,
            val2=_format_value(f2),
            doc2=doc2,
            pct=pct_diff,
        )

    def _build_reconciliation_reasoning(
        self,
        f1: Dict[str, Any], f2: Dict[str, Any],
        v1: float, v2: float,
        doc1: str, doc2: str,
        reason: str,
    ) -> str:
        """Generate reasoning for a contextual reconciliation."""
        pred = f1.get("predicate", f1.get("normalized_predicate", "metric"))

        return (
            "RECONCILED: {subject}'s {predicate} appears different — "
            "{val1} in \"{doc1}\" vs {val2} in \"{doc2}\" — but this is explained by "
            "{reason}. The apparent contradiction dissolves when accounting for "
            "this contextual difference."
        ).format(
            subject=f1.get("subject", "Entity"),
            predicate=pred,
            val1=_format_value(f1),
            doc1=doc1,
            val2=_format_value(f2),
            doc2=doc2,
            reason=reason,
        )

    def _deduplicate_relationships(self, rels: List[Relationship]) -> List[Relationship]:
        """Remove duplicate relationships (same fact pairs)."""
        seen = set()
        unique = []
        for rel in rels:
            fact_ids = json.loads(rel.fact_ids) if isinstance(rel.fact_ids, str) else rel.fact_ids
            key = tuple(sorted(fact_ids))
            if key not in seen:
                seen.add(key)
                unique.append(rel)
        return unique
