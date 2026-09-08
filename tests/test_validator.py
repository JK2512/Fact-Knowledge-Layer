"""
Unit tests for the Evidence Validator.
Ensures hallucinated or unsupported numerical claims are strictly caught.
"""

import unittest
from backend.rag.validator import EvidenceValidator
from backend.retrieval.schemas import RetrievalResult, RetrievedFact, QueryInterpretation


class TestEvidenceValidator(unittest.TestCase):

    def setUp(self):
        self.validator = EvidenceValidator()

    def test_grounded_answer_validation(self):
        fact = RetrievedFact(
            id="f1",
            document_id="d1",
            document_filename="economic_survey.pdf",
            document_title="Economic Survey",
            fact_type="numerical",
            subject="India",
            predicate="GDP growth",
            value="6.4%",
            numeric_value=6.4,
            unit="%",
            time_period="FY25",
            confidence=0.9,
            source_page=14,
            source_text="Real GDP growth is projected at 6.4% in FY25.",
            context="",
            normalized_subject="india",
            normalized_predicate="gdp_growth",
            normalized_period="FY2025",
            normalized_value=6.4,
        )

        retrieval = RetrievalResult(
            query="What is India GDP growth?",
            interpretation=QueryInterpretation(raw_query=""),
            facts=[fact],
            relationships=[],
            evidence=[],
            sources=[],
        )

        valid_answer = "India's projected real GDP growth is 6.4% for FY25 according to the Economic Survey on Page 14."
        res = self.validator.validate(valid_answer, retrieval)
        self.assertTrue(res["is_valid"])
        self.assertEqual(res["validation_status"], "VERIFIED")

    def test_hallucinated_number_rejection(self):
        fact = RetrievedFact(
            id="f1",
            document_id="d1",
            document_filename="economic_survey.pdf",
            document_title="Economic Survey",
            fact_type="numerical",
            subject="India",
            predicate="GDP growth",
            value="6.4%",
            numeric_value=6.4,
            unit="%",
            time_period="FY25",
            confidence=0.9,
            source_page=14,
            source_text="Real GDP growth is projected at 6.4% in FY25.",
            context="",
            normalized_subject="india",
            normalized_predicate="gdp_growth",
            normalized_period="FY2025",
            normalized_value=6.4,
        )

        retrieval = RetrievalResult(
            query="What is India GDP growth?",
            interpretation=QueryInterpretation(raw_query=""),
            facts=[fact],
            relationships=[],
            evidence=[],
            sources=[],
        )

        # Answer introduces unsupported 9.8% metric
        hallucinated_answer = "India's GDP growth reached 9.8% in FY25."
        res = self.validator.validate(hallucinated_answer, retrieval)
        self.assertFalse(res["is_valid"])
        self.assertEqual(res["validation_status"], "UNSUPPORTED_METRIC_DETECTED")
        self.assertTrue(any("9.8" in m for m in res["ungrounded_metrics"]))
        self.assertEqual(res["confidence_adjustment"], "LOW")


if __name__ == "__main__":
    unittest.main()
