"""
Unit tests for Structured, Semantic, and Hybrid Retrieval.
"""

import unittest
from backend.retrieval.structured_retriever import StructuredRetriever
from backend.retrieval.semantic_retriever import SemanticRetriever
from backend.retrieval.hybrid_retriever import HybridRetriever


class TestRetrieval(unittest.TestCase):

    def setUp(self):
        self.struct = StructuredRetriever()
        self.sem = SemanticRetriever()
        self.hybrid = HybridRetriever()

    def test_query_interpretation(self):
        q = "What was India's FY25 real GDP growth and do sources agree?"
        interp = self.struct.interpret_query(q)
        self.assertIn("india", interp.subjects)
        self.assertIn("gdp", interp.metrics)
        self.assertTrue(any("25" in p for p in interp.periods))
        self.assertEqual(interp.intent, "contradiction_check")

    def test_structured_retrieval(self):
        interp = self.struct.interpret_query("What was India's GDP growth in FY25?")
        facts = self.struct.retrieve(interp, limit=10)
        self.assertTrue(len(facts) > 0)
        self.assertTrue(any("6." in str(f.value) or "7." in str(f.value) for f in facts))

    def test_semantic_retrieval(self):
        facts = self.sem.search("Delhivery revenue and shipments", top_k=10)
        self.assertTrue(len(facts) > 0)
        self.assertTrue(all(hasattr(f, "retrieval_score") for f in facts))

    def test_hybrid_retrieval_merge(self):
        res = self.hybrid.retrieve("Delhivery express parcel shipments FY24", top_k=10)
        self.assertFalse(res.is_empty)
        self.assertTrue(len(res.facts) > 0)
        self.assertTrue(len(res.evidence) > 0)
        self.assertTrue(len(res.sources) > 0)


if __name__ == "__main__":
    unittest.main()
