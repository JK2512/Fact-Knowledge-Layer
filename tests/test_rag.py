"""
Unit tests for Contradiction-Aware RAG Engine and the 4 Core Demo Cases.
"""

import unittest
from backend.rag.rag_engine import RAGEngine


class TestRAGCoreCases(unittest.TestCase):

    def setUp(self):
        self.rag = RAGEngine()

    def test_case_1_corroboration(self):
        """Case 1: Corroboration across sources for Delhivery FY24 Express Parcel Shipments (740M)."""
        q = "Which sources corroborate Delhivery's FY24 express parcel shipment volume?"
        res = self.rag.query(q)
        self.assertEqual(res["confidence"], "HIGH")
        self.assertEqual(res["validation"]["validation_status"], "VERIFIED")
        self.assertIn("740", res["answer"])
        self.assertIn("02-delhivery-annual-report-fy24-excerpt.pdf", res["answer"])
        self.assertIn("03-delhivery-q4-fy24-earnings-presentation.pdf", res["answer"])
        self.assertIn("CORROBORATION", res["answer"])
        self.assertTrue(len(res["facts_used"]) > 0)
        self.assertTrue(len(res["evidence"]) > 0)

    def test_case_2_contradiction(self):
        """Case 2: Contradiction / Discrepancy detection (6.4% vs 6.5%) without forced resolution."""
        q = "Do the sources agree on India's FY25 real GDP growth?"
        res = self.rag.query(q)
        self.assertIn(res["confidence"], ["HIGH", "MEDIUM"])
        self.assertEqual(res["validation"]["validation_status"], "VERIFIED")
        self.assertIn("6.4", res["answer"])
        self.assertIn("6.5", res["answer"])
        self.assertIn("CONTRADICTION", res["answer"])
        self.assertIn("CORROBORATION", res["answer"])
        self.assertIn("01-india-economic-survey-2024-25-excerpt.pdf", res["answer"])
        self.assertIn("02-rbi-annual-report-2024-25-excerpt.pdf", res["answer"])
        self.assertIn("03-imf-india-2025-article-iv-excerpt.pdf", res["answer"])
        self.assertTrue(len(res["relationships"]) > 0)

    def test_case_3_contextual_difference(self):
        """Case 3: Contextual reconciliation / definition differences (RBI 4.7% vs IMF 4.9% Fiscal Deficit)."""
        q = "Why do the fiscal deficit figures differ across the sources?"
        res = self.rag.query(q)
        self.assertEqual(res["confidence"], "HIGH")
        self.assertEqual(res["validation"]["validation_status"], "VERIFIED")
        self.assertIn("4.7", res["answer"])
        self.assertIn("4.9", res["answer"])
        self.assertIn("CONTEXTUAL DIFFERENCE", res["answer"])
        self.assertIn("02-rbi-annual-report-2024-25-excerpt.pdf", res["answer"])
        self.assertIn("03-imf-india-2025-article-iv-excerpt.pdf", res["answer"])

    def test_case_4_uncertainty_handling(self):
        """Case 4: Explicit uncertainty on missing unit context (81,417.43 revenue ambiguity)."""
        q = "Can the 81,417.43 revenue value be safely interpreted?"
        res = self.rag.query(q)
        self.assertEqual(res["confidence"], "UNCERTAIN")
        self.assertEqual(res["validation"]["validation_status"], "UNCERTAIN")
        self.assertIn("Unable to safely interpret", res["answer"])
        self.assertIn("81,417.43", res["answer"])


if __name__ == "__main__":
    unittest.main()
