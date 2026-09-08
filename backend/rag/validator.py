"""
Evidence Validator.
Performs deterministic post-generation validation on RAG answers.
Verifies that all numerical values, percentages, periods, and document citations in the answer
are directly grounded in the retrieved facts and evidence.
"""

import re
from typing import List, Dict, Any, Tuple
from backend.retrieval.schemas import RetrievedFact, RetrievalResult


class EvidenceValidator:
    """Verifies that generated answers do not contain hallucinated numbers, facts, or citations."""

    def __init__(self):
        pass

    def validate(
        self,
        answer_text: str,
        retrieval_result: RetrievalResult,
    ) -> Dict[str, Any]:
        """Validate answer against retrieved facts.
        
        Returns:
            Dict containing:
            - is_valid: bool
            - validation_status: "VERIFIED" | "UNSUPPORTED_METRIC_DETECTED" | "UNCERTAIN" | "NO_EVIDENCE"
            - grounded_metrics: List[str]
            - ungrounded_metrics: List[str]
            - confidence_adjustment: str ("HIGH" | "MEDIUM" | "LOW" | "UNCERTAIN")
            - audit_details: str
        """
        if not answer_text or retrieval_result.is_empty or not retrieval_result.facts:
            return {
                "is_valid": False,
                "validation_status": "NO_EVIDENCE",
                "grounded_metrics": [],
                "ungrounded_metrics": [],
                "confidence_adjustment": "UNCERTAIN",
                "audit_details": "No grounded evidence available in knowledge store for this query.",
            }

        # 1. Extract all numbers and percentages from the answer
        # e.g., "6.4%", "6.5%", "740 million", "7.2%", "81,417.43"
        number_pattern = re.compile(
            r'(\b\d[\d,]*(?:\.\d+)?\s*(?:%|cr|crore|crores|lakh|lakhs|million|mn|billion|bn|thousand|bps)?\b)',
            re.IGNORECASE
        )
        answer_tokens = number_pattern.findall(answer_text)

        # 2. Extract ground-truth numbers/values from retrieved facts
        ground_truth_values = set()
        ground_truth_raw = set()
        for f in retrieval_result.facts:
            if f.value:
                ground_truth_raw.add(f.value.strip().lower())
                # Normalize raw numbers
                num_only = re.sub(r'[^\d\.]', '', f.value)
                if num_only:
                    ground_truth_values.add(num_only)
            if f.numeric_value is not None:
                ground_truth_values.add(str(f.numeric_value))
                ground_truth_values.add(f"{f.numeric_value:.1f}")
                ground_truth_values.add(f"{f.numeric_value:.2f}")

        # Also add values, source text, page numbers from facts
        for f in retrieval_result.facts:
            if f.source_page:
                ground_truth_values.add(str(f.source_page))
            if f.source_text:
                for match in number_pattern.findall(f.source_text):
                    ground_truth_raw.add(match.strip().lower())
                    n_clean = re.sub(r'[^\d\.]', '', match)
                    if n_clean:
                        ground_truth_values.add(n_clean)

        # Also add values from relationships reasoning and connected facts
        for rel in retrieval_result.relationships:
            reasoning = rel.get("reasoning", "")
            if reasoning:
                for match in number_pattern.findall(reasoning):
                    ground_truth_raw.add(match.strip().lower())
                    n_clean = re.sub(r'[^\d\.]', '', match)
                    if n_clean:
                        ground_truth_values.add(n_clean)
            for rf in rel.get("facts", []):
                val = rf.get("value", "")
                if val:
                    ground_truth_raw.add(val.strip().lower())
                    num_only = re.sub(r'[^\d\.]', '', val)
                    if num_only:
                        ground_truth_values.add(num_only)

        # 3. Check each number extracted from the answer
        grounded_metrics = []
        ungrounded_metrics = []

        # Common innocuous numbers to ignore (single digit ordinals, 100%)
        ignored_numbers = {"1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "100"}

        for token in answer_tokens:
            token_clean = token.strip().lower()
            token_num = re.sub(r'[^\d\.]', '', token)
            
            # Check if token matches raw or numeric ground truth
            is_grounded = False
            if any(token_clean in gt or gt in token_clean for gt in ground_truth_raw):
                is_grounded = True
            elif token_num and token_num in ground_truth_values:
                is_grounded = True
            elif token_num and any(gt.startswith(token_num) or token_num.startswith(gt) for gt in ground_truth_values if len(gt) > 1):
                is_grounded = True
            elif token_num in ignored_numbers:
                is_grounded = True

            if is_grounded:
                grounded_metrics.append(token)
            else:
                ungrounded_metrics.append(token)

        # Deduplicate
        grounded_metrics = list(dict.fromkeys(grounded_metrics))
        ungrounded_metrics = list(dict.fromkeys(ungrounded_metrics))

        # 4. Determine validation status
        if ungrounded_metrics:
            return {
                "is_valid": False,
                "validation_status": "UNSUPPORTED_METRIC_DETECTED",
                "grounded_metrics": grounded_metrics,
                "ungrounded_metrics": ungrounded_metrics,
                "confidence_adjustment": "LOW",
                "audit_details": f"Detected {len(ungrounded_metrics)} unsupported numerical claim(s): {', '.join(ungrounded_metrics)}.",
            }

        # Check if contradiction exists in facts
        has_contradiction = any(
            r.get("relationship_type") == "contradiction"
            for r in retrieval_result.relationships
        )

        return {
            "is_valid": True,
            "validation_status": "VERIFIED",
            "grounded_metrics": grounded_metrics,
            "ungrounded_metrics": [],
            "confidence_adjustment": "HIGH" if not has_contradiction else "MEDIUM",
            "audit_details": f"All {len(grounded_metrics)} numerical claim(s) successfully verified against source evidence.",
        }
